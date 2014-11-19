from collections import namedtuple
from . import fields
from .manager import DESCENDING_ORDER, ASCENDING_ORDER
from .reference import ResourceBound
from .utils import get_value
from .schema import Schema


Comparator = namedtuple('Comparator', ['name', 'schema', 'supported_types'])

DEFAULT_COMPARATORS = (
    Comparator('$eq',
                lambda field: field.response,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$ne',
                lambda field: field.response,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$in',
               lambda field: {
                   "type": "array",
                   # "minItems": 1, # NOTE: Permitting 0 items for now.
                   "uniqueItems": True,
                   "items": field.response  # NOTE: None is valid.
               },
               (fields.String, fields.Integer, fields.Number)),
    Comparator('$lt',
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$gt',
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$lte',
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$gte',
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$text',
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$startswith',  # TODO case insensitive
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$endswith',  # TODO case insensitive
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
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
        return self.comparator(self.value, get_value(self.attribute, item, None))


class Instances(Schema, ResourceBound):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """

    def __init__(self, resource, default_sort=None, filters=None):
        self.allowed_filters = filters
        self.filters = {}
        self.sort_fields = []

    def bind(self, resource):
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

    def schema(self):
        request_schema = {
            "type": "object",
            "properties": {
                "where": {
                    "type": "object",
                    "properties": {
                        name: self._filter_field_schema(field, comparators)
                        for name, (field, comparators) in self.filters.items()
                    },
                    "additionalProperties": False
                },
                "sort": {
                    "type": "object",
                    "properties": { # FIXME switch to tuples
                        name: {"type": "integer", "enum": [DESCENDING_ORDER, ASCENDING_ORDER]}
                        for name in self.sort_fields
                    },
                    "additionalProperties": False
                },
                "page": {
                    "type": "integer",
                    "minimum": 1
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                   # "maximum": self.resource.potion.max_per_page
                }
            }

        }

        response_schema = {
            "type": "array",
            "items": {"$ref": "#"}
        }

        return response_schema, request_schema

    def convert(self, value):
        pass
        # TODO properties -> field attributes
        # parse filters