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
    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)

        if 'Meta' in members:
            meta = class_.meta
            changes = members['Meta'].__dict__

            if 'model' in changes:
                fs = class_.schema
                fs.fields[meta.id_attribute] = meta.id_field_class(io="r", attribute=meta.id_attribute)
                class_.manager = meta.manager(class_, meta.model)
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
        return self.manager.paginated_instances(**kwargs)

    # TODO custom schema (Instances/Instances) that contains the necessary schema.
    instances.request_schema = instances.response_schema = DeferredSchema(Instances, 'self') # TODO NOTE Instances('self') for filter, etc. schema

    @instances.POST(rel="create")
    def create(self, properties):  # XXX need some way for field bindings to be dynamic/work dynamically.
        print('X',self.manager, properties)
        item = self.manager.create(properties)
        print('CREATED',item)
        return item

    create.request_schema = create.response_schema = DeferredSchema(fields.Inline, 'self')

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
        self.manager.delete_by_id(id)
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