from collections import namedtuple
from . import fields, ValidationError
import collections

from flask import json, request
from werkzeug.exceptions import InternalServerError
from werkzeug.utils import cached_property
from .exceptions import InvalidJSON
from .backends import Pagination
from .reference import ResourceBound
from .utils import get_value
from .schema import Schema


Comparator = namedtuple('Comparator', ['name', 'schema', 'expression', 'supported_types'])

DEFAULT_COMPARATORS = (
    Comparator('$eq',
               lambda field: field.response,
               lambda eq, value: value == eq,
               (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$ne',
               lambda field: field.response,
               lambda ne, value: value != ne,
               (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$in',
               lambda field: {
                   "type": "array",
                   # "minItems": 1, # NOTE: Permitting 0 items for now.
                   "uniqueItems": True,
                   "items": field.response  # NOTE: None is valid.
               },
               lambda in_, value: value in in_,
               (fields.String, fields.Integer, fields.Number)),
    Comparator('$lt',
               lambda field: {"type": "number"},
               lambda lt, value: value < lt,
               (fields.Integer, fields.Number)),
    Comparator('$gt',
               lambda field: {"type": "number"},
               lambda gt, value: value > gt,
               (fields.Integer, fields.Number)),
    Comparator('$lte',
               lambda field: {"type": "number"},
               lambda lte, value: value <= lte,
               (fields.Integer, fields.Number)),
    Comparator('$gte',
               lambda field: {"type": "number"},
               lambda gte, value: value <= gte,
               (fields.Integer, fields.Number)),
    Comparator('$text',
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               lambda text, value: value and text in value,
               (fields.String,)),
    Comparator('$startswith',  # TODO case insensitive
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               lambda sw, value: value and value.startswith(sw),
               (fields.String,)),
    Comparator('$endswith',  # TODO case insensitive
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               lambda ew, value: value and value.endswith(ew),
               (fields.String,))

)

COMPARATORS = {c.name: c for c in DEFAULT_COMPARATORS}

COMPARATORS_BY_TYPE = {
    t: [c for c in DEFAULT_COMPARATORS if t in c.supported_types]
    for t in (fields.Boolean, fields.String, fields.Integer, fields.Number)
}

EQUALITY_COMPARATOR = '$eq'

ALL = '*'


class Condition(object):
    def __init__(self, attribute, comparator, value):
        self.attribute = attribute
        self.comparator = comparator
        self.value = value

    def __call__(self, item):
        return self.comparator.expression(self.value, get_value(self.attribute, item, None))


class Instances(Schema, ResourceBound):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """

    def __init__(self, reference, default_sort=None, filters=None):
        self.allowed_filters = filters
        self.filters = {}
        self.sort_fields = []

    def bind(self, resource):
        super(Instances, self).bind(resource)

        fs = resource.schema
        filters = self.allowed_filters

        # TODO only allow filters supported by the manager

        if filters in (ALL, None):
            filters = ALL
        elif isinstance(filters, (list, tuple)):
            filters = {field: ALL for field in filters}
        elif isinstance(filters, dict):
            pass

        for name, field in fs.fields.items():
            try:
                available_comparators = COMPARATORS_BY_TYPE[field.__class__]
            except KeyError:
                continue

            if filters == ALL:
                self.filters[name] = field, available_comparators
            elif name in filters:
                if filters[name] == ALL:
                    comparators = available_comparators
                else:
                    comparators = [c for c in filters[name] if c in available_comparators]

                self.filters[name] = field, comparators

        if filters in (ALL, None):
            sort = fs.fields
        elif isinstance(filters, (list, tuple, dict)):
            sort = {name: fs.fields[name] for name in filters}
        else:
            raise RuntimeError("Meta.allowed_filters is not configured properly")

        self.sort_fields = {name: field for name, field in sort.items() if self._is_sortable(field)}

    @classmethod
    def _is_sortable(cls, field):
        return isinstance(field, (fields.String, fields.Boolean, fields.Number, fields.Integer))

    def _filter_field_schema(self, field, comparators):
        if len(comparators) == 1 and comparators[0].name == EQUALITY_COMPARATOR:
            return comparators[0].schema(field)

        comparator_options = {
            "type": "object",
            "properties": {c.name: c.schema(field) for c in comparators if c.name != EQUALITY_COMPARATOR},
            "minProperties": 1,
            "maxProperties": 1
        }

        if COMPARATORS[EQUALITY_COMPARATOR] in comparators:
            return {
                "oneOf": [
                    comparator_options,
                    COMPARATORS[EQUALITY_COMPARATOR].schema(field)
                ]
            }

        return comparator_options

    @cached_property
    def _where_schema(self):
        return {
            "type": "object",
            "properties": {
                name: self._filter_field_schema(field, comparators)
                for name, (field, comparators) in self.filters.items()
            },
            "additionalProperties": False
        }

    @cached_property
    def _sort_schema(self):
        return {
            "type": "object",
            "properties": {  # FIXME switch to tuples
                             name: {"type": "boolean"}
                             for name in self.sort_fields
            },
            "additionalProperties": False
        }

    def schema(self):
        request_schema = {
            "type": "object",
            "properties": {
                "where": self._where_schema,
                "sort": self._sort_schema,
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": self.resource.potion.max_per_page,
                    "default": self.resource.potion.default_per_page
                }
            },
            "additionalProperties": True
        }

        response_schema = {
            "type": "array",
            "items": {"$ref": "#"}
        }

        return response_schema, request_schema

    # def convert(self, value):
    # pass
    #     # TODO properties -> field attributes
    #     # parse filters

    def _convert_where(self, where):
        for name, condition in where.items():
            field, comparators = self.filters[name]

            value = None
            comparator = None
            if isinstance(condition, dict):
                for c in comparators:
                    if c.name in condition:
                        comparator = c
                        value = condition[c.name]
                        break

                assert comparator is not None
            elif isinstance(condition, list):
                comparator = COMPARATORS['$in']
                value = condition
            else:
                comparator = COMPARATORS['$eq']
                value = condition

            yield Condition(field.attribute or name, comparator, value)

    def _convert_sort(self, sort):
        for name, reverse in sort.items():
            field = self.sort_fields[name]
            yield field.attribute or name, reverse

    def parse_request(self, request):
        # TODO convert instances to FieldSet
        # TODO (implement in FieldSet too:) load values from request.args
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', self.resource.potion.default_per_page, type=int)
            where = json.loads(request.args.get('where', '{}'))  # FIXME
            sort = json.loads(request.args.get('sort', '{}'), object_pairs_hook=collections.OrderedDict)
        except ValueError:
            raise InvalidJSON()

        result = self.convert({
            "page": page,
            "per_page": per_page,
            "where": where,
            "sort": sort
        })

        result['where'] = tuple(self._convert_where(result['where']))
        result['sort'] = tuple(self._convert_sort(result['sort']))
        return result

    def format(self, items):
        return [self.resource.schema.format(item) for item in items]

    def format_response(self, items):
        if isinstance(items, list):
            return self.format(items)

        links = [(request.path, items.page, items.per_page, 'self')]

        if items.has_prev:
            links.append((request.path, 1, items.per_page, 'first'))
            links.append((request.path, items.page - 1, items.per_page, 'prev'))
        if items.has_next:
            links.append((request.path, items.page + 1, items.per_page, 'next'))

        links.append((request.path, items.pages, items.per_page, 'last'))

        # FIXME links must contain filters & sort
        headers = {'Link': ','.join(('<{0}?page={1}&per_page={2}>; rel="{3}"'.format(*link) for link in links))}
        return self.format(items.items), 200, headers