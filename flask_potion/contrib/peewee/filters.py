from operator import and_
from flask_potion import fields
import flask_potion.filters as filters


class PeeweeBaseFilter(filters.BaseFilter):
    def __init__(self, name, field=None, attribute=None, column=None):
        super(PeeweeBaseFilter, self).__init__(name, field=field, attribute=attribute)
        self.column = column

    @classmethod
    def apply(cls, query, conditions):
        expressions = [condition.filter.expression(condition.value) for condition in conditions]
        if len(expressions) == 1:
            return query.where(expressions[0])
        return query.where(and_(*expressions))


class EqualFilter(PeeweeBaseFilter, filters.EqualFilter):
    def expression(self, value):
        return self.column == value


class NotEqualFilter(PeeweeBaseFilter, filters.NotEqualFilter):
    def expression(self, value):
        return self.column != value


class LessThanFilter(PeeweeBaseFilter, filters.LessThanFilter):
    def expression(self, value):
        return self.column < value


class LessThanEqualFilter(PeeweeBaseFilter, filters.LessThanEqualFilter):
    def expression(self, value):
        return self.column <= value


class GreaterThanFilter(PeeweeBaseFilter, filters.GreaterThanFilter):
    def expression(self, value):
        return self.column > value


class GreaterThanEqualFilter(PeeweeBaseFilter, filters.GreaterThanEqualFilter):
    def expression(self, value):
        return self.column >= value


class InFilter(PeeweeBaseFilter, filters.InFilter):
    def expression(self, values):
        return self.column << values


class ContainsFilter(PeeweeBaseFilter, filters.ContainsFilter):
    def expression(self, value):
        return self.column.contains(value)


class StringContainsFilter(PeeweeBaseFilter, filters.StringContainsFilter):
    def expression(self, value):
        return self.column % ('%' + value.replace('%', '\\%') + '%')


class StringIContainsFilter(PeeweeBaseFilter, filters.StringIContainsFilter):
    def expression(self, value):
        return self.column ** ('%' + value.replace('%', '\\%') + '%')


class StartsWithFilter(PeeweeBaseFilter, filters.StartsWithFilter):
    def expression(self, value):
        return self.column.startswith(value.replace('%', '\\%'))


class IStartsWithFilter(PeeweeBaseFilter, filters.IStartsWithFilter):
    def expression(self, value):
        return self.column ** (value.replace('%', '\\%') + "%")


class EndsWithFilter(PeeweeBaseFilter, filters.EndsWithFilter):
    def expression(self, value):
        return self.column.endswith(value.replace('%', '\\%'))


class IEndsWithFilter(PeeweeBaseFilter, filters.IEndsWithFilter):
    def expression(self, value):
        return self.column ** ("%" + value.replace('%', '\\%'))


FILTER_NAMES = (
    (EqualFilter, None),
    (EqualFilter, 'eq'),
    (NotEqualFilter, 'ne'),
    (LessThanFilter, 'lt'),
    (LessThanEqualFilter, 'lte'),
    (GreaterThanFilter, 'gt'),
    (GreaterThanEqualFilter, 'gte'),
    (InFilter, 'in'),
    (ContainsFilter, 'contains'),
    (StringContainsFilter, 'contains'),
    (StringIContainsFilter, 'icontains'),
    (StartsWithFilter, 'startswith'),
    (IStartsWithFilter, 'istartswith'),
    (EndsWithFilter, 'endswith'),
    (IEndsWithFilter, 'iendswith'),
)


FILTERS_BY_TYPE = (
    (fields.Boolean, (
        EqualFilter,
        NotEqualFilter,
        InFilter
    )),
    (fields.Integer, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        InFilter,
    )),
    (fields.Number, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        InFilter,
    )),
    (fields.String, (
        EqualFilter,
        NotEqualFilter,
        StringContainsFilter,
        StringIContainsFilter,
        StartsWithFilter,
        IStartsWithFilter,
        EndsWithFilter,
        IEndsWithFilter,
        InFilter,
    )),
    (fields.Array, (
        ContainsFilter,
    )),
    (fields.ToOne, (
        EqualFilter,
        NotEqualFilter,
        InFilter,
    )),
    (fields.ToMany, (
        ContainsFilter,
    )),
)
