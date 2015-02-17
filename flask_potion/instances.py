from collections import namedtuple
import collections

from flask import json, request, current_app
from flask_sqlalchemy import Pagination as SAPagination
from werkzeug.utils import cached_property

from flask_potion import fields
from .exceptions import InvalidJSON
from .backends import Pagination
from .fields import ToMany
from .reference import ResourceBound
from .utils import get_value
from .schema import Schema


Comparator = namedtuple('Comparator', ['name', 'schema', 'expression', 'supported_types'])

DEFAULT_COMPARATORS = (
    Comparator('$eq',
               lambda field: field.response,
               lambda eq, value: value == eq,
               (fields.Boolean, fields.String, fields.Integer, fields.Number, fields.ToOne)),
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
    Comparator('$contains',
               lambda field: field.container.response,
               lambda contains, value: value and contains in value,
               (fields.Array, fields.ToMany)),
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
    for t in (fields.Boolean, fields.String, fields.Integer, fields.Number, fields.ToOne)
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


class PaginationMixin(object):
    query_params = ()

    def format_response(self, data):
        if not isinstance(data, (Pagination, SAPagination)):
            return self.format(data)

        links = [(request.path, data.page, data.per_page, 'self')]

        if data.has_prev:
            links.append((request.path, 1, data.per_page, 'first'))
            links.append((request.path, data.page - 1, data.per_page, 'prev'))
        if data.has_next:
            links.append((request.path, data.page + 1, data.per_page, 'next'))

        # HACK max(data.pages, 1): Flask-SQLAlchemy returns pages=0 when no results are returned
        links.append((request.path, max(data.pages, 1), data.per_page, 'last'))

        # FIXME links must contain filters & sort
        # TODO include query_params

        headers = {
            'Link': ','.join(('<{0}?page={1}&per_page={2}>; rel="{3}"'.format(*link) for link in links)),
            'X-Total-Count': data.total
        }

        return self.format(data.items), 200, headers


class RelationInstances(PaginationMixin, ToMany):
    pass


class Instances(PaginationMixin, Schema, ResourceBound):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """
    query_params = ('where', 'sort')

    def __init__(self, default_sort=None, filters=None):

        # TODO only allow filters supported by the manager
        if filters in (ALL, None):
            filters = ALL
        elif isinstance(filters, (list, tuple)):
            filters = {field: ALL for field in filters}
        elif isinstance(filters, dict):
            filters = dict(filters)

        self.allowed_filters = filters
        self.filters = {}
        self.sort_fields = []

    def _on_bind(self, resource):
        fs = resource.schema
        filters = self.allowed_filters

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

    def rebind(self, resource):
        return self.__class__(
            filters=self.allowed_filters
        ).bind(resource)

    @classmethod
    def _is_sortable(cls, field):
        return isinstance(field, (fields.String,
                                  fields.Boolean,
                                  fields.Number,
                                  fields.Integer,
                                  fields.Date,
                                  fields.DateTime))

    def _filter_field_schema(self, field, comparators):
        if len(comparators) == 1 and comparators[0].name == EQUALITY_COMPARATOR:
            return comparators[0].schema(field)

        comparator_options = {
            "type": "object",
            "properties": {c.name: c.schema(field) for c in comparators if c.name != EQUALITY_COMPARATOR},
            "minProperties": 1,
            "maxProperties": 1,
            "additionalProperties": False
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
                             name: {"type": "boolean", "title": "Reverse order?"}
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
                    "maximum": current_app.config['POTION_MAX_PER_PAGE'],
                    "default": current_app.config['POTION_DEFAULT_PER_PAGE'],
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
            if isinstance(condition, dict) and '$ref' not in condition:
                # if len(condition) == 1 and '$ref' in condition:

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
                value = field.convert(condition)

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
            per_page = request.args.get('per_page', current_app.config['POTION_DEFAULT_PER_PAGE'], type=int)
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
