import six
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden
from werkzeug.utils import cached_property
from flask_principal import Permission, RoleNeed
from flask_potion.resource import ModelResource
from flask_potion.fields import ToOne
from flask_potion.backends import Pagination
from flask_potion.exceptions import ItemNotFound
from flask_potion.backends.alchemy import SQLAlchemyManager
from .permission import HybridPermission
from .needs import HybridItemNeed, HybridUserNeed


PERMISSION_DEFAULTS = (
    ('read', 'yes'),
    ('create', 'no'),
    ('update', 'create'),
    ('delete', 'update')
)

DEFAULT_METHODS = ('read', 'create', 'update', 'delete')


class PrincipalManager(SQLAlchemyManager):

    def __init__(self, resource, model):
        super(PrincipalManager, self).__init__(resource, model)

        raw_needs = dict(PERMISSION_DEFAULTS)
        raw_needs.update(resource.meta.get('permissions', {}))
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
                if need in ('no', 'nobody', 'noone'):
                    options.add(Permission(('permission-denied',)))
                elif need in ('yes', 'everybody', 'anybody', 'everyone', 'anyone'):
                    return {True}
                elif need in methods:
                    if need == method:
                        options.add(HybridItemNeed(method, self.resource))
                    elif need in path:
                        raise RuntimeError('Circular permissions in {} (path: {})'.format(self.resource, path))
                    else:
                        path += (method, )
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

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        query = getattr(item, attribute)

        if isinstance(query, InstrumentedList):
            if page and per_page:
                return Pagination.from_list(query, page, per_page)
            return query

        if isinstance(target_resource.manager, PrincipalManager):
            read_permission = target_resource.manager._permissions['read']
            query = read_permission.apply_filters(query)

        if page and per_page:
            return query.paginate(page=page, per_page=per_page)
        return query.all()

    def paginated_instances(self, page, per_page, where=None, sort=None):
        instances = self.instances(where=where, sort=sort)
        if isinstance(instances, list):
            return Pagination.from_list(instances, page, per_page)
        return instances.paginate(page=page, per_page=per_page)

    def _query(self):
        read_permission = self._permissions['read']
        query = read_permission.apply_filters(self.model.query)

        if query is None:
            # abort with 403, but only if permissions for this resource are role-based.
            if all(need.method == 'role' for need in read_permission.needs):
                # abort(403, message='Permission denied: not allowed to access this resource')
                raise Forbidden()

        return query

    def instances(self, where=None, sort=None):
        """
        Applies permissions to query and returns query.

        :raises HTTPException: If read access is entirely forbidden.
        """
        query = self._query()

        if query is None:
            return []

        if where:
            query = query.filter(self._where_expression(where))
        if sort:
            query = query.order_by(*self._order_by(sort))
        return query

    def read(self, id):
        try:
            query = self._query()
            if query is None:
                raise ItemNotFound(self.resource, id=id)
            # NOTE SQLAlchemy's .get() does not work well with .filter(), therefore using .one()
            return query.filter(self.id_column == id).one()
        except NoResultFound:
            raise ItemNotFound(self.resource, id=id)

    def create(self, properties, commit=True):
        if not self.can_create_item(properties):
            raise Forbidden()
        return super(PrincipalManager, self).create(properties, commit)

    def update(self, item, changes, *args, **kwargs):
        if not self.can_update_item(item, changes):
            raise Forbidden()
        return super(PrincipalManager, self).update(item, changes, *args, **kwargs)

    def delete(self, item):
        if not self.can_delete_item(item):
            raise Forbidden()
        return super(PrincipalManager, self).delete(item)


class PrincipalResource(ModelResource):
    class Meta:
        manager = PrincipalManager