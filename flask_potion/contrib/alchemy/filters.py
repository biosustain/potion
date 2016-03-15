from sqlalchemy import and_
from flask_potion import fields
import flask_potion.filters as filters


class SQLAlchemyBaseFilter(filters.BaseFilter):
    def __init__(self, name, field=None, attribute=None, column=None):
        super(SQLAlchemyBaseFilter, self).__init__(name, field=field, attribute=attribute)
        self.column = column

    @classmethod
    def apply(cls, query, conditions):
        expressions = [condition.filter.expression(condition.value) for condition in conditions]
        if len(expressions) == 1:
            return query.filter(expressions[0])
        return query.filter(and_(*expressions))


class EqualFilter(SQLAlchemyBaseFilter, filters.EqualFilter):
    def expression(self, value):
        return self.column == value


class NotEqualFilter(SQLAlchemyBaseFilter, filters.NotEqualFilter):
    def expression(self, value):
        return self.column != value


class LessThanFilter(SQLAlchemyBaseFilter, filters.LessThanFilter):
    def expression(self, value):
        return self.column < value


class LessThanEqualFilter(SQLAlchemyBaseFilter, filters.LessThanEqualFilter):
    def expression(self, value):
        return self.column <= value


class GreaterThanFilter(SQLAlchemyBaseFilter, filters.GreaterThanFilter):
    def expression(self, value):
        return self.column > value


class GreaterThanEqualFilter(SQLAlchemyBaseFilter, filters.GreaterThanEqualFilter):
    def expression(self, value):
        return self.column >= value


class InFilter(SQLAlchemyBaseFilter, filters.InFilter):
    def expression(self, values):
        return self.column.in_(values) if len(values) else False


class ContainsFilter(SQLAlchemyBaseFilter, filters.ContainsFilter):
    def expression(self, value):
        return self.column.contains(value)


class StringContainsFilter(SQLAlchemyBaseFilter, filters.StringContainsFilter):
    def expression(self, value):
        return self.column.like('%' + value.replace('%', '\\%') + '%')


class StringIContainsFilter(SQLAlchemyBaseFilter, filters.StringIContainsFilter):
    def expression(self, value):
        return self.column.ilike('%' + value.replace('%', '\\%') + '%')


class StartsWithFilter(SQLAlchemyBaseFilter, filters.StartsWithFilter):
    def expression(self, value):
        return self.column.startswith(value.replace('%', '\\%'))


class IStartsWithFilter(SQLAlchemyBaseFilter, filters.IStartsWithFilter):
    def expression(self, value):
        return self.column.ilike(value.replace('%', '\\%') + '%')


class EndsWithFilter(SQLAlchemyBaseFilter, filters.EndsWithFilter):
    def expression(self, value):
        return self.column.endswith(value.replace('%', '\\%'))


class IEndsWithFilter(SQLAlchemyBaseFilter, filters.IEndsWithFilter):
    def expression(self, value):
        return self.column.ilike('%' + value.replace('%', '\\%'))


class DateBetweenFilter(SQLAlchemyBaseFilter, filters.DateBetweenFilter):
    def expression(self, value):
        return self.column.between(value[0], value[1])


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
    (DateBetweenFilter, 'between')
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
    (fields.Date, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        DateBetweenFilter,
        InFilter,
    )),
    (fields.DateTime, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        DateBetweenFilter,
    )),
    (fields.DateString, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        DateBetweenFilter,
        InFilter,
    )),
    (fields.DateTimeString, (
        EqualFilter,
        NotEqualFilter,
        LessThanFilter,
        LessThanEqualFilter,
        GreaterThanFilter,
        GreaterThanEqualFilter,
        DateBetweenFilter,
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
