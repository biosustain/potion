import calendar
from datetime import datetime
import re

import aniso8601
from flask import current_app, request
import six
from werkzeug.utils import cached_property

from flask_potion.utils import get_value, route_from
from flask_potion.reference import ResourceReference, ResourceBound, _bind_schema
from flask_potion.schema import Schema

class Raw(Schema):
    """
    This is the base class for all field types, can be given any JSON-schema.

    >>> f = fields.Raw({"type": "string"}, io="r")
    >>> f.response
    {'readOnly': True, 'type': 'string'}

    :param io: one or more of "r" (read), "c" (create), "u" (update) and "w" (write), default: "rw";
     used to control presence in fieldsets/parent schemas
    :param schema: JSON-schema for field, or :class:`callable` resolving to a JSON-schema when called
    :param default: optional default value, must be JSON-convertible; may be a callable with no arguments
    :param attribute: key on parent object, optional.
    :param nullable: whether the field is nullable.
    :param title: optional title for JSON schema
    :param description: optional description for JSON schema
    """

    def __init__(self, schema, io="rw", default=None, attribute=None, nullable=False, title=None, description=None):
        self._schema = schema
        self._default = default
        self.attribute = attribute
        self.nullable = nullable
        self.title = title
        self.description = description
        self.io = io

    def _finalize_schema(self, schema, io):
        """
        :return: new schema updated for field `nullable`, `title`, `description` and `default` attributes.
        """
        schema = dict(schema)

        if self.io == "r" and "r" in io:
            schema["readOnly"] = True

        if "null" in schema.get("type", []):
            self.nullable = True
        elif self.nullable:
            # enum is independent of type validation:
            if "enum" in schema and None not in schema["enum"]:
                schema["enum"].append(None)

            if "type" in schema:
                type_ = schema["type"]
                if isinstance(type_, (str, dict)):
                    schema["type"] = [type_, "null"]
                else:
                    schema["type"].append("null")

            if "anyOf" in schema:
                if not any("null" in choice.get("type", []) for choice in schema["anyOf"]):
                    schema["anyOf"].append({"type": "null"})
            elif "oneOf" in schema:
                if not any("null" in choice.get("type", []) for choice in schema["oneOf"]):
                    schema["oneOf"].append({"type": "null"})
            elif "type" not in schema:
                if len(schema) == 1 and "$ref" in schema:
                    schema = {"anyOf": [schema, {"type": "null"}]}
                else:
                    current_app.logger.warn('{} is nullable but "null" type cannot be added'.format(self))

        for attr in ("default", "title", "description"):
            value = getattr(self, attr)
            if value is not None:
                schema[attr] = value
        return schema

    @property
    def io(self):
        return self._io

    @io.setter
    def io(self, value):
        io = ''
        if 'w' in value or 'c' in value:
            io += 'c'
        if 'r' in value:
            io += 'r'
        if 'w' in value or 'u' in value:
            io += 'u'
        self._io = io

    @property
    def default(self):
        if callable(self._default):
            return self._default()
        return self._default

    @default.setter
    def default(self, value):
        self._default = value

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
            return self._finalize_schema(schema, "r"), self._finalize_schema(schema, "w")

        return self._finalize_schema(read_schema, "r"), self._finalize_schema(write_schema, "w")

    def format(self, value):
        """
        Format a Python value representation for output in JSON. Noop by default.
        """
        if value is not None:
            return self.formatter(value)
        return value

    def convert(self, instance, update=False, validate=True):
        """
        Convert a JSON value representation to a Python object. Noop by default.
        """
        if validate:
            instance = super(Raw, self).convert(instance, update)

        if instance is not None:
            return self.converter(instance)
        return instance

    def formatter(self, value):
        return value

    def converter(self, value):
        return value

    def output(self, key, obj):
        key = key if self.attribute is None else self.attribute
        return self.format(get_value(key, obj, self.default))

    def __repr__(self):
        return '{}(attribute={})'.format(self.__class__.__name__, repr(self.attribute))


class Any(Raw):
    """
    A field type that allows any value.
    """
    def __init__(self, **kwargs):
        super(Any, self).__init__({"type": ["null", "string", "number", "boolean", "object", "array"]}, **kwargs)

def _field_from_object(parent, cls_or_instance):
    # --- start of Flask-RESTful code ---
    # Copyright (c) 2013, Twilio, Inc.
    # All rights reserved.
    # This code is part of or substantially similar to code in Flask-RESTful and is governed by its
    # license. Please see the LICENSE file in the root of this package.
    if isinstance(cls_or_instance, type):
        container = cls_or_instance()
    else:
        container = cls_or_instance
    if not isinstance(container, Schema):
        raise RuntimeError('{} expected Raw or Schema, but got {}'.format(parent, container.__class__.__name__))
    if not isinstance(container, Raw):
        container = Raw(container)
    # --- end of Flask-RESTful code ---
    return container


class Custom(Raw):
    """
    A field type that cann be passed any schema and optional formatter/converter transformers. It is a very thin
    wrapper over :class:`Raw`.

    :param dict schema: JSON-schema
    :param callable converter: convert function
    :param callable formatter: format function
    """

    def __init__(self, schema, converter=None, formatter=None, **kwargs):
        super(Custom, self).__init__(schema, **kwargs)
        self._converter = converter
        self._formatter = formatter

    def format(self, value):
        if self._formatter is None:
            return value
        return self._formatter(value)

    def converter(self, value):
        if self._converter is None:
            return value
        return self._converter(value)


class Array(Raw, ResourceBound):
    """
    A field for an array of a given field type.

    :param Raw cls_or_instance: field class or instance
    :param int min_items: minimum number of items
    :param int max_items: maximum number of items
    :param bool unique: if ``True``, all values in the list must be unique
    """

    def __init__(self, cls_or_instance, min_items=None, max_items=None, unique=None, **kwargs):
        self.container = container = _field_from_object(self, cls_or_instance)

        schema_properties = [('type', 'array')]
        schema_properties += [(k, v) for k, v in [('minItems', min_items), ('maxItems', max_items), ('uniqueItems', unique)] if v is not None]
        schema = lambda s: dict([('items', s)] + schema_properties)

        super(Array, self).__init__(lambda: (schema(container.response), schema(container.request)),
                                    default=kwargs.pop('default', list), **kwargs)

    def bind(self, resource):
        if isinstance(self.container, ResourceBound):
            self.container = self.container.bind(resource)
        return self

    def format(self, value):
        if value is not None:
            return self.formatter(value)
        if not self.nullable:
            return []
        return value

    def formatter(self, value):
        return [self.container.format(v) for v in value]

    def converter(self, value):
        return [self.container.convert(v) for v in value]


List = Array


class Object(Raw, ResourceBound):
    """
    A versatile field for an object, containing either properties all of a single type, properties matching a pattern,
    or named properties matching some fields.

    `Raw.attribute` is not used in pattern properties and additional properties.

    :param properties: field class, instance, or dictionary of {property: field} pairs
    :param str pattern: an optional regular expression that all property keys must match
    :param dict pattern_properties: dictionary of {property: field} pairs
    :param Raw additional_properties: field class or instance
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

        if isinstance(additional_properties, (type, Raw)):
            self.additional_properties = _field_from_object(self, additional_properties)
        elif additional_properties is True:
            self.additional_properties = Any()

        if isinstance(pattern_properties, (type, Raw)):
            self.pattern_properties = _field_from_object(self, pattern_properties)

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
            raise NotImplementedError("Only one pattern property is currently supported "
                                      "and it cannot be combined with additionalProperties")

        super(Object, self).__init__(schema, **kwargs)

    def bind(self, resource):
        if self.properties:
            self.properties = {
                key: _bind_schema(value, resource)
                for key, value in self.properties.items()}
        if self.pattern_properties:
            self.pattern_properties = {
                key: _bind_schema(value, resource)
                for key, value in self.pattern_properties.items()}
        if self.additional_properties:
            self.additional_properties = _bind_schema(self.additional_properties, resource)
        return self

    @cached_property
    def _property_attributes(self):
        if not self.properties:
            return ()
        return [field.attribute or key for key, field in self.properties.items()]

    def formatter(self, value):
        output = {}

        if self.properties:
            output = {key: field.format(get_value(field.attribute or key, value, field.default)) for key, field in self.properties.items()}
        else:
            output = {}

        if self.pattern_properties:
            pattern, field = next(iter(self.pattern_properties.items()))

            if not self.additional_properties:
                output.update({k: field.format(v) for k, v in value.items() if k not in self._property_attributes})
            else:
                raise NotImplementedError()
                # TODO match regular expression
        elif self.additional_properties:
            field = self.additional_properties
            output.update({k: field.format(v) for k, v in value.items() if k not in self._property_attributes})

        return output

    def converter(self, instance):
        result = {}

        if self.properties:
            result = {field.attribute or key: field.convert(instance.get(key, field.default))
                      for key, field in self.properties.items()}

        if self.pattern_properties:
            pattern, field = next(iter(self.pattern_properties.items()))

            if not self.additional_properties:
                result.update({key: field.convert(value)
                               for key, value in instance.items() if key not in result})
            else:
                raise NotImplementedError()
                # TODO match regular expression
        elif self.additional_properties:
            field = self.additional_properties
            result.update({key: field.convert(value) for key, value in instance.items() if key not in result})

        return result


class AttributeMapped(Object):
    """
    Maps property keys from a JSON object to a list of items using `mapping_attribute`. The mapping attribute is the
    name of the attribute where the value of the property key is set on the property values.

    :class:`contrib.alchemy.fields.InlineModel` is typically used with this field in a common SQLAlchemy pattern.

    :param Raw cls_or_instance: field class or instance
    :param str pattern: an optional regular expression that all property keys must match
    :param str mapping_attribute: mapping attribute
    """

    def __init__(self, cls_or_instance, mapping_attribute=None, **kwargs):
        self.mapping_attribute = mapping_attribute
        # TODO reject additional_properties, properties, pattern_properties, pattern
        super(AttributeMapped, self).__init__(cls_or_instance, **kwargs)

    def _set_mapping_attribute(self, obj, value):
        if isinstance(obj, dict):
            obj[self.mapping_attribute] = value
        else:
            setattr(obj, self.mapping_attribute, value)
        return obj

    def formatter(self, value):
        if self.pattern_properties:
            pattern, field = next(iter(self.pattern_properties.items()))
            return {get_value(self.mapping_attribute, v, None): field.format(v) for v in value}
        elif self.additional_properties:
            return {get_value(self.mapping_attribute, v, None): self.additional_properties.format(v) for v in value}

    def converter(self, value):
        if self.pattern_properties:
            pattern, field = next(iter(self.pattern_properties.items()))
            return [self._set_mapping_attribute(field.convert(v), k) for k, v in value.items()]
        elif self.additional_properties:
            return [self._set_mapping_attribute(self.additional_properties.convert(v), k) for k, v in value.items()]


class String(Raw):
    """
    :param int min_length: minimum length of string
    :param int max_length: maximum length of string
    :param str pattern: regex pattern that the string must match
    :param list enum: list of strings with enumeration
    """
    url_rule_converter = 'string'

    def __init__(self, min_length=None, max_length=None, pattern=None, enum=None, format=None, **kwargs):
        schema = {"type": "string"}

        if enum is not None:
            enum = list(enum)

        for v, k in ((min_length, 'minLength'),
                     (max_length, 'maxLength'),
                     (pattern, 'pattern'),
                     (enum, 'enum'),
                     (format, 'format')):
            if v is not None:
                schema[k] = v

        super(String, self).__init__(schema, **kwargs)


class UUID(String):
    """
    A field for UUID strings in canonical form.
    """
    url_rule_converter = 'string'
    UUID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

    def __init__(self, **kwargs):
        super(UUID, self).__init__(min_length=36, max_length=36, pattern=self.UUID_REGEX, **kwargs)


try:
    from datetime import timezone
except ImportError:
    from datetime import tzinfo, timedelta

    class timezone(tzinfo):
        def __init__(self, utcoffset, name=None):
            self._utcoffset = utcoffset
            self._name = name

        def utcoffset(self, dt):
            return self._utcoffset

        def tzname(self, dt):
            return self._name

        def dst(self, dt):
            return timedelta(0)

    timezone.utc = timezone(timedelta(0), 'UTC')


class Date(Raw):
    """
    A field for EJSON-style dates in the format:

    ::

        {"$date": MILLISECONDS_SINCE_EPOCH}

    Converts to :class:`datetime.date` with UTC timezone.

    """

    def __init__(self, **kwargs):
        # TODO is a 'format' required for "date"
        super(Date, self).__init__({
                                       "type": "object",
                                       "properties": {
                                           "$date": {
                                               "type": "integer"
                                           }
                                       },
                                       "additionalProperties": False
                                   }, **kwargs)

    def formatter(self, value):
        return {"$date": int(calendar.timegm(value.timetuple()) * 1000)}

    def converter(self, value):
        # TODO support both $dateObj and ISO string formats
        return datetime.fromtimestamp(value["$date"] / 1000, timezone.utc).date()


class DateTime(Date):
    """
    A field for EJSON-style date-times in the format:

    ::

        {"$date": MILLISECONDS_SINCE_EPOCH}

    Converts to :class:`datetime.datetime` with UTC timezone.

    """

    def formatter(self, value):
        return {"$date": int(calendar.timegm(value.utctimetuple()) * 1000)}

    def converter(self, value):
        # TODO support both $dateObj and ISO string formats
        return datetime.fromtimestamp(value["$date"] / 1000, timezone.utc)


class DateString(Raw):
    """
    A field for ISO8601-formatted date strings.
    """

    def __init__(self, **kwargs):
        # TODO is a 'format' required for "date"
        super(DateString, self).__init__({"type": "string", "format": "date"}, **kwargs)

    def formatter(self, value):
        return value.strftime('%Y-%m-%d')

    def converter(self, value):
        return aniso8601.parse_date(value)


class DateTimeString(Raw):
    """
    A field for ISO8601-formatted date-time strings.
    """

    def __init__(self, **kwargs):
        super(DateTimeString, self).__init__({"type": "string", "format": "date-time"}, **kwargs)

    def formatter(self, value):
        return value.isoformat()

    def converter(self, value):
        # FIXME enforce UTC
        return aniso8601.parse_datetime(value)


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
    url_rule_converter = 'int'

    def __init__(self, minimum=None, maximum=None, default=None, **kwargs):
        schema = {"type": "integer"}

        if minimum is not None:
            schema['minimum'] = minimum
        if maximum is not None:
            schema['maximum'] = maximum

        super(Integer, self).__init__(schema, default=default, **kwargs)

    def formatter(self, value):
        return int(value)


class PositiveInteger(Integer):
    """
    A :class:`Integer` field that only accepts integers >=1.
    """

    def __init__(self, maximum=None, **kwargs):
        super(PositiveInteger, self).__init__(minimum=1, maximum=maximum, **kwargs)


class Number(Raw):
    def __init__(self,
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

        super(Number, self).__init__(schema, **kwargs)

    def formatter(self, value):
        return float(value)


class ToOne(Raw, ResourceBound):
    """
    Represents references between resources as `json-ref` objects.

    Resource references can be one of the following:

    - :class:`Resource` class
    - a string with a resource name
    - a string with a module name and class name of a resource
    - ``"self"`` --- which resolves to the resource this field is bound to

    :param resource: a resource reference
    """
    def __init__(self, resource, **kwargs):
        self.target_reference = ResourceReference(resource)

        def schema():
            target = self.target
            key_converters = self.target.meta.key_converters
            response_schema = self.formatter_key.response
            if len(key_converters) > 1:
                request_schema = {
                    # "type": [self.formatter_key.matcher_type()] + [nk.matcher_type() for nk in natural_keys],
                    "anyOf": [nk.request for nk in key_converters]
                }
            else:
                request_schema = self.formatter_key.request
            return response_schema, request_schema

        super(ToOne, self).__init__(schema, **kwargs)

    def rebind(self, resource):
        if self.target_reference.value == 'self':
            return self.__class__(
                'self',
                default=self.default,
                attribute=self.attribute,
                nullable=self.nullable,
                title=self.title,
                description=self.description,
                io=self.io
            ).bind(resource)
        else:
            return self

    @cached_property
    def target(self):
        return self.target_reference.resolve(self.resource)

    @cached_property
    def formatter_key(self):
        return self.target.meta.key_converters[0]

    def formatter(self, item):
        return self.formatter_key.format(item)

    def converter(self, value):
        for python_type, json_type in (
                (dict, 'object'),
                (int, 'integer'),
                ((list, tuple), 'array'),
                (six.string_types, 'string')):
            if isinstance(value, python_type):
                return self.target.meta.key_converters_by_type[json_type].convert(value)


class ToMany(Array):
    """
    Like :class:`ToOne`, but for arrays of references.
    """
    def __init__(self, resource, **kwargs):
        super(ToMany, self).__init__(ToOne(resource, nullable=False), **kwargs)


class Inline(Raw, ResourceBound):
    """
    Formats and converts items in a :class:`ModelResource` using the resource's ``schema``.

    :param resource: a resource reference as in :class:`ToOne`
    :param bool patchable: whether to allow partial objects
    """

    def __init__(self, resource, patchable=False, **kwargs):
        self.target_reference = ResourceReference(resource)
        self.patchable = patchable

        def schema():
            def _response_schema():
                if self.resource == self.target:
                    return {"$ref": "#"}
                return {"$ref": self.resource.routes["describedBy"].rule_factory(self.resource)}

            if not not self.patchable:
                return _response_schema()
            else:
                return _response_schema(), self.target.schema.patchable.update

        super(Inline, self).__init__(schema, **kwargs)

    def rebind(self, resource):
        if self.target_reference.value == 'self':
            return self.__class__(
                'self',
                patchable=self.patchable,
                default=self.default,
                attribute=self.attribute,
                nullable=self.nullable,
                title=self.title,
                description=self.description,
                io=self.io
            ).bind(resource)
        else:
            return self

    @cached_property
    def target(self):
        return self.target_reference.resolve(self.resource)

    def format(self, item):
        return self.target.schema.format(item)

    def convert(self, item, update=False):
        return self.target.schema.convert(item, update=update, patchable=self.patchable)


class ItemType(Raw):
    """
    A string field that formats the name of a resource; read-only.
    """
    def __init__(self, resource):
        self.resource = resource
        super(ItemType, self).__init__(lambda: {
            "type": "string",
            "enum": [self.resource.meta.name]
        }, io="r")

    def format(self, value):
        return self.resource.meta.name


class ItemUri(Raw):
    """
    A string field that formats the url of a resource item; read-only.
    """
    def __init__(self, resource, attribute=None):
        self.target_reference = ResourceReference(resource)
        super(ItemUri, self).__init__(lambda: {
            "type": "string",
            "pattern": "^{}\/[^/]+$".format(re.escape(self.target.route_prefix))
        }, io="r", attribute=attribute)

    @cached_property
    def target(self):
        return self.target_reference.resolve()

    def format(self, value):
        return '{}/{}'.format(self.target.route_prefix, value)

    def converter(self, value):
        try:
            endpoint, args = route_from(value, 'GET')
        except Exception as e:
            raise e
        return self.target.manager.id_field.convert(args['id'])
