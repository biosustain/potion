from flask import g
from flask_principal import UserNeed, ItemNeed
from sqlalchemy.orm.attributes import ScalarObjectAttributeImpl


class HybridNeed(object):
    """
    :class:`HybridNeed` base class. Hybrid needs can both be evaluated directly or produce an expression for use with
    SQLAlchemy.
    """
    def __call__(self, item):
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.__repr__())

    def make_expression(self, query):
        """
        :returns: SQLAlchemy expression for this Need
        """
        # TODO support inversion of HybridNeed objects for negative permissions.
        raise NotImplementedError()


class HybridItemNeed(HybridNeed):
    def __init__(self, method, resource, type_=None):
        self.method = method
        self.type = type_ or resource.meta.name
        self.resource = resource

    def _identity_get_item_needs(self):
        if self.method == 'id':
            prototype = ('id', None)
        else:
            prototype = (self.method, None, self.type)

        for need in g.identity.provides:
            if len(need) == len(prototype):
                if all(p is None or n == p for n, p in zip(need, prototype)):
                    yield need[1]

    def extend(self, field):
        return HybridRelationshipNeed(self.method, field)

    def __call__(self, item):
        if self.method == 'id':
            return UserNeed(self.resource.item_get_id(item))
        return ItemNeed(self.method, get_value(item, self.resource.meta.id_attribute, None), self.type)

    def __eq__(self, other):
        return isinstance(other, HybridItemNeed) and \
               self.method == other.method and \
               self.type == other.type and \
               self.resource == other.resource

    def make_expression(self):
        ids = list(self._identity_get_item_needs())

        if not ids:
            return None

        return self.resource.manager.id_column.in_(ids)

    def __hash__(self):
        return hash(self.__repr__())

    def __repr__(self):
        return "<HybridItemNeed method='{}' type='{}'>".format(self.method, self.type)


def get_value(item, attribute, default=None):
    if isinstance(item, dict):
        return item.get(attribute, default)
    else:
        return getattr(item, attribute, None)


class HybridRelationshipNeed(HybridItemNeed):
    """
    HybridNeed objects
    """

    def __init__(self, method, *fields):
        super(HybridRelationshipNeed, self).__init__(method,
                                                     fields[-1].resource,
                                                     fields[-1].target.meta.name)
        self.fields = fields
        self.final_field = self.fields[-1]

    def __call__(self, item):
        """

        """
        for field in self.fields:
            item = get_value(item, field.attribute)

            if item is None:
                if self.method == 'id':
                    return UserNeed(None)
                return ItemNeed(self.method, None, self.type)

        item_id = get_value(item, self.final_field.resource.meta.id_attribute, None)

        if self.method == 'id':
            return UserNeed(item_id)
        return ItemNeed(self.method, item_id, self.type)

    def __eq__(self, other):
        return isinstance(other, HybridItemNeed) and \
               self.method == other.method and \
               self.resource == other.resource and \
               self.fields == other.fields

    def extend(self, field):
        return HybridRelationshipNeed(self.method, field, *self.fields)

    def make_expression(self):
        ids = list(self._identity_get_item_needs())

        if not ids:
            return None

        reversed_fields = reversed(self.fields)

        target_field = next(reversed_fields)
        target_relationship = getattr(target_field.resource.manager.model, target_field.attribute)

        expression = target_relationship.has(target_field.target.manager.id_column.in_(ids))

        for field in reversed_fields:
            relationship = getattr(field.binding._model, field.attribute)

            if isinstance(relationship.impl, ScalarObjectAttributeImpl):
                expression = relationship.has(expression)
            else:
                expression = relationship.any(expression)

        return expression

    def __hash__(self):
        return hash((self.method, self.type, self.fields))

    def __repr__(self):
        return "<HybridRelationshipNeed method='{}' type='{}' {}>".format(self.method, self.type, self.fields)


class HybridUserNeed(HybridRelationshipNeed):
    def __init__(self, field):
        super(HybridUserNeed, self).__init__('id', field)

    def __repr__(self):
        return '<HybridUserNeed {} {}>'.format(self.type, self.fields)

