from unittest import TestCase
from flask import Flask, request, Request
from flask_potion import fields, Resource
from flask_potion.exceptions import ValidationError
from flask_potion.schema import Schema, FieldSet, RequestMustBeJSON
from sys import version_info
if version_info.major < 3:
    from StringIO import StringIO
else:
    from io import StringIO

class SchemaTestCase(TestCase):

    def test_schema_class(self):
        class FooSchema(Schema):

            def __init__(self, schema):
                self._schema = schema

            def schema(self):
                return self._schema

        foo_response = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "createdAt": {"type": "string", "format": "date-time"}
            }
        }

        foo_request = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 3},
                "properties": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                }
            }
        }

        foo = FooSchema((foo_response, foo_request))
        bar = FooSchema({"type": "boolean"})

        self.assertEqual(foo_request, foo.request)
        self.assertEqual(foo_response, foo.response)
        self.assertEqual({"type": "boolean"}, bar.request)
        self.assertEqual({"type": "boolean"}, bar.response)
        self.assertEqual({"name": "Foo foo"}, foo.format({"name": "Foo foo"}))
        self.assertEqual(False, bar.format(False))
        self.assertEqual(True, bar.convert(True))

        with self.assertRaises(ValidationError) as cx:
            bar.convert("True")

        self.assertEqual({
            "name": "Foo",
            "properties": {
                "is": "foo"
            }
        }, foo.convert({
            "name": "Foo",
            "properties": {
                "is": "foo"
            }
        }))

        with Flask(__name__).app_context():
            with self.assertRaises(ValidationError) as cx:
                foo.convert({
                    "name": "Foo",
                    "properties": {
                        "age": 12
                    }})

            self.assertEqual({
                                 'errors': [
                                     {
                                         'path': ('properties', 'age'),
                                         'validationOf': {'type': 'string'}
                                     }
                                 ],
                                 'message': 'Bad Request',
                                 'status': 400
                             }, cx.exception.as_dict())


    def test_schema_class_parse_request(self):
        pass

    def test_schema_class_format_response(self):
        pass

    def test_fieldset_schema(self):
        pass

    def test_fieldset_rebind(self):
        class FooResource(Resource):
            pass
        class BarResource(Resource):
            pass

        FieldSet({"foo": fields.String()}).bind(FooResource).bind(BarResource)

    def test_fieldset_parse_request(self):
        app = Flask(__name__)
        env = {}
        with app.test_request_context():
            env = request.environ

        # Ensure allow empty POST
        fs = FieldSet(None)
        env['REQUEST_METHOD'] = 'POST'
        fs.parse_request(Request(env))

        # Ensure failure when there are fields
        fs = FieldSet({'field': fields.String()})
        with self.assertRaises(RequestMustBeJSON):
            fs.parse_request(Request(env))

        # Successful POST with data
        env['wsgi.input'] = StringIO('{"field": "data"}')
        env['CONTENT_TYPE'] = 'application/json'
        env['CONTENT_LENGTH'] = '17'
        fs.parse_request(Request(env))

    def test_fieldset_format(self):
        self.assertEqual(
            {"number": 42, "constant": "constant"},
            FieldSet({
                "number": fields.Number(),
                "constant": fields.String(io='r'),
                "secret": fields.String(io='w'),
            }).format({"number": 42, "constant": "constant", "secret": "secret"})
        )

    def test_fieldset_schema_io(self):
        fs = FieldSet({
            "id": fields.Number(io='r'),
            "name": fields.String(),
            "secret": fields.String(io='c'),
            "updateOnly": fields.String(io='u'),
        })

        self.assertEqual(
            {
                "type": "object",
                "properties": {
                    "id": {"type": "number", "readOnly": True},
                    "name": {"type": "string"},
                }
            }, fs.response)

        self.assertEqual(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "updateOnly": {"type": "string"}
                }
            }, fs.update)

        self.assertEqual(
            {
                "name": {"type": "string"},
                "secret": {"type": "string"}
            }, fs.create['properties'])

        self.assertEqual({"name", "secret"}, set(fs.create['required']))

    def test_fieldset_format_response(self):
        pass
