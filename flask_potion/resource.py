from collections import namedtuple, OrderedDict
import json
import datetime

from flask import url_for, request
from flask.views import MethodViewType
import itertools
import six

from . import fields
from sqlalchemy.dialects import postgres
from sqlalchemy.orm import class_mapper
import sqlalchemy.types as sa_types
from flask.ext.potion.util import AttributeDict
from .manager import Manager
from .routes import route, Route, MethodRoute, DeferredSchema
from .schema import Schema, FieldSet
from .filter import Filter, Sort
from collections import defaultdict


class Set(Schema):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """

    def __init__(self, resource, default_sort=None):
        pass

    def get(self, items, where=None, sort=None, page=None, per_page=None):
        """

        :param items: SQLAlchemy Query object
        :param where:
        :param sort:
        :param page:
        :param per_page:
        :return:
        """
        #
        # TODO make work with non
        #

        items = self._filter_where(items, where)
        items = self._sort_by(items, sort)
        items = self._paginate(items, page, per_page)


        return items, 200, {
            "Link": ','.join(str(link) for link in (
                Link(self.resource.schema.uri, rel="describedBy"),
            ))
        }

    def put(self, item, child):
        raise NotImplementedError()

    def delete(self, item, child):
        raise NotImplementedError()


class PotionMeta(type):
    def __new__(mcs, name, bases, members):
        class_ = super(PotionMeta, mcs).__new__(mcs, name, bases, members)
        class_.routes = routes = dict(getattr(class_, 'routes') or {})
        class_.meta = meta = AttributeDict(getattr(class_, 'meta', {}) or {})

        if 'Meta' in members:
            changes = members['Meta'].__dict__
            for k, v in changes.items():
                if not k.startswith('__'):
                    meta[k] = v

            if not changes.get('name'):
                meta['name'] = class_.__name__.lower()

        for name, m in members.items():
            if isinstance(m, (Route, MethodRoute)):
                m.binding = class_

                if m.attribute is None:
                    m.attribute = name

                routes[m.attribute] = m

        return class_


class PotionResource(six.with_metaclass(PotionMeta, object)):
    meta = None
    routes = None
    schema = None

    @Route.GET('/schema', rel="describedBy", attribute="schema")
    def schema_route(self): # No "targetSchema" because that would be way too meta.
        schema = OrderedDict([
            ("$schema", "http://json-schema.org/draft-04/hyper-schema#")
        ])

        # copy title, description from Resource.meta
        for property in ('title', 'description'):
            value = getattr(self.meta, property)
            if value:
                schema[property] = value

        links = itertools.chain(*(route.links() for name, route in sorted(self.routes.items())))

        if self.schema:
            schema['type'] = "object"
            schema.update(self.schema.response_schema)
        schema['links'] = [link.schema_factory(self) for link in links]

        return schema, 200, {'Content-Type': 'application/schema+json'}

    class Schema:
        pass

    class Meta:
        name = None
        title = None
        description = None


class ResourceMeta(PotionMeta):

    @staticmethod
    def _get_field_from_python_type(python_type):
        try:
            return {
                str: fields.String,
                six.text_type: fields.String,
                int: fields.Integer,
                float: fields.Number,
                bool: fields.Boolean,
                list: fields.Array,
                dict: fields.KeyValue,
                datetime.date: fields.Date,
                datetime.datetime: fields.DateTime
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)
        class_.meta = meta = dict(getattr(class_, 'meta', {}))
        class_.routes = routes = dict(getattr(class_, 'routes', {}))

        if 'Schema' in members:
            schema = dict(members['Schema'].__dict__)
        else:
            schema = {}

        if 'Meta' in members:
            changes = members['Meta'].__dict__
            meta.update(changes)

            # (pre-)populate schema with fields from model:
            if 'model' in changes:
                model = changes['model']
                mapper = class_mapper(model)

                id_field = meta.get('id_field', mapper.primary_key[0].name)
                id_column = getattr(model, id_field)

                # resource name: use model table's name if not set explicitly
                if 'name' not in meta:
                    meta['name'] = model.__tablename__.lower()

                include_fields = meta.get('include_fields', None)
                exclude_fields = meta.get('exclude_fields', None)
                explicit_fields = {f.attribute or k for k, f in schema.items()}

                for name, column in six.iteritems(dict(mapper.columns)):
                    if (include_fields and name in include_fields) or \
                            (exclude_fields and name not in exclude_fields) or \
                            not (include_fields or exclude_fields):

                        if column.primary_key or column.foreign_keys:
                            continue

                        if name in explicit_fields:
                            continue

                        args = ()
                        kwargs = {}

                        if isinstance(column.type, postgres.ARRAY):
                            field_class = fields.Array
                            args = (fields.String,)
                        elif isinstance(column.type, sa_types.String) and column.type.length:
                            field_class = fields.String
                            kwargs = {'max_length': column.type.length}
                        elif isinstance(column.type, postgres.HSTORE):
                            field_class = fields.KeyValue
                            args = (fields.String,)
                        elif hasattr(postgres, 'JSON') and isinstance(column.type, postgres.JSON):
                            field_class = fields.Raw
                            kwargs = {"schema": {}}
                        else:
                            field_class = mcs._get_field_from_python_type(column.type.python_type)

                        kwargs['nullable'] = column.nullable

                        if column.default is not None and column.default.is_scalar:
                            kwargs['default'] = column.default.arg
                        #
                        # if not (column.nullable or column.default):
                        #     meta["required_fields"].append(name)
                        schema[name] = field_class(*args, attribute=name, **kwargs)


            # TODO pre-populate Schema from `model` if present in 'meta'

        # create fieldset schema
        # add id_field from meta to fieldset schema

        if schema:
            class_.schema = FieldSet({k: f for k, f in schema.items() if not k.startswith('__')},
                                     required_fields=meta.get('required_fields', None),
                                     read_only_fields=meta.get('read_only_fields', None))

        # NKs: group by type -- e.g. string, integer, object, array -- while keeping order intact:
        if hasattr(meta, 'natural_keys'):
            meta['natural_keys_by_type'] = natural_keys_by_type = defaultdict(list)
            for nk in meta['natural_keys']:
                natural_keys_by_type[nk.matcher_type(class_)].append(nk)

        return class_


class Resource(six.with_metaclass(ResourceMeta, PotionResource)):
#    items = Manager(None, None)
    meta = None
    routes = None
    schema = None

    @classmethod
    def get_item_id(cls, item):
        return getattr(item, cls.meta['id_attribute'])

    @classmethod
    def get_item_url(cls, item):
        return url_for(cls.read.endpoint, id=cls.get_item_id(item.id))

    # XXX move somewhere better if possible
    @classmethod
    def get_item_from_id(cls, id):
        pass

    @classmethod
    def get_items_query(cls):
        pass

    @route.GET('/', rel="instances")
    def instances(self, where, sort):
        where = None
        sort = None

        try:
            if "where" in request.args:
                where = json.loads(request.args["where"])
        except:
            abort(400, message='Bad filter: Must be valid JSON object')
            # FIXME XXX proper aborts & error messages

        self.items.get(self.items.index().all())

    instances.schema = DeferredSchema(FieldSet, {
        'where': DeferredSchema(Filter, 'self'),
        'sort':  DeferredSchema(Sort, 'self'),
    })# TODO NOTE Set('self') for filter, etc. schema
    instances.response_schema = DeferredSchema(Set, 'self')

    @instances.POST(rel="create")
    def create(self, item_or_items):  # XXX need some way for field bindings to be dynamic/work dynamically.
        pass # TODO handle integrity errors

    create.schema = DeferredSchema(fields.Inline, 'self')
    create.response_schema = DeferredSchema(fields.Inline, 'self')

    @route.GET(lambda r: '/<id:{}>'.format(r.meta.id_converter), rel="self")
    def read(self, id):
        pass

    read.schema = None
    read.response_schema = DeferredSchema(fields.Inline, 'self')

    @read.PATCH(rel="update")
    def update(self, id, object_):
        pass

    update.schema = DeferredSchema(fields.Inline, 'self')
    update.response_schema = DeferredSchema(fields.Inline, 'self')

    @update.DELETE(rel="destroy")
    def destroy(self, id):
        pass

    class Schema:
        pass

    class Meta:
        id_attribute = 'id'
        id_converter = 'int'
        id_field = fields.PositiveInteger()  # Must inherit from Integer or String
        include_fields = None
        exclude_fields = None
        allowed_filters = "*"
        permissions = {
            "read": "anyone",  # anybody, yes
            "create": "nobody",  # noone, no
            "update": "create",
            "delete": "update"
        }
        postgres_text_search_fields = ()
        postgres_full_text_index = None  # $fulltext
        read_only_fields = ()
        write_only_fields = ()
        natural_keys = ()
        cache = False


# class StrainResource(Resource):
#
#     class Meta:
#         natural_keys = (
#
#         )
#         natural_keys_by_type = {
#             'int': [resolvers.IDResolver()],
#             'string': [],
#             'object': [],
#             'array': []
#         }