from collections import OrderedDict
import inspect
from operator import attrgetter
import itertools

import six

from .natural_keys import RefKey, IDKey, PropertyKey, PropertiesKey
from .fields import ItemType, ItemUri, Integer, Inline
from .reference import ResourceBound
from .instances import Instances
from .utils import AttributeDict
from .backends.alchemy import SQLAlchemyManager
from .routes import Route
from .schema import FieldSet


class ResourceMeta(type):
    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)
        class_.routes = routes = dict(getattr(class_, 'routes') or {})
        class_.meta = meta = AttributeDict(getattr(class_, 'meta', {}) or {})

        for base in bases:
            for n, m in inspect.getmembers(base, lambda m: isinstance(m, Route)):
                if m.attribute is None:
                    m.attribute = n
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

        return class_


class Resource(six.with_metaclass(ResourceMeta, object)):
    """
    A plain resource with nothing but a schema.


    .. attribute:: api

        Back reference to the :class:`Api` this resource is registered on.

    .. attribute:: meta

        A :class:`AttributeDict` of configuration attributes collected from the :class:`Meta` attributes of the base classes.

    .. attribute:: routes

        A dictionary of routes registered with this resource. Keyed by ``Route.attribute``.

    .. attribute:: schema

        A :class:`FieldSet` containing fields collected from the :class:`Schema` attributes of the base classes.

    .. attribute:: route_prefix

        The prefix URI to any route in this resource; includes the API prefix.

    .. method:: described_by

        A :class:`Route` at ``/schema`` that contains the JSON Hyper-Schema for this resource.

    """
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


class ModelResourceMeta(ResourceMeta):
    def __new__(mcs, name, bases, members):
        class_ = super(ModelResourceMeta, mcs).__new__(mcs, name, bases, members)

        if 'Meta' in members:
            meta = class_.meta
            changes = members['Meta'].__dict__

            if 'model' in changes or 'model' in meta and 'manager' in changes:
                fs = class_.schema

                if meta.include_id:
                    fs.set('$id', meta.id_field_class(io="r", attribute=meta.id_attribute))
                else:
                    fs.set('$uri', ItemUri(class_, attribute=meta.id_attribute))

                class_.manager = meta.manager(class_, meta.model)

                if meta.include_type:
                    fs.set('$type', ItemType(class_))

            if 'natural_key' in meta:
                if isinstance(meta.natural_key, str):
                    meta['key_converters'] += (PropertyKey(meta.natural_key),)
                elif isinstance(meta.natural_key, (list, tuple)):
                    meta['key_converters'] += (PropertiesKey(*meta.natural_key),)

            if 'key_converters' in meta:
                meta.key_converters = [k.bind(class_) for k in meta['key_converters']]
                meta.key_converters_by_type = {}
                for nk in meta.key_converters:
                    if nk.matcher_type() in meta.key_converters_by_type:
                        raise RuntimeError(
                            'Multiple keys of type {} defined for {}'.format(nk.matcher_key(), meta.name))
                    meta.key_converters_by_type[nk.matcher_type()] = nk
        return class_


class ModelResource(six.with_metaclass(ModelResourceMeta, Resource)):
    """

    .. method:: create

        A link --- part of a :class:`Route` at the root of the resource --- for creating new items.

        :param properties:
        :return: created item

    .. method:: instances

        A link --- part of a :class:`Route` at the root of the resource --- for reading item instances.

        :param where:
        :param sort:
        :param int page:
        :param int per_page:
        :return: list of items

    .. method:: read

        A link --- part of a :class:`Route` at ``/<{Resource.meta.id_converter}:id>`` --- for reading a specific item.

        :param id: item id
        :return: item

    .. method:: update

        A link --- part of a :class:`Route` at ``/<{Resource.meta.id_converter}:id>`` --- for updating a specific item.

        :param id: item id
        :param properties: changes
        :return: item

    .. method:: destroy

        A link --- part of a :class:`Route` at ``/<{Resource.meta.id_converter}:id>`` --- for deleting a specific item.

        :param id: item id
        :return: ``(None, 204)``

    """
    manager = None

    @Route.GET('', rel="instances")
    def instances(self, **kwargs):
        return self.manager.paginated_instances(**kwargs)

    # TODO custom schema (Instances/Instances) that contains the necessary schema.
    instances.request_schema = instances.response_schema = Instances() # TODO NOTE Instances('self') for filter, etc. schema


    @instances.POST(rel="create")
    def create(self, properties):  # XXX need some way for field bindings to be dynamic/work dynamically.
        item = self.manager.create(properties)
        return item  # TODO consider 201 Created

    create.request_schema = create.response_schema = Inline('self')

    @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter), rel="self", attribute="instance")
    def read(self, id):
        return self.manager.read(id)

    read.request_schema = None
    read.response_schema = Inline('self')

    @read.PATCH(rel="update")
    def update(self, properties, id):
        item = self.manager.read(id)
        updated_item = self.manager.update(item, properties)
        return updated_item

    update.request_schema = Inline('self', patchable=True)
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
        id_field_class = Integer  # Must inherit from Integer, String or ItemUri
        include_id = False
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
        key_converters = (
            RefKey(),
            IDKey()
        )
        natural_key = None