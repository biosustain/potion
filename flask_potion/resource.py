from collections import OrderedDict
import inspect
from operator import attrgetter
import itertools
import six
from flask_potion import fields
from .reference import ResourceBound
from .instances import Instances
from .utils import AttributeDict
from .backends.alchemy import SQLAlchemyManager
from .routes import Route, DeferredSchema, RouteSet
from .schema import FieldSet


class ResourceMeta(type):
    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)
        class_.routes = routes = dict(getattr(class_, 'routes') or {})
        class_.meta = meta = AttributeDict(getattr(class_, 'meta', {}) or {})

        for base in bases:
            for n, m in inspect.getmembers(base, lambda m: isinstance(m, (Route, RouteSet))):
                if m.attribute is None:
                    m.attribute = n

                if isinstance(m, RouteSet):
                    for i, r in enumerate(m.routes()):
                        if r.attribute is None:
                            r.attribute = '{}_{}'.format(m.attribute, i)
                        routes[r.attribute] = r
                else:
                    routes[m.attribute] = m

            if hasattr(base, 'Meta'):
                meta.update(base.Meta.__dict__)


        if 'Meta' in members:
            changes = members['Meta'].__dict__
            for k, v in changes.items():
                if not k.startswith('__'):
                    meta[k] = v

            if not changes.get('name', None):
                meta['name'] = name.lower()

            # NKs: group by type -- e.g. string, integer, object, array -- while keeping order intact:
            # if 'natural_keys' in meta:
            #     meta['natural_keys_by_type'] = natural_keys_by_type = defaultdict(list)
            #     for nk in meta['natural_keys']:
            #         natural_keys_by_type[nk.matcher_type(class_)].append(nk)
        else:
            meta['name'] = name.lower()

        schema = {}
        for base in bases:
            if hasattr(base, 'Schema'):
                schema.update(base.Schema.__dict__)

        if 'Schema' in members:
            schema.update(members['Schema'].__dict__)

        if schema:
            # TODO support FieldSet with definitions
            class_.schema = fs = FieldSet({k: f for k, f in schema.items() if not k.startswith('__')},
                                          required_fields=meta.get('required_fields', None))

            for name in meta.get('read_only_fields', ()):
                if name in fs.fields:
                    fs.fields[name].io = "r"

            for name in meta.get('write_only_fields', ()):
                if name in fs.fields:
                    fs.fields[name].io = "w"

            fs.bind(class_)

        for n, m in members.items():
            if isinstance(m, Route):
                if m.attribute is None:
                    m.attribute = n

                routes[m.attribute] = m

            if isinstance(m, ResourceBound):
                m.bind(class_)

            if isinstance(m, RouteSet):
                if m.attribute is None:
                    m.attribute = n
                for i, r in enumerate(m.routes()):
                    if r.attribute is None:
                        r.attribute = '{}_{}'.format(m.attribute, i)
                    routes['{}_{}'.format(m.attribute, r.attribute)] = r
        return class_


class Resource(six.with_metaclass(ResourceMeta, object)):
    api = None
    meta = None
    routes = None
    schema = None
    route_prefix = None

    @Route.GET('/schema', rel="describedBy", attribute="schema")
    def described_by(self): # No "targetSchema" because that would be way too meta.
        schema = OrderedDict([
            ("$schema", "http://json-schema.org/draft-04/hyper-schema#"),
        ])

        # copy title, description from ModelResource.meta
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
        # get_item_url_keys = (
        #     RefResolver(),
        # )


class ModelResourceMeta(ResourceMeta):
    def __new__(mcs, name, bases, members):
        class_ = super(ModelResourceMeta, mcs).__new__(mcs, name, bases, members)

        if 'Meta' in members:
            meta = class_.meta
            changes = members['Meta'].__dict__

            if 'model' in changes or 'model' in meta and 'manager' in changes:
                fs = class_.schema

                if issubclass(meta.id_field_class, fields.ItemUri):
                    fs.set('$uri', meta.id_field_class(class_, attribute=meta.id_attribute))
                else:
                    fs.set('$id', meta.id_field_class(io="r", attribute=meta.id_attribute))
                class_.manager = meta.manager(class_, meta.model)

                if meta.include_type:
                    fs.set('$type', fields.ItemType(class_))

        return class_


class ModelResource(six.with_metaclass(ModelResourceMeta, Resource)):
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
        item = self.manager.create(properties)
        return item  # TODO consider 201 Created

    create.request_schema = create.response_schema = DeferredSchema(fields.Inline, 'self')

    @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter), rel="self", attribute="instance")
    def read(self, id):
        return self.manager.read(id)

    read.request_schema = None
    read.response_schema = DeferredSchema(fields.Inline, 'self')

    @read.PATCH(rel="update")
    def update(self, properties, id):
        item = self.manager.read(id)
        updated_item = self.manager.update(item, properties)
        return updated_item

    update.request_schema = DeferredSchema(fields.Inline, 'self', patch_instance=True)
    update.response_schema = update.request_schema

    @update.DELETE(rel="destroy")
    def destroy(self, id):
        self.manager.delete_by_id(id)
        return None, 204

    class Schema:
        pass

    class Meta:
        id_attribute = 'id'
        id_converter = 'int'
        id_field_class = fields.ItemUri  # Must inherit from Integer, String or ItemUri
        include_type = False
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
