from collections import OrderedDict

from flask import json
from werkzeug.utils import cached_property
from jsonschema import Draft4Validator, ValidationError, FormatChecker

from flask_potion.reference import ResourceBound
from flask_potion.utils import unpack
from flask_potion.exceptions import ValidationError as PotionValidationError, RequestMustBeJSON


class Schema(object):
    """
    The base class for all types with a schema in Potion. Has :attr:`response` and a :attr:`request` attributes
    for the schema to be used, respectively, for serializing and de-serializing.

    Any class inheriting from schema needs to implement :meth:`schema`.

    ..  attribute:: response

        JSON-schema used to represent data returned by the server.

    .. attribute:: request

        JSON-schema used for validation of data sent to the server.

    """

    def schema(self):
        """
        Abstract method returning the JSON schema used by both :attr:`response` and :attr:`request`.

        :return: a JSON-schema or a tuple of JSON-schemas in the formats ``(response_schema, request_schema)`` or
            ``(read_schema, create_schema, update_schema)``
        """
        raise NotImplementedError()

    @cached_property
    def response(self):
        schema = self.schema()
        if isinstance(schema, tuple):
            return schema[0]
        return schema

    @cached_property
    def request(self):
        schema = self.schema()
        if isinstance(schema, tuple):
            return schema[1]
        return schema

    create = request

    @cached_property
    def update(self):
        schema = self.schema()
        if isinstance(schema, tuple):
            return schema[-1]
        return schema

    @cached_property
    def _validator(self):
        Draft4Validator.check_schema(self.request)
        return Draft4Validator(self.request, format_checker=FormatChecker())

    @cached_property
    def _update_validator(self):
        Draft4Validator.check_schema(self.update)
        return Draft4Validator(self.update, format_checker=FormatChecker())


    def format(self, value):
        """
        Formats a python object for JSON serialization. Noop by default.

        :param object value:
        :return:
        """
        return value

    def convert(self, instance, update=False):
        """
        Validates a deserialized JSON object against :attr:`request` and converts it into a python object.

        :param instance: JSON import
        :raises PotionValidationError: if validation failed
        """
        if update:
            validator = self._update_validator
        else:
            validator = self._validator
        try:
            validator.validate(instance)
        except ValidationError as ve:
            errors = validator.iter_errors(instance)
            raise PotionValidationError(errors)
        return instance

    def parse_request(self, request):
        """
        Parses a Flask request object, validates it the against :attr:`request` and returns the converted request data.

        :param request: Flask request object
        :return:
        """
        data = request.json

        if not data and request.method in ('GET', 'HEAD'):
            data = dict(request.args)

        return self.convert(data, update=request.method in ('PUT', 'PATCH'))

    def format_response(self, response):
        """
        Takes a response value, which can be a ``data`` object or a tuple ``(data, code)`` or ``(data, code, headers)``
        and formats it using :meth:`format`.

        :param response: A response tuple.
        :return: A tuple in the form ``(data, code, headers)``
        """
        data, code, headers = unpack(response)
        # TODO omit formatting on certain codes.
        return self.format(data), code, headers


class SchemaImpl(Schema):
    def __init__(self, schema):
        self._schema = schema

    def schema(self):
        return self._schema

class FieldSet(Schema, ResourceBound):
    """
    A schema representation of a dictionary of :class:`fields.Raw` objects.

    Uses the fields' ``io`` attributes to determine whether they are read-only, write-only, or read-write.

    :param dict fields: a dictionary of :class:`fields.Raw` objects
    :param required_fields: a list or tuple of field names that are required during parsing
    """

    def __init__(self, fields, required_fields=None):
        self.fields = fields
        self.required = set(required_fields or ())

    def bind(self, resource):
        if self.resource is None:
            self.resource = resource
            self.fields = {
                key: field.bind(resource) if isinstance(field, ResourceBound) else field
                for key, field in self.fields.items()
            }
        elif self.resource != resource:
            return self.rebind(resource)
        return self

    def rebind(self, resource):
        return FieldSet(
            dict(self.fields),
            tuple(self.required)
        ).bind(resource)

    def set(self, key, field):
        if self.resource and isinstance(field, ResourceBound):
            field = field.bind(self.resource)
        self.fields[key] = field

    def _schema(self, patchable=False):
        read_schema = {
            "type": "object",
            "properties": OrderedDict((
                (key, field.response) for key, field in self.fields.items() if 'r' in field.io))
        }

        create_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": OrderedDict((
                (key, field.request) for key, field in self.fields.items() if 'c' in field.io))
        }

        update_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": OrderedDict((
                (key, field.request) for key, field in self.fields.items() if 'u' in field.io))
        }

        # TODO figure out logic for required
        for key, field in self.fields.items():
            if 'c' in field.io and not field.nullable and field.default is None:
                self.required.add(key)

        if not patchable and self.required:
            create_schema['required'] = list(self.required)

        return read_schema, create_schema, update_schema


    def schema(self):
        return self._schema()

    @cached_property
    def patchable(self):
        return SchemaImpl(self._schema(True))

    def format(self, item):
        return OrderedDict((key, field.output(key, item)) for key, field in self.fields.items() if 'r' in field.io)

    def convert(self, instance, update=False, pre_resolved_properties=None, patchable=False, strict=False):
        """
        :param instance: JSON-object
        :param pre_resolved_properties: optional dictionary of properties that are already known
        :param bool patchable: when ``True`` does not check for required fields
        :param bool strict:
        :return:
        """
        result = dict(pre_resolved_properties) if pre_resolved_properties else {}

        if patchable:
            object_ = self.patchable.convert(instance, update)
        else:
            object_ = super(FieldSet, self).convert(instance, update)

        for key, field in self.fields.items():
            if update and 'u' not in field.io or not update and 'c' not in field.io:
                continue

            # ignore fields that have been pre-resolved
            if key in result:
                continue

            value = None

            try:
                value = object_[key]
                value = field.convert(value, validate=False)
            except KeyError:
                if patchable:
                    continue

                if field.default is not None:
                    value = field.default
                elif field.nullable:
                    value = None
                elif key not in self.required and not strict:
                    value = None

            result[field.attribute or key] = value
        return result

    def parse_request(self, request):
        if request.method in ('POST', 'PATCH', 'PUT', 'DELETE'):
            if request.mimetype != 'application/json':
                raise RequestMustBeJSON()

        # TODO change to request.get_json() to catch invalid JSON
        data = request.json

        # FIXME raise error if request body is not JSON

        if not self.fields:
            return {}

        if not data and request.method in ('GET', 'HEAD'):
            data = {}

            for name, field in self.fields.items():
                try:
                    value = request.args[name]
                    # FIXME type conversion!
                    try:
                        data[name] = json.loads(value)
                    except ValueError:
                        data[name] = value
                except KeyError:
                    pass

        return self.convert(data, update=request.method in ('PUT', 'PATCH'), patchable=request.method == 'PATCH')

