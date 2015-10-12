from __future__ import absolute_import

from bson import ObjectId as bson_ObjectId
from flask import current_app
from mongoengine.errors import OperationError, ValidationError
from bson.errors import InvalidId

import mongoengine.fields as mongo_fields

from flask_potion.utils import get_value
from flask_potion.exceptions import ItemNotFound, BackendConflict
from flask_potion.backends import Manager, Pagination
from flask_potion.signals import before_create, before_update, after_update, before_delete, after_delete, after_create, \
    before_add_to_relation, after_remove_from_relation, before_remove_from_relation, after_add_to_relation
from flask_potion import fields


# TODO: more elaborate field that validates and returns ObjectId

class custom_fields:
    class ObjectId(fields.String):
        def formatter(self, value):
            if isinstance(value, bson_ObjectId):
                return str(value)
            else:
                return value


MONGO_REFERENCE_FIELD_TYPES = (
    mongo_fields.ReferenceField,
    mongo_fields.CachedReferenceField,
    mongo_fields.ObjectIdField
)


COMPARATOR_EXPRESSIONS = {
    '$eq': lambda column, value: {column: value},
    '$ne': lambda column, value: {"%s__ne" % column: value},
    '$in': lambda column, value: {"%s__in" % column: value},
    '$lt': lambda column, value: {"%s__lt" % column: value},
    '$gt': lambda column, value: {"%s__gt" % column: value},
    '$lte': lambda column, value: {"%s__lte" % column: value},
    '$gte': lambda column, value: {"%s__gte" % column: value},
    '$contains': lambda column, value: {"%s__contains" % column: value},
    '$startswith': lambda column, value: {"%s__startswith" % column: value.replace('%', '\\%')},
    '$endswith': lambda column, value: {"%s__endswith" % column: value.replace('%', '\\%')},
    # TODO: $istartswith and $iendswith filters
}

MONGO_FIELDS_MAPPING = {
    mongo_fields.ReferenceField: fields.Object,
    mongo_fields.ObjectIdField: custom_fields.ObjectId,
    mongo_fields.IntField: fields.Integer,
    mongo_fields.FloatField: fields.Number,
    mongo_fields.BooleanField: fields.Boolean,
    mongo_fields.ListField: fields.Array,
    mongo_fields.SortedListField: fields.Array,
    mongo_fields.LongField: fields.Number,
    mongo_fields.BinaryField: fields.Array,
    mongo_fields.DictField: fields.Object,
    mongo_fields.DateTimeField: fields.Date,
    mongo_fields.ComplexDateTimeField: fields.DateTime
}


class MongoEngineManager(Manager):
    """
    A manager for MongoEngineManager models.

    Expects that :class:`Meta.model` contains an MongoEngine declarative model.

    """
    supported_comparators = tuple(COMPARATOR_EXPRESSIONS.keys())

    def __init__(self, resource, model):
        super(MongoEngineManager, self).__init__(resource, model)
        meta = resource.meta

        self.id_attribute = meta.id_attribute
        self.id_column = model._fields[self.id_attribute]

        if resource.meta.include_id:
            resource.schema.set("$id", custom_fields.ObjectId(io='r', attribute=self.id_attribute))

        # resource name: use model table's name if not set explicitly
        if not hasattr(resource.Meta, 'name'):
            meta['name'] = model._meta.get('collection', model.__class__.__name__).lower()

        fs = resource.schema
        include_fields = meta.get('include_fields', None)
        exclude_fields = meta.get('exclude_fields', None)
        read_only_fields = meta.get('read_only_fields', ())
        write_only_fields = meta.get('write_only_fields', ())
        pre_declared_fields = {f.attribute or k for k, f in fs.fields.items()}

        for name, column in model._fields.items():
            if (include_fields and name in include_fields) or \
                    (exclude_fields and name not in exclude_fields) or \
                    not (include_fields or exclude_fields):

                if column.primary_key:
                    continue
                if name in pre_declared_fields:
                    continue
                if isinstance(column, MONGO_REFERENCE_FIELD_TYPES):
                    continue
                if isinstance(column, mongo_fields.ListField) and isinstance(column.field, MONGO_REFERENCE_FIELD_TYPES):
                    continue

                field_class, args, kwargs = self._get_field_from_mongoengine_type(column)

                io = "rw"
                if name in read_only_fields:
                    io = "r"
                elif name in write_only_fields:
                    io = "w"

                if not (column.null or column.default is not None):
                    fs.required.add(name)

                fs.set(name, field_class(*args, io=io, attribute=name, **kwargs))

    def _init_key_converters(self, resource, meta):
        meta.id_attribute = meta.get('id_attribute', meta.model.pk)
        meta.id_field_class = custom_fields.ObjectId
        meta.id_converter = 'string'
        super(MongoEngineManager, self)._init_key_converters(resource, meta)

    def _get_field_from_mongoengine_type(self, property):
        args = ()
        kwargs = {}

        if isinstance(property, mongo_fields.ListField):
            field_class = fields.Array
            args = (self._get_field_from_mongoengine_type(property.field)[0],)
        elif isinstance(property, mongo_fields.UUIDField):  # TODO support UUIDfield
            field_class = fields.String
            kwargs = {
                'max_length': 36,
                'min_length': 36,
            }
        elif isinstance(property, mongo_fields.StringField):
            field_class = fields.String
            kwargs = {
                'max_length': property.max_length,
                'min_length': property.min_length,
                'enum': property.choices,
                'pattern': property.regex
            }
        else:
            try:
                field_class = MONGO_FIELDS_MAPPING[type(property)]
            except KeyError:
                raise TypeError("%s not supported (use %s)" % (type(property), str(list(MONGO_FIELDS_MAPPING.keys()))))

        kwargs['nullable'] = property.null
        kwargs['default'] = property.default
        return field_class, args, kwargs

    def _where_expression(self, where):
        expressions = {}

        for condition in where:
            expressions.update(COMPARATOR_EXPRESSIONS[condition.comparator.name](condition.attribute, condition.value))

        return expressions

    @staticmethod
    def _order_by(sort):
        for attribute, reverse in sort:
            if reverse:
                yield "-%s" % attribute
            else:
                yield "%s" % attribute

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        query = getattr(item, attribute)
        if page and per_page:
            return Pagination.from_list(query, page, per_page)
        else:
            return query.all()

    def relation_add(self, item, attribute, target_resource, target_item):
        before_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        getattr(item, attribute).append(target_item)
        item.save()
        after_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def relation_remove(self, item, attribute, target_resource, target_item):
        before_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        getattr(item, attribute).remove(target_item)
        item.save()
        after_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        instances = self.instances(where=where, sort=sort)
        return Pagination(instances, page, per_page, instances.count())

    def instances(self, where=None, sort=None):
        query = self.model.objects

        if where is not None:
            where_expression = self._where_expression(where)
            query = query(**where_expression)

        if sort is not None:
            query = query.order_by(*self._order_by(sort))

        return query

    def first(self, where=None, sort=None):
        res = self.instances(where, sort).first()
        if res is None:
            raise ItemNotFound(self.resource, where=where)
        else:
            return res

    def create(self, properties, commit=True):
        item = self.model()

        for key, value in properties.items():
            setattr(item, key, value)

        before_create.send(self.resource, item=item)

        try:
            item.save()
        except OperationError as e:
            if current_app.debug:
                raise BackendConflict(debug_info=dict(statement=e.args))
            raise BackendConflict()

        after_create.send(self.resource, item=item)
        return item

    def read(self, id):
        try:
            return self.model.objects(**{self.id_attribute: id}).first()
        except (InvalidId, ValidationError):
            raise ItemNotFound(self.resource, id=id)

    def update(self, item, changes, commit=True):
        actual_changes = {
            key: value for key, value in changes.items()
            if get_value(key, item, None) != value
        }

        try:
            before_update.send(self.resource, item=item, changes=actual_changes)

            for key, value in changes.items():
                setattr(item, key, value)

            if commit:
                item.save()
        except OperationError:
            raise

        after_update.send(self.resource, item=item, changes=actual_changes)
        return item

    def delete(self, item):
        before_delete.send(self.resource, item=item)
        item.delete()
        after_delete.send(self.resource, item=item)
