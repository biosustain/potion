from unittest import TestCase
from flask_potion.exceptions import ValidationError
from flask_potion.schema import Schema


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

    def test_fieldset_parse_request(self):
        pass


    def test_fieldset_format_response(self):
        pass
