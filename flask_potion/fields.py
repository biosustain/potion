import re
import collections
from flask import url_for, current_app
from werkzeug.utils import cached_property
from . import resolvers
from .reference import ResourceReference
from .schema import Schema

# FIXME this code is similar to Flask-RESTful code. Need to add license
def _get_value_for_key(key, obj, default):
    if hasattr(obj, '__getitem__'):
        try:
            return obj[key]
        except (IndexError, KeyError):
            pass
    return getattr(obj, key, default)


class Raw(Schema):
    """
    :param io: one of "r", "w" or "rw" (default); used to control presence in fieldsets/parent schemas
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
        self.io = io

    def _finalize_schema(self, schema):
        """
        :return: new schema updated for field `nullable`, `title`, `description` and `default` attributes.
        """
        schema = dict(schema)
        if 'null' in schema.get('type', []):
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

        return (self._finalize_schema(read_schema), self._finalize_schema(write_schema))

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
        key = key if self.attribute is None else self.attribute
        return self.format(_get_value_for_key(key, obj, self.default))


# FIXME this code is similar to Flask-RESTful code. Need to add license
def _field_from_object(parent, cls_or_instance):
    if isinstance(cls_or_instance, type):
        container = cls_or_instance()
    else:
        container = cls_or_instance

    if not isinstance(container, Schema):
        raise RuntimeError('{} expected Raw or Schema, but got {}'.format(parent, container.__class__.__name__))
    if not isinstance(container, Raw):
        container = Raw(container)

    return container


class Array(Raw):
    """
    A field for an array of a given field type.

    :param Raw cls_or_instance: field class or instance
    """
    def __init__(self, cls_or_instance, min_items=None, max_items=None, **kwargs):
        self.container = container = _field_from_object(self, cls_or_instance)

        schema_properties = [('type', 'array')]
        schema_properties += [(k, v) for k, v in [('minItems', min_items), ('maxItems', max_items)] if v is not None]
        schema = lambda s: dict([('items', s)] + schema_properties)

        super(Array, self).__init__(lambda: (schema(container.response), schema(container.request)), **kwargs)

    def format(self, value):
        return [self.container.format(v) for v in value]

    def convert(self, value):
        return [self.container.convert(v) for v in value]


class KeyValue(Raw):
    """
    A field for an object containing properties of a single type specified by a schema or field.

    :param Raw cls_or_instance: field class or instance
    :param str pattern: an optional regular expression that all property keys must match
    """
    def __init__(self, cls_or_instance, pattern=None, **kwargs):
        self.container = container = _field_from_object(self, cls_or_instance)

        if pattern:
            schema = lambda s: {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    pattern: s
                }
            }
        else:
            schema = lambda s: {
                "type": "object",
                "additionalProperties": s
            }

        super(KeyValue, self).__init__(lambda: (schema(container.response), schema(container.request)), **kwargs)

    def format(self, value):
        return {k: self.container.format(v) for k, v in value.items()}

    def convert(self, value):
        return {k: self.container.convert(v) for k, v in value.items()}


class AttributeMapped(KeyValue):
    """
    Maps property keys from a JSON object to a list of items using `mapping_attribute`. The mapping attribute is the
    name of the attribute where the value of the property key is set on the property values.

    .. seealso::

        :class:`InlineModel` field is typically used with this field in a common SQLAlchemy pattern.

    :param Raw cls_or_instance: field class or instance
    :param str pattern: an optional regular expression that all property keys must match
    :param str mapping_attribute: mapping attribute
    """
    def __init__(self, *args, mapping_attribute=None, **kwargs):
        self.mapping_attribute = mapping_attribute
        super().__init__(*args, **kwargs)

    def _set_mapping_attribute(self, obj, value):
        setattr(obj, self.mapping_attribute, value)
        return obj

    def format(self, value):
        return {getattr(v, self.mapping_attribute): self.container.format(v) for v in value}

    def convert(self, value):
        return [self._set_mapping_attribute(self.container.convert(v), k) for k, v in value.items()]


class Object(Raw):
    """
    A versatile field for an object, containing either properties all of a single type, properties matching a pattern,
    or named properties matching some fields.

    :param properties: field class, instance, or dictionary of {property: field} pairs
    :param str pattern: an optional regular expression that all property keys must match
    :param dict pattern_properties: dictionary of {property: field} pairs
    :param dict additional_properties: field class or instance
    """

    def __init__(self, properties=None, pattern=None, pattern_properties=None, additional_properties=None, **kwargs):
        self.properties = None
        self.pattern_properties = None
        self.additional_properties = None

        if isinstance(properties, dict):
            self.properties = properties
        elif isinstance(properties, (type, Raw)):
            field = _field_from_object(self, properties)
            if pattern:
                self.pattern_properties = {pattern: field}
            else:
                self.additional_properties = field

        def schema():
            request = {"type": "object"}
            response = {"type": "object"}

            for schema, attr in ((request, "request"), (response, "response")):
                if self.properties:
                    schema["properties"] = {key: getattr(field, attr) for key, field in self.properties.items()}
                if self.pattern_properties:
                    schema["patternProperties"] = {pattern: getattr(field, attr)
                                                     for pattern, field in self.pattern_properties.items()}
                if self.additional_properties:
                    schema["additionalProperties"] = getattr(self.additional_properties, attr)
                else:
                    schema["additionalProperties"] = False

            return response, request

        if self.pattern_properties and (len(self.pattern_properties) > 1 or self.additional_properties):
            raise NotImplementedError("Only one pattern property, which CANNOT BE combined with additionalProperties,"
                                      " is currently supported.")

        super(Object, self).__init__(schema, **kwargs)

    def format(self, value):
        raise NotImplementedError()
        # TODO support g
        if self.properties:
            return {key: field.format(_get_value_for_key(key, value, field.default)) for key, field in self.properties.items()}

        if self.additional_properties or self.pattern_properties:
            pass
        else:
            return {k: self.container.format(v) for k, v in value.items()}

    def convert(self, value):
        raise NotImplementedError()

        return {k: self.container.convert(v) for k, v in value.items()}

class String(Raw):
    """
    :param int min_length: minimum length of string
    :param int max_length: maximum length of string
    :param str pattern: regex pattern that the string must match
    :param list enum: list of strings with enumeration
    """

    def __init__(self, min_length=None, max_length=None, pattern=None, enum=None, format=None, **kwargs):
        schema = {"type": "string"}

        for v, k in ((min_length, 'minLength'),
                     (max_length, 'maxLength'),
                     (pattern, 'pattern'),
                     (enum, 'enum'),
                     (format, 'format')):
            if v is not None:
                schema[k] = v

        super(String, self).__init__(schema, **kwargs)




#
# Default:
# {"$date": <iso date>}
#
# Accepts also: string dates
#
#
#

class Date(Raw):
    # """
    # Only accept ISO8601-formatted date strings.
    # """
    #
    # def __init__(self, **kwargs):
    #     # TODO is a 'format' required for "date"
    #     super(Date, self).__init__({"type": "string", "format": "date"}, **kwargs)
    #
    # @skip_none
    # def format(self, value):
    #     return value.strftime('%Y-%m-%d')
    #
    # @skip_none
    # def convert(self, value):
    #     return aniso8601.parse_date(value)
    pass


class DateTime(Raw):
    # """
    # Only accept ISO8601-formatted date-time strings.
    # """
    #
    # def __init__(self, **kwargs):
    #     super(DateTime, self).__init__({"type": "string", "format": "date-time"}, **kwargs)
    #
    # @skip_none
    # def format(self, value):
    #     return value.isoformat()
    #
    # @skip_none
    # def convert(self, value):
    #     # FIXME enforce UTC
    #     return aniso8601.parse_datetime(value)
    pass


class Uri(String):
    def __init__(self, **kwargs):
        super(Uri, self).__init__(format="uri", **kwargs)


class Email(String):
    def __init__(self, **kwargs):
        super(Email, self).__init__(format="email", **kwargs)



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
    def __init__(self, resource, formatter=resolvers.RefResolver(), **kwargs):
        self._resource = ResourceReference(resource)
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

    @cached_property
    def resource(self):
        return self._resource.resolve(self.binding)  # FIXME XXX could just have this in Potion instance

    def format(self, item):
        raise NotImplementedError() # TODO


    def convert(self, value):
        pass


class ToMany(Array):
    def __init__(self, resource, **kwargs):
        super(ToMany, self).__init__(ToOne(resource, nullable=False), **kwargs)


class Inline(Raw):

    def __init__(self, resource, **kwargs):
        self.reference = ResourceReference(resource)
        self.binding = None

        def schema():
            if self.binding == self.resource:
                return { "$ref": "#" }

            # resource_url = url_for(self.resource.endpoint)
            # return { "$ref": "{}/schema".format(resource_url) }
            # FIXME complete with API prefix

            return { "$ref": self.resource.routes["schema"].rule_factory(self.resource) }

        super(Inline, self).__init__(schema, **kwargs)

    @cached_property
    def resource(self):
        return self.reference.resolve(self.binding)

    def format(self, item):
        return self.resource.schema.format(item)

    def convert(self, item):
        # TODO create actual model instance here?
        return self.resource.schema.convert(item)


# class InlineModel(fields.Nested):
#
#     def __init__(self, fields, model, **kwargs):
#         super().__init__(fields, **kwargs)
#         self.model = model
#
#     def convert(self, obj):
#         obj = EmbeddedJob.complete(super().convert(obj))
#         if obj is not None:
#             obj = self.model(**obj)
#         return obj
#
#     def format(self, obj):
#         return marshal(obj, self.fields)