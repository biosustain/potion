import six
from sqlalchemy.orm.collections import InstrumentedList
from werkzeug.exceptions import Forbidden
from werkzeug.utils import cached_property
from flask_principal import Permission, RoleNeed

from flask_potion.manager import RelationalManager
from flask_potion.fields import ToOne
from flask_potion.instances import Pagination
from .permission import HybridPermission
from .needs import HybridItemNeed, HybridUserNeed

PERMISSION_DEFAULTS = (
    ('read', 'yes'),
    ('create', 'no'),
    ('update', 'create'),
    ('delete', 'update')
)

DEFAULT_METHODS = ('read', 'create', 'update', 'delete')

METHOD_ROUTE_RELATIONS = (
    ('read', ('read', 'instances')),
    ('create', ('create',)),
    ('update', ('update',)),
    ('delete', ('destroy',))
)

PERMISSION_DENIED_STRINGS = ('no', 'nobody', 'noone')
PERMISSION_GRANTED_STRINGS = ('yes', 'everybody', 'anybody', 'everyone', 'anyone')

class PrincipalMixin(object):
    def __init__(self, *args, **kwargs):
        super(PrincipalMixin, self).__init__(*args, **kwargs)
        raw_needs = dict(PERMISSION_DEFAULTS)
        raw_needs.update(self.resource.meta.get('permissions', {}))
        self._raw_needs = raw_needs

    @cached_property
    def _needs(self):
        needs_map = self._raw_needs.copy()
        methods = needs_map.keys()

        def convert(method, needs, map, path=()):
            options = set()

            if isinstance(needs, six.string_types):
                needs = [needs]
            if isinstance(needs, set):
                return needs

            for need in needs:
                if need in PERMISSION_DENIED_STRINGS:
                    options.add(Permission(('permission-denied',)))
                elif need in PERMISSION_GRANTED_STRINGS:
                    return {True}
                elif need in methods:
                    if need == method:
                        options.add(HybridItemNeed(method, self.resource))
                    elif need in path:
                        raise RuntimeError('Circular permissions in {} (path: {})'.format(self.resource, path))
                    else:
                        path += (method,)
                        options |= convert(need, map[need], map, path)

                elif ':' in need:
                    role, value = need.split(':')
                    field = self.resource.schema.fields[value]

                    if field.attribute is None:
                        field.attribute = value

                    # TODO implement this for ToMany as well as ToOne
                    if isinstance(field, ToOne):
                        target = field.target

                        if role == 'user':
                            options.add(HybridUserNeed(field))
                        elif role == 'role':
                            options.add(RoleNeed(value))
                        else:
                            for imported_need in target.manager._needs[role]:
                                if isinstance(imported_need, HybridItemNeed):
                                    imported_need = imported_need.extend(field)
                                options.add(imported_need)
                else:
                    options.add(RoleNeed(need))

            return options

        for method, needs in needs_map.items():
            converted_needs = convert(method, needs, needs_map)
            needs_map[method] = converted_needs

        # TODO exclude routes for impossible permissions

        return needs_map

    @cached_property
    def _permissions(self):
        permissions = {}

        for method, needs in self._needs.items():
            if True in needs:
                needs = set()
            permissions[method] = HybridPermission(*needs)

        return permissions

    def get_permissions_for_item(self, item):
        """
        Returns a dictionary of evaluated permissions for an item.
        :param item:
        :return: Dictionary in the form ``{operation: bool, ..}``
        """
        return {operation: permission.can(item) for operation, permission in self._permissions.items()}

    def can_create_item(self, item):
        """
        Looks up permissions on whether an item may be created.
        :param item:
        """
        permission = self._permissions['create']
        return permission.can(item)

    def can_update_item(self, item, changes=None):
        """
        Looks up permissions on whether an item may be updated.
        :param item:
        :param changes: dictionary of changes
        """
        permission = self._permissions['update']
        return permission.can(item)

    def can_delete_item(self, item):
        """
        Looks up permissions on whether an item may be deleted.
        :param item:
        """
        permission = self._permissions['delete']
        return permission.can(item)

    def _query_filter_read_permission(self, query):
        read_permission = self._permissions['read']
        return self._query_filter_permission(query, read_permission)

    def _query_filter_permission(self, query, permission):
        if permission.can():
            return query

        # filters must not be applied if not present:
        if not permission.hybrid_needs:
            return None

        expressions = []

        for need in permission.hybrid_needs:
            ids = list(need.identity_get_item_needs())

            if not ids:
                continue

            if len(need.fields) == 0:
                expression = self._expression_for_ids(ids)
            else:
                expression = need.fields[-1].target.manager._expression_for_ids(ids)

                for field in reversed(need.fields):
                    expression = field.resource.manager._expression_for_join(field.attribute, expression)

            expressions.append(expression)

        if not expressions:
            return None

        return self._query_filter(query, self._or_expression(expressions))

    def _query(self, **kwargs):
        query = super(PrincipalMixin, self)._query(**kwargs)

        read_permission = self._permissions['read']
        query = self._query_filter_permission(query, read_permission)

        if query is None:
            # abort with 403, but only if permissions for this resource are role-based.
            if all(need.method == 'role' for need in read_permission.needs):
                # abort(403, message='Permission denied: not allowed to access this resource')
                raise Forbidden()

        return query

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        query = getattr(item, attribute)

        if isinstance(query, InstrumentedList):
            if page and per_page:
                return Pagination.from_list(query, page, per_page)
            return query

        target_manager = target_resource.manager
        if isinstance(target_manager, PrincipalMixin):
            query = target_manager._query_filter_read_permission(query)

        if page and per_page:
            return target_manager._query_get_paginated_items(query, page, per_page)

        return target_manager._query_get_all(query)

    def create(self, properties, commit=True):
        if not self.can_create_item(properties):
            raise Forbidden()
        return super(PrincipalMixin, self).create(properties, commit)

    def update(self, item, changes, *args, **kwargs):
        if not self.can_update_item(item, changes):
            raise Forbidden()
        return super(PrincipalMixin, self).update(item, changes, *args, **kwargs)

    def delete(self, item):
        if not self.can_delete_item(item):
            raise Forbidden()
        return super(PrincipalMixin, self).delete(item)


def principals(manager):
    if not issubclass(manager, RelationalManager):
        raise RuntimeError("principals() only works with managers that inherit from RelationalManager")

    class PrincipalsManager(PrincipalMixin, manager):
        pass

    return PrincipalsManager
