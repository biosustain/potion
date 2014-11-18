import re
from flask import url_for
from werkzeug.utils import cached_property
from .exceptions import ItemNotFound
from .schema import Schema
from .util import route_from
import six

class Resolver(object):

    def matcher_type(self, resource):
        type_ = self.schema(resource)['type']
        if isinstance(type_, six.text_type):
            return type_
        return type_[0]

    def schema(self, resource):
        raise NotImplementedError()


class RefResolver(Resolver):

    def schema(self, resource):
        resource_url = url_for(resource.endpoint)
        return {
            "type": "object",
            "properties": {
                "$ref": {
                    "type": "string",
                    "format": "uri",
                    "pattern": "^{}".format(re.escape(resource_url))
                }
            },
            "required": ["$ref"],
            "additionalProperties": False
        }

    def format(self, resource, item):
        return {"$ref": resource.get_item_url(item)}

    def resolve(self, resource, value):
        endpoint, args = route_from(value["$ref"])
        # XXX verify endpoint is correct (it should be)
        # assert resource.endpoint == endpoint
        return resource.manager.read(args['id'])


class PropertyResolver(Resolver):

    def __init__(self, property):
        self.property = property

    def schema(self, resource):
        return resource.schema[self.property].response_schema

    def format(self, resource, item):
        return resource.schema[self.property].output(self.property, item)

    def resolve(self, resource, value):
        instances = resource.manager.instances(where={self.property: value})
        try:
            return instances[0]
        except IndexError:
            raise ItemNotFound(resource, natural_key=value)


class PropertiesResolver(Resolver):
    def __init__(self, *properties):
        self.properties = properties

    def schema(self, resource):
        return {
            "type": "array",
            "items": [resource.schema[p].response_schema for p in self.properties],
            "additionalItems": False
        }

    def format(self, resource, item):
        return [resource.schema[p].output(p, item) for p in self.properties]

    def resolve(self, resource, value):
        instances = resource.manager.instances(where={property: value[i] for i, property in enumerate(self.properties)})
        try:
            return instances[0]
        except IndexError:
            raise ItemNotFound(resource, natural_key=value)


class IDResolver(Resolver):
    def schema(self, resource):
        return resource.meta.id_field.response_schema

    def format(self, resource, item):
        return resource.meta.id_field.output(resource.meta.id_attribute, item)

    def resolve(self, resource, value):
        return resource.manager.read(value)
