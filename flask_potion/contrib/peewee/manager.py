from __future__ import absolute_import
from flask import current_app
import peewee as pw

try:
    from playhouse import postgres_ext
except ImportError:
    postgres_ext = False

from flask_potion import fields, signals
from flask_potion.instances import Pagination
from flask_potion.contrib.peewee.filters import FILTER_NAMES, FILTERS_BY_TYPE, PeeweeBaseFilter
from flask_potion.exceptions import ItemNotFound, BackendConflict
from flask_potion.manager import Manager
from flask_potion.utils import get_value


class PeeweeManager(Manager):
    """
    A manager for Peewee models.
    """
    FILTER_NAMES = FILTER_NAMES
    FILTERS_BY_TYPE = FILTERS_BY_TYPE

    def __init__(self, resource, model):
        super(PeeweeManager, self).__init__(resource, model)

    def _init_model(self, resource, model, meta):
        super(PeeweeManager, self)._init_model(resource, model, meta)
        self.model = model

        if meta.id_attribute:
            self.id_attribute = meta.id_attribute
            self.id_column = model._meta.fields[meta.id_attribute]
        else:
            self.id_attribute = model._meta.primary_key.name
            self.id_column = model._meta.primary_key

        self.id_field = meta.id_field_class(attribute=self.id_attribute, io="r")

        if not hasattr(resource.Meta, 'name'):
            meta['name'] = model._meta.db_table.lower()

        fs = resource.schema
        if meta.include_id:
            fs.set('$id', self.id_field)
        else:
            fs.set('$uri', fields.ItemUri(resource, attribute=self.id_attribute))

        if meta.include_type:
            fs.set('$type', fields.ItemType(resource))

        include_fields = meta.get('include_fields', None)
        exclude_fields = meta.get('exclude_fields', None)
        read_only_fields = meta.get('read_only_fields', ())
        write_only_fields = meta.get('write_only_fields', ())
        pre_declared_fields = {f.attribute or k for k, f in fs.fields.items()}

        for name, column in model._meta.fields.items():
            if (include_fields and name in include_fields) or \
                    (exclude_fields and name not in exclude_fields) or \
                    not (include_fields or exclude_fields):
                if column.primary_key or name in model._meta.rel:
                    continue
                if name in pre_declared_fields:
                    continue

                args = ()
                kwargs = {}

                if isinstance(column, (pw.CharField, pw.TextField)):
                    field_class = fields.String
                    if hasattr(column, 'max_length') and column.max_length:
                        kwargs['max_length'] = column.max_length
                elif isinstance(column, pw.IntegerField):
                    field_class = fields.Integer
                elif isinstance(column, (pw.DecimalField, pw.FloatField)):
                    field_class = fields.Number
                elif isinstance(column, pw.BooleanField):
                    field_class = fields.Boolean
                elif isinstance(column, pw.DateField):
                    field_class = fields.Date
                elif isinstance(column, pw.DateTimeField):
                    field_class = fields.DateTime
                elif isinstance(column, pw.BlobField):
                    field_class = fields.raw
                elif isinstance(column, postgres_ext.ArrayField):
                    field_class = fields.Array
                    args = (fields.String,)
                elif postgres_ext and \
                        isinstance(column, postgres_ext.HStoreField):
                    field_class = fields.Object
                    args = (fields.String,)
                elif postgres_ext and \
                        isinstance(column, (postgres_ext.JSONField,
                                            postgres_ext.BinaryJSONField)):
                    field_class = fields.Raw
                    kwargs = {"schema": {}}
                else:
                    field_class = fields.String

                kwargs['nullable'] = column.null

                if column.default is not None:
                    kwargs['default'] = column.default

                io = "rw"
                if name in read_only_fields:
                    io = "r"
                elif name in write_only_fields:
                    io = "w"

                if not (column.null or column.default):
                    fs.required.add(name)

                fs.set(
                    name, field_class(*args, io=io, attribute=name, **kwargs))

    def _init_filter(self, filter_class, name, field, attribute):
        return filter_class(name,
                            field=field,
                            attribute=field.attribute or attribute,
                            column=getattr(self.model, field.attribute or attribute))

    def _query(self):
        return self.model.select()

    def _order_by(self, sort):
        for field, attribute, reverse in sort:
            column = getattr(self.model, attribute)

            if reverse:
                yield column.desc()
            else:
                yield column.asc()

    def relation_instances(self, item, attribute, target_resource, page=None,
                           per_page=None):
        query = getattr(item, attribute)
        if page and per_page:
            # TODO see if this can be better done in one query
            return Pagination(query.paginate(page, per_page), page, per_page, query.count())
        return query

    def relation_add(self, item, attribute, target_resource, target_item):
        signals.before_add_to_relation.send(
            self.resource, item=item, attribute=attribute, child=target_item)

        relation = getattr(item, attribute)
        if hasattr(relation, 'add'):
            relation.add(target_item)
        else:
            reverse_attribute = item._meta.reverse_rel[attribute].name
            setattr(target_item, reverse_attribute, item)
            target_item.save()

        signals.after_add_to_relation.send(
            self.resource, item=item, attribute=attribute, child=target_item)

    def relation_remove(self, item, attribute, target_resource, target_item):
        signals.before_remove_from_relation.send(
            self.resource, item=item, attribute=attribute, child=target_item)

        relation = getattr(item, attribute)
        if hasattr(relation, 'remove'):
            relation.remove(target_item)
        else:
            reverse_atribute = item._meta.reverse_rel[attribute].name
            setattr(target_item, reverse_atribute, None)
            target_item.save()

        signals.after_remove_from_relation.send(
            self.resource, item=item, attribute=attribute, child=target_item)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        query = self.instances(where, sort)
        # TODO see if this can be better done in one query
        return Pagination(query.paginate(page, per_page), page, per_page, query.count())

    def instances(self, where=None, sort=None):
        query = self._query()

        if where:
            query = PeeweeBaseFilter.apply(query, where)
        if sort:
            query = query.order_by(*self._order_by(sort))

        return query

    def first(self, where=None, sort=None):
        try:
            return self.instances(where, sort).first()
        except self.model.DoesNotExist:
            raise ItemNotFound(self.resource, where=where)

    def create(self, properties, commit=True):
        item = self.model()

        for key, value in properties.items():
            setattr(item, key, value)

        signals.before_create.send(
            self.resource, item=item)

        try:
            item.save()
        except pw.IntegrityError as e:
            if current_app.debug:
                raise BackendConflict(debug_info=e.args)
            raise BackendConflict()

        signals.after_create.send(self.resource, item=item)
        return item

    def read(self, id):
        try:
            return self.model.get(self.id_column == id)
        except self.model.DoesNotExist:
            raise ItemNotFound(self.resource, id=id)

    def update(self, item, changes, commit=True):
        actual_changes = {
            key: value for key, value in changes.items()
            if get_value(key, item, None) != value
            }

        signals.before_update.send(
            self.resource, item=item, changes=actual_changes)

        for key, value in changes.items():
            setattr(item, key, value)

        try:
            item.save()
        except pw.IntegrityError as e:
            if current_app.debug:
                raise BackendConflict(debug_info=e.args)
            raise BackendConflict()

        signals.after_update.send(
            self.resource, item=item, changes=actual_changes)
        return item

    def delete(self, item):
        signals.before_delete.send(
            self.resource, item=item)

        item.delete_instance()

        signals.after_delete.send(
            self.resource, item=item)