import re
from flask import url_for, current_app
from werkzeug.utils import cached_property
from flask.ext.potion.reference import resolvers
from flask.ext.potion.schema import Schema


class Raw(Schema):
    """
    :param io: one of "r", "w" and "rw"
    :param schema: JSON-schema for field, or :class:`callable` resolving to a JSON-schema when called
    :param default: optional default value, must be JSON-convertible
    :param attribute: key on parent object, optional.
    :param nullable: whether the field is nullable.
    :param title: optional title for JSON schema
    :param description: optional description for JSON schema
    """

    def __init__(self, schema, io="rw", default=None, attribute=None, nullable=False, title=None, description=None):
        self._schema = schema
        self.default = default
        self.attribute = attribute
        self.nullable = nullable
        self.title = title
        self.description = description

    def _finalize_schema(self, schema):
        """
        :return: new schema updated for field `nullable`, `title`, `description` and `default` attributes.
        """
        schema = dict(schema)
        if 'null' in schema.get('type'):
            self.nullable = True
        elif self.nullable:
            if "anyOf" in schema:
                if not any('null' in choice.get('type', []) for choice in schema['anyOf']):
                    schema['anyOf'].append({'type': 'null'})
            elif "oneOf" in schema:
                if not any('null' in choice.get('type', []) for choice in schema['oneOf']):
                    schema['oneOf'].append({'type': 'null'})
            else:
                try:
                    type_ = schema['type']
                    if isinstance(type_, (str, dict)):
                        schema['type'] = [type_, 'null']
                    else:
                        schema['type'].append('null')
                except KeyError:
                    if len(schema) == 1 and '$ref' in schema:
                        schema = {'anyOf': [schema, {'type': 'null'}]}
                    else:
                        current_app.logger.warn('{} is nullable but "null" type cannot be added to schema.'.format(self))

        for attr in ('default', 'title', 'description'):
            value = getattr(self, attr)
            if value is not None:
                schema[attr] = value
        return schema

    @cached_property
    def schema(self):
        """
        JSON schema representation
        """
        schema = self._schema
        if callable(schema):
            schema = schema()

        if isinstance(schema, Schema):
            read_schema, write_schema = schema.response, schema.request
        elif isinstance(schema, tuple):
            read_schema, write_schema = schema
        else:
            return self._finalize_schema(schema)

        return (self._finalize_schema(s) for s in (read_schema, write_schema))

    def format(self, value):
        """
        Format a Python value representation for output in JSON. Noop by default.
        """
        return value

    def convert(self, value):
        """
        Convert a JSON value representation to a Python object. Noop by default.
        """
        return value

    def output(self, key, obj):
        value = getattr(key if self.attribute is None else self.attribute, obj)

        if value is None:
            return self.default

        return self.format(value)


class Array(Raw):
    """
    A field for an array of a given field type.

    :param Raw cls_or_instance: field class or instance
    """
    def __init__(self, cls_or_instance, min_items=None, max_items=None, **kwargs):
        if isinstance(cls_or_instance, type):
            container = cls_or_instance()
        else:
            container = cls_or_instance

        if not isinstance(container, Schema):
            raise RuntimeError('{} expects Raw or Schema, got {}'.format(self, container.__class__.__name__))
        if not isinstance(container, Raw):
            container = Raw(container)

        self.container = container

        schema_properties = [('type', 'array')]
        schema_properties += [(k, v) for k, v in [('minItems', min_items), ('maxItems', max_items)] if v is not None]

        super(Array, self).__init__(lambda: (
            dict([('items', container.response)] + schema_properties),
            dict([('items', container.request)] + schema_properties)
        ), **kwargs)

    def format(self, value):
        return [self.container.format(v) for v in value]

    def convert(self, value):
        return [self.container.convert(v) for v in value]


# class Object(Raw):
#
#     def __init__(self, properties=None, pattern_properties=None, additional_properties=None, nullable=False):
#         pass


class String(Raw):
    """
    :param int min_length: minimum length of string
    :param int max_length: maximum length of string
    :param str pattern: regex pattern that the string must match
    :param list enum: list of strings with enumeration
    """

    def __init__(self, min_length=None, max_length=None, pattern=None, enum=None, **kwargs):
        schema = {"type": "string"}

        for v, k in ((min_length, 'minLength'), (max_length, 'maxLength'), (pattern, 'pattern'), (enum, 'enum')):
            if v is not None:
                schema[k] = v

        super(String, self).__init__(schema, **kwargs)


class Boolean(Raw):
    def __init__(self, **kwargs):
        super(Boolean, self).__init__({"type": "boolean"}, **kwargs)

    def format(self, value):
        return bool(value)


class Integer(Raw):
    def __init__(self, minimum=None, maximum=None, default=0, **kwargs):
        schema = {"type": "integer"}

        if minimum is not None:
            schema['minimum'] = minimum
        if maximum is not None:
            schema['maximum'] = maximum

        super(Integer, self).__init__(schema, default=default, **kwargs)

    def format(self, value):
        return int(value)


class PositiveInteger(Integer):
    """
    A :class:`Integer` field that only accepts integers >=0.
    """

    def __init__(self, maximum=None, **kwargs):
        super(PositiveInteger, self).__init__(minimum=0, maximum=maximum, **kwargs)


class Number(Raw):
    def __init__(self,
                 default=0,
                 minimum=None,
                 maximum=None,
                 exclusive_minimum=False,
                 exclusive_maximum=False,
                 **kwargs):

        schema = {"type": "number"}

        if minimum is not None:
            schema['minimum'] = minimum
            if exclusive_minimum:
                schema['exclusiveMinimum'] = True

        if maximum is not None:
            schema['maximum'] = maximum
            if exclusive_maximum:
                schema['exclusiveMaximum'] = True

        super(Number, self).__init__(schema, default=default, **kwargs)

    def format(self, value):
        return float(value)


class ToOne(Raw):
    """

    Different schemas for read & write:

    {
        "type": "object",
        "properties": {
            "$ref": {
                "type": "string",
                "format": "uri",
                "pattern": "^{}".format(re.escape(resource_url))
            }
        },
        "required": ["$ref"]
    }

    {
        "type": ["null", "object"],
        "anyOf": {
            "$ref": "{}/schema#definitions/_resolvers".format(resource_url)
        }
    }


    """
    def __init__(self, resource, formatter=resolvers.RefResolver(), **kwargs):
        self.resource = resource
        self.formatter = formatter
        self.binding = None

        def schema():
            resource_url = url_for(self.resource.endpoint)
            resource_reference = { "$ref": "{}/schema".format(resource_url) }
            response_schema = {
                "oneOf": [
                    formatter.schema(resource),
                    resource_reference
                ]
            }

            natural_keys = resource.meta.natural_keys
            if natural_keys:
                request_schema = {
                    "anyOf": [formatter.schema(resource)] + [nk.request for nk in natural_keys]
                }
            else:
                request_schema = resource_reference
            return response_schema, request_schema

        super(ToOne, self).__init__(schema, **kwargs)



class Inline(Raw):

    def __init__(self, resource, **kwargs):
        self.resource = resource