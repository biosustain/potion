from flask_potion import fields
import flask_potion.filters as filters


class EqualFilter(filters.EqualFilter):
    def expression(self, value):
        return {self.attribute: value}


class NotEqualFilter(filters.NotEqualFilter):
    def expression(self, value):
        return {"{}__ne".format(self.attribute): value}


class LessThanFilter(filters.LessThanFilter):
    def expression(self, value):
        return {"{}__lt".format(self.attribute): value}


class LessThanEqualFilter(filters.LessThanEqualFilter):
    def expression(self, value):
        return {"{}__lte".format(self.attribute): value}


class GreaterThanFilter(filters.GreaterThanFilter):
    def expression(self, value):
        return {"{}__gt".format(self.attribute): value}


class GreaterThanEqualFilter(filters.GreaterThanEqualFilter):
    def expression(self, value):
        return {"{}__gte".format(self.attribute): value}


class InFilter(filters.InFilter):
    def expression(self, values):
        return {"{}__in".format(self.attribute): values}


class ContainsFilter(filters.ContainsFilter):
    def expression(self, value):
        return {"{}__contains".format(self.attribute): value}


class StringContainsFilter(filters.StringContainsFilter):
    def expression(self, value):
        return {"{}__contains".format(self.attribute): value}


class StringIContainsFilter(filters.StringIContainsFilter):
    def expression(self, value):
        return {"{}__icontains".format(self.attribute): value}


class StartsWithFilter(filters.StartsWithFilter):
    def expression(self, value):
        return {"{}__startswith".format(self.attribute): value}


class IStartsWithFilter(filters.IStartsWithFilter):
    def expression(self, value):
        return {"{}__istartswith".format(self.attribute): value}


class EndsWithFilter(filters.EndsWithFilter):
    def expression(self, value):
        return {"{}__endswith".format(self.attribute): value}


class IEndsWithFilter(filters.IEndsWithFilter):
    def expression(self, value):
        return {"{}__iendswith".format(self.attribute): value}


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
