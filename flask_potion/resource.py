from collections import OrderedDict
import datetime
from operator import attrgetter
import itertools
from collections import defaultdict

import six
from sqlalchemy.dialects import postgres
from sqlalchemy.orm import class_mapper
import sqlalchemy.types as sa_types

from . import fields
from .instances import Instances
from .utils import AttributeDict
from .manager import SQLAlchemyManager
from .routes import Route, MethodRoute, DeferredSchema
from .schema import FieldSet


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

            if 'name' not in changes:
                meta['name'] = class_.__name__.lower()

            # NKs: group by type -- e.g. string, integer, object, array -- while keeping order intact:
            if 'natural_keys' in meta:
                meta['natural_keys_by_type'] = natural_keys_by_type = defaultdict(list)
                for nk in meta['natural_keys']:
                    natural_keys_by_type[nk.matcher_type(class_)].append(nk)

        if 'Schema' in members:
            schema = dict(members['Schema'].__dict__)

            # TODO support FieldSet with definitions
            class_.schema = fs = FieldSet({k: f for k, f in schema.items() if not k.startswith('__')},
                                          required_fields=meta.get('required_fields', None))

            for name in meta.get('read_only_fields', ()):
                if name in fs.fields:
                    fs.fields[name].io = "r"

            for name in meta.get('write_only_fields', ()):
                if name in fs.fields:
                    fs.fields[name].io = "w"

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
    def described_by(self): # No "targetSchema" because that would be way too meta.
        schema = OrderedDict([
            ("$schema", "http://json-schema.org/draft-04/hyper-schema#"),
        ])

        # copy title, description from Resource.meta
        for property in ('title', 'description'):
            value = getattr(self.meta, property)
            if value:
                schema[property] = value

        links = itertools.chain(*(route.links() for name, route in sorted(self.routes.items())))

        if self.schema:
            schema['type'] = "object"
            schema.update(self.schema.response)

        # TODO more intuitive sorting [self, instances,.. GET_bar, POST_bar, GET_foo, POST_foo, ..describedBy]
        schema['links'] = [link.schema_factory(self) for link in sorted(links, key=attrgetter('relation'))]

        return schema, 200, {'Content-Type': 'application/schema+json'}

    class Meta:
        name = None
        title = None
        description = None
        required_fields = None
        read_only_fields = ()
        write_only_fields = ()
        natural_keys = ()


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
                datetime.date: fields.DateString,
                datetime.datetime: fields.DateTimeString
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)

        if 'Meta' in members:
            meta = class_.meta
            changes = members['Meta'].__dict__

            if 'model' in meta:
                class_.manager = meta.manager(class_, meta.model)

                fs = class_.schema
                fs.fields[meta.id_attribute] = meta.id_field_class(io="r", attribute=meta.id_attribute)


            # TODO move this into manager maybe?
            # (pre-)populate schema with fields from model:
            if 'model' in changes and False:
                model = meta.model
                mapper = class_mapper(model)

                id_field = meta.get('id_field', mapper.primary_key[0].name)
                id_column = getattr(model, id_field)

                # resource name: use model table's name if not set explicitly
                if 'name' not in meta:
                    meta['name'] = model.__tablename__.lower()

                fs = class_.schema
                include_fields = meta.get('include_fields', None)
                exclude_fields = meta.get('exclude_fields', None)
                read_only_fields = meta.get('read_only_fields', ())
                write_only_fields = meta.get('write_only_fields', ())
                pre_declared_fields = {f.attribute or k for k, f in fs.schema.items()}

                for name, column in six.iteritems(dict(mapper.columns)):
                    if (include_fields and name in include_fields) or \
                            (exclude_fields and name not in exclude_fields) or \
                            not (include_fields or exclude_fields):

                        if column.primary_key or column.foreign_keys:
                            continue

                        if name in pre_declared_fields:
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

                        io = "rw"
                        if name in read_only_fields:
                            io = "r"
                        elif name in write_only_fields:
                            io = "w"

                        #
                        # if not (column.nullable or column.default):
                        #     meta["required_fields"].append(name)

                        fs.fields["name"] = field_class(*args, io=io, attribute=name, **kwargs)


            # TODO pre-populate Schema from `model` if present in 'meta'

        # TODO add id_field from meta to fieldset schema


        return class_


class Resource(six.with_metaclass(ResourceMeta, PotionResource)):
    manager = None

    @Route.GET('', rel="instances")
    def instances(self, **kwargs):
        """
        :param where:
        :param sort:
        :param int page:
        :param int per_page:
        :return:
        """
        print("INSTANCES", kwargs)

        # TODO link headers for next/previous/last page. Pagination object.
        return self.manager.paginated_instances(**kwargs)

        # TODO links must contain filters & sort
        # links = [(request.path, item_list.page, item_list.per_page, 'self')]
        #
        # if item_list.has_prev:
        #     links.append((request.path, 1, item_list.per_page, 'first'))
        #     links.append((request.path, item_list.page - 1, item_list.per_page, 'prev'))
        # if item_list.has_next:
        #     links.append((request.path, item_list.pages, item_list.per_page, 'last'))
        #     links.append((request.path, item_list.page + 1, item_list.per_page, 'next'))
        #
        # headers = {'Link': ','.join((LINK_HEADER_FORMAT_STR.format(*link) for link in links))}
        # return super(ModelResource, cls).marshal_item_list(item_list.items), 200, headers

        LINK_HEADER_FORMAT_STR = '<{0}?page={1}&per_page={2}>; rel="{3}"'

        return pagination.items


    # TODO custom schema (Instances/Instances) that contains the necessary schema.
    instances.request_schema = DeferredSchema(Instances, 'self') # TODO NOTE Instances('self') for filter, etc. schema
    instances.response_schema = DeferredSchema(Instances, 'self')

    @instances.POST(rel="create")
    def create(self, properties):  # XXX need some way for field bindings to be dynamic/work dynamically.
        print('X',self.manager, properties)
        item = self.manager.create(properties)
        print('CREATED',item)
        return item

    create.request_schema = DeferredSchema(fields.Inline, 'self')
    create.response_schema = DeferredSchema(fields.Inline, 'self')

    @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter), rel="self")
    def read(self, id):
        return self.manager.read(id)

    read.request_schema = None
    read.response_schema = DeferredSchema(fields.Inline, 'self')

    @read.PATCH(rel="update")
    def update(self, properties, id):
        item = self.manager.read(id)
        updated_item = self.manager.update(item, properties)
        return updated_item

    update.request_schema = DeferredSchema(fields.Inline, 'self')
    update.response_schema = DeferredSchema(fields.Inline, 'self')

    @update.DELETE(rel="destroy")
    def destroy(self, id):
        self.manager.delete(id)
        return None, 204

    class Schema:
        pass

    class Meta:
        id_attribute = 'id'
        id_converter = 'int'
        id_field_class = fields.PositiveInteger  # Must inherit from Integer or String
        manager = SQLAlchemyManager
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