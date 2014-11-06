from collections import OrderedDict
from werkzeug.utils import cached_property
from flask.ext.potion.errors import ValidationError
from .util import unpack


class Schema(object):

    @property
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

    def format(self, data):
        return data

    def convert(self, data):
        pass # TODO validate

    def parse_request(self, request):
        data = request.json

        return self.convert(data)

    def format_response(self, response):
        data, code, headers = unpack(response)
        # TODO omit formatting on certain codes.
        return self.format(data), code, headers


class FieldSet(Schema):

    def __init__(self, fields, required_fields=None, read_only_fields=None):
        self.fields = fields
        self.required = required_fields or ()
        self.read_only_override = read_only_fields or ()

    def schema(self):
        response_schema = {
            "type": "object",
            "properties": OrderedDict((
                (key, field.response_schema) for key, field in self.fields.items() if 'r' in field.io
            ))
        }

        request_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": OrderedDict((
                (key, field.request_schema) for key, field in self.fields.items()
                if 'w' in field.io and key not in self.read_only_override
            ))
        }

        if self.required:
            request_schema['required'] = list(self.required)

        return response_schema, request_schema

    def format(self, item):
        return OrderedDict((
            (key, field.output(key, item)),
            for key, field in self.fields.items()
        ))

    def convert(self, object_, pre_resolved_properties=None, patch=False, strict=False):
        converted = dict(pre_resolved_properties) if pre_resolved_properties else {}

        for key, field in self.fields.items():
            if 'w' not in field.io or key in self.read_only_override:
                continue

            # ignore fields that have been pre-resolved
            if key in converted:
                continue

            value = None

            try:
                value = object_[key]
                field.validate(value)
            except ValueError as e:
                raise ValidationError('invalid-property', property=key, schema_trace=e.args[0])
            except KeyError:
                if patch:
                    continue

                if field.default is not None:
                    value = field.default
                elif field.nullable:
                    value = None
                elif key not in self.required and not strict:
                    value = None
                else:
                    raise ValidationError('missing-property', property=key)

            converted[field.attribute or key] = field.convert(value)

        if strict:
            unknown_fields = set(object_.keys()) - set(self.fields.keys())
            if unknown_fields:
                raise ValidationError('unknown-properties', unknown_fields)

        return converted

    def parse_request(self, request):
        data = request.json

        if not data and request.method in ('GET', 'HEAD'):
            data = {}

            for name, field in self.fields.items():
                # FIXME type conversion!
                data[name] = request.args.get(name, type=field.python_type)

        if not self.fields:
            return {}

        return self.convert(data)

