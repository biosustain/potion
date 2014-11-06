from collections import namedtuple
from sqlalchemy import func
from . import fields
from .schema import Schema

Comparator = namedtuple('Comparator', ['name', 'expression', 'schema', 'supported_types'])

DEFAULT_COMPARATORS = (
    Comparator('$eq',
                lambda column, value: column == value,
                lambda field: field.schema,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$ne',
                lambda column, value: column != value,
                lambda field: field.schema,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$in',
               lambda column, value: column.in_(value) if len(value) else False,
               lambda field: {
                   "type": "array",
                   # "minItems": 1, # NOTE: Permitting 0 items for now.
                   "uniqueItems": True,
                   "items": field.schema  # NOTE: None is valid.
               },
               (fields.String, fields.Integer, fields.Number)),
    Comparator('$lt',
               lambda column, value: column < value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$gt',
               lambda column, value: column > value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$lte',
               lambda column, value: column <= value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$gte',
               lambda column, value: column >= value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$text',
               lambda column, value: column.op('@@')(func.plainto_tsquery(value)),
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$startswith',  # TODO case insensitive
               lambda column, value: column.startswith(value.replace('%', '\\%')),
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$endswith',  # TODO case insensitive
               lambda column, value: column.endswith(value.replace('%', '\\%')),
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

IMPLICIT_COMPARATOR = '$eq'

ALL = '*'

class Filter(Schema):
    def __init__(self, fieldset, allowed_filters=None):
        self.filters = {}
        self.allowed_filters = None

        if allowed_filters in (ALL, None):
            allowed_filters = ALL
        elif isinstance(allowed_filters, (list, tuple)):
            allowed_filters = {field: ALL for field in allowed_filters}
        elif isinstance(allowed_filters, dict):
            pass

        for name, field in fieldset.fields.items():
            try:
                available_comparators = COMPARATORS_BY_TYPE[field.__class__]
            except KeyError:
                continue

            if allowed_filters == ALL:
                self.filters[name] = field, available_comparators
            elif name in allowed_filters:
                if allowed_filters[name] == ALL:
                    comparators = available_comparators
                else:
                    comparators = [c for c in allowed_filters[name] if c in available_comparators]

                self.filters[name] = field, comparators

    def _filter_field_schema(self, field, comparators):
        if len(comparators) == 1 and comparators[0].name == IMPLICIT_COMPARATOR:
            return comparators[0].schema(field)

        explicit_options = {
            "type": "object",
            "properties": {c.name: c.schema(field) for c in comparators if c.name != IMPLICIT_COMPARATOR},
            "minProperties": 1,
            "maxProperties": 1,
        }

        if comparators[IMPLICIT_COMPARATOR] in comparators:
            return {
                "oneOf": [
                    explicit_options,
                    comparators[IMPLICIT_COMPARATOR].schema(field)
                ]
            }

        return explicit_options



    # def get_sa_expression(self, model, where):
    #     expressions = []
    #
    #     for name, where_clause in where.items():
    #         field, comparators = self.fields[name]
    #         column = getattr(self.model, field.attribute)
    #
    #         try:
    #             validate(where_clause, self._filter_field_schema(field))
    #         except ValidationError as ve:
    #             abort(400, message="Bad filter: {}".format(where_clause))
    #
    #         comparator = None
    #         value = None
    #
    #         if isinstance(where_clause, dict):
    #             for c in comparators:
    #                 if c.name in where_clause:
    #                     comparator = c
    #                     value = where_clause[c.name]
    #                     break
    #
    #             if not comparator:
    #                 abort(400, message='Bad filter expression: {}'.format(where_clause))
    #         elif isinstance(where_clause, list):
    #             comparator = self.comparators['$in']
    #             value = where_clause
    #         else:
    #             comparator = self.comparators['$eq']
    #             value = where_clause
    #
    #         expressions.append(comparator.expression(column, value))
    #
    #     if len(expressions) == 1:
    #         return expressions[0]
    #
    #     # TODO ranking by default with text-search.
    #
    #     return and_(*expressions)

    def schema(self):
        return {
            "type": "object",
            "properties": {
                name: self._filter_field_schema(field, comparators)
                for name, (field, comparators) in self.filters.items()
            },
            "additionalProperties": False
        }

SORT_DESCENDING = -1
SORT_ASCENDING = 1

class Sort(Schema):

    def __init__(self, fieldset, allowed_filters=None):
        sortable = None
        if allowed_filters in (ALL, None):
            sortable = fieldset.fields
        elif isinstance(allowed_filters, (list, tuple, dict)):
            sortable = {name: fieldset.fields[name] for name in allowed_filters}
        else:
            raise RuntimeError("Meta.allowed_filters is not configured properly")

        self.sortable = [name for name, field in sortable.items()
                         if field.__class__ in (fields.String, fields.Boolean, fields.Number, fields.Integer)]

    def get_sa_sort_criteria(self, model, fieldset, sort):
        for name, order in sort.items():
            field = fieldset.fields[name]
            column = getattr(model, field.attribute)

            if order == SORT_DESCENDING:
                yield column.desc()
            else:
                yield column.asc()

    def schema(self):
        return {
            "type": "object",
            "properties": {
                name: {"type": "integer", "enum": [SORT_DESCENDING, SORT_ASCENDING]}
                for name in self.sortable
            },
            "additionalProperties": False
        }