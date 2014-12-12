from collections import OrderedDict
import six
from werkzeug.utils import cached_property
from jsonschema import Draft4Validator, ValidationError, FormatChecker
from .reference import ResourceBound
from .utils import unpack
from .exceptions import ValidationError as PotionValidationError, PotionException


class Schema(object):

    def schema(self):
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

    @cached_property
    def _validator(self):
        print(self.request)
        Draft4Validator.check_schema(self.request)
        return Draft4Validator(self.request, format_checker=FormatChecker())

    def format(self, value):
        return value

    def convert(self, instance):
        try:
            self._validator.validate(instance)
        except ValidationError as ve:
            errors = self._validator.iter_errors(instance)
            raise PotionValidationError(errors)
        return instance

    def parse_request(self, request):
        data = request.json

        if not data and request.method in ('GET', 'HEAD'):
            data = dict(request.args)

        return self.convert(data)

    def format_response(self, response):
        data, code, headers = unpack(response)
        # TODO omit formatting on certain codes.
        return self.format(data), code, headers


class FieldSet(Schema, ResourceBound):

    def __init__(self, fields, required_fields=None):
        self.fields = fields
        self.required = required_fields or ()

    def bind(self, resource):
        ResourceBound.bind(self, resource)
        for key, field in self.fields.items():
            if isinstance(field, ResourceBound):
                field.bind(resource)

    def set(self, key, field):
        self.fields[key] = field
        if self.resource and isinstance(field, ResourceBound):
            field.bind(self.resource)

    def schema(self):
        response_schema = {
            "type": "object",
            "properties": OrderedDict((
                (key, field.response) for key, field in self.fields.items() if 'r' in field.io))
        }

        request_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": OrderedDict((
                (key, field.request) for key, field in self.fields.items() if 'w' in field.io))
        }

        if self.required:
            request_schema['required'] = list(self.required)

        return response_schema, request_schema

    def format(self, item):
        return OrderedDict((
            (key, field.output(key, item))
            for key, field in self.fields.items()
        ))

    def convert(self, obj, pre_resolved_properties=None, patch=False, strict=False):
        converted = dict(pre_resolved_properties) if pre_resolved_properties else {}
        # TODO move converted properties into object_
        print(obj)
        obj = super(FieldSet, self).convert(obj)
        print(obj,'converted')

        # FIXME consider validating entire schema at the beginning for proper error messages.

        for key, field in self.fields.items():
            if 'w' not in field.io:
                continue

            # ignore fields that have been pre-resolved
            if key in converted:
                continue

            value = None

            print('>',value, key, field)
            try:
                value = obj[key]
                value = field.convert(value, validate=False)
                print('>>')
            # except ValueError as ve:
            #     raise PotionValidationError(ve, key)
            except KeyError:
                if patch:
                    continue

                if field.default is not None:
                    value = field.default
                elif field.nullable:
                    value = None
                elif key not in self.required and not strict:
                    value = None
                # else:
                #     raise ValidationError('missing-property', property=key)

            converted[field.attribute or key] = value
        #
        # if strict:
        #     unknown_fields = set(object_.keys()) - set(self.fields.keys())
        #     if unknown_fields:
        #         raise ValidationError('unknown-properties', unknown_fields)
        print(converted, 'OUT')
        return converted

    def parse_request(self, request):
        data = request.json

        if not data and request.method in ('GET', 'HEAD'):
            data = {}

            # for name, field in self.fields.items():
            #     # FIXME type conversion!
            #     data[name] = request.args.get(name, type=field.python_type)

        if not self.fields:
            return {}

        return self.convert(data)

