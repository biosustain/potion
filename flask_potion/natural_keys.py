import re

import six
from werkzeug.utils import cached_property
from .filters import Condition

from .schema import Schema
from .reference import ResourceBound
from .exceptions import ItemNotFound
from .utils import route_from, get_value


class Key(Schema, ResourceBound):

    def matcher_type(self):
        type_ = self.response['type']
        if isinstance(type_, six.string_types):
            return type_
        return type_[0]

    def rebind(self, resource):
        return self.__class__().bind(resource=resource)

    def schema(self):
        raise NotImplementedError()


class RefKey(Key):

    def matcher_type(self):
        return 'object'

    def schema(self):
        return {
            "type": "object",
            "properties": {
                "$ref": {
                    "type": "string",
                    "format": "uri",
                    "pattern": "^{}\/[^/]+$".format(re.escape(self.resource.route_prefix))
                }
                # TODO consider replacing with {$type: foo, $value: 123}
            },
            "additionalProperties": False
        }

    def _item_uri(self, resource, item):
        # return url_for('{}.instance'.format(self.resource.meta.id_attribute, item, None), get_value(self.resource.meta.id_attribute, item, None))
        return '{}/{}'.format(resource.route_prefix, get_value(resource.manager.id_attribute, item, None))

    def format(self, item):
        return {"$ref": self._item_uri(self.resource, item)}

    def convert(self, value):
        try:
            endpoint, args = route_from(value["$ref"], 'GET')
        except Exception as e:
            raise e
        # XXX verify endpoint is correct (it should be)
        # assert resource.endpoint == endpoint
        return self.resource.manager.read(args['id'])


class PropertyKey(Key):

    def __init__(self, property):
        self.property = property

    def rebind(self, resource):
        return self.__class__(self.property).bind(resource)

    def schema(self):
        return self.resource.schema.fields[self.property].request

    def format(self, item):
        return self.resource.schema.fields[self.property].output(self.property, item)

    @cached_property
    def _field_filter(self):
        return self.resource.manager.filters[self.property][None]

    def convert(self, value):
        return self.resource.manager.first(where=[Condition(self.property, self._field_filter, value)])


class PropertiesKey(Key):

    def __init__(self, *properties):
        self.properties = properties

    def matcher_type(self):
        return 'array'


    def rebind(self, resource):
        return self.__class__(*self.properties).bind(resource)

    def schema(self):
        return {
            "type": "array",
            "items": [self.resource.schema.fields[p].request for p in self.properties],
            "additionalItems": False
        }

    def format(self, item):
        return [self.resource.schema.fields[p].output(p, item) for p in self.properties]

    @cached_property
    def _field_filters(self):
        return self.resource.manager.filters

    def convert(self, value):
        return self.resource.manager.first(where=[
            Condition(property, self._field_filters[property][None], value[i])
            for i, property in enumerate(self.properties)
        ])


class IDKey(Key):

    def _on_bind(self, resource):
        self.id_field = resource.manager.id_field

    def schema(self):
        return self.id_field.request

    def format(self, item):
        return self.id_field.output(self.resource.manager.id_attribute, item)

    def convert(self, value):
        return self.resource.manager.read(self.id_field.convert(value))
