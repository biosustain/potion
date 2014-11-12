from unittest import TestCase
from flask.ext.potion import fields


class FieldsTestCase(TestCase):
    def test_raw_schema(self):
        foo = fields.Raw({"type": "string"})

        self.assertEqual({"type": "string"}, foo.response)
        self.assertEqual({"type": "string"}, foo.request)

        # NOTE format is (response, request)
        foo_rw = fields.Raw((
            {"type": "string"},
            {"type": "number"}
        ))
        self.assertEqual({"type": "string"}, foo_rw.response)
        self.assertEqual({"type": "number"}, foo_rw.request)

        type_, foo_callable = None, fields.Raw(lambda: {"type": type_})
        type_ = "boolean"
        self.assertEqual({"type": "boolean"}, foo_callable.response)

    def test_raw_nullable(self):
        foo_type_string = fields.Raw({"type": "string"}, nullable=True)
        self.assertEqual({"type": ["string", "null"]}, foo_type_string.response)

        foo_rw = fields.Raw(({"type": "string"}, {"type": "number"}), nullable=True)
        self.assertEqual({"type": ["string", "null"]}, foo_rw.response)
        self.assertEqual({"type": ["number", "null"]}, foo_rw.request)

        foo_type_array = fields.Raw({"type": ["string", "number"]}, nullable=True)
        self.assertEqual({"type": ["string", "number", "null"]}, foo_type_array.response)

        foo_one_of = fields.Raw({
                                    "oneOf": [
                                        {"type": "string", "minLength": 5},
                                        {"type": "string", "maxLength": 3}
                                    ]
                                }, nullable=True)
        self.assertEqual({
                                    "oneOf": [
                                        {"type": "string", "minLength": 5},
                                        {"type": "string", "maxLength": 3},
                                        {"type": "null"}
                                    ]
                                }, foo_one_of.response)

        foo_any_of = fields.Raw(
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "string", "maxLength": 3}
                ]
            }, nullable=True)
        self.assertEqual(
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "string", "maxLength": 3},
                    {"type": "null"}
                ]
            }, foo_any_of.response)

        foo_ref = fields.Raw({"$ref": "#/some/other/schema"}, nullable=True)
        self.assertEqual({'anyOf': [{'$ref': '#/some/other/schema'}, {'type': 'null'}]}, foo_ref.response)

    def test_raw_default(self):
        foo = fields.Raw({"type": "string"}, default="Foo")
        self.assertEqual({"default": "Foo", "type": "string"}, foo.response)

    def test_raw_title(self):
        foofy = fields.Raw({"type": "string"}, title="How to call your foo")
        self.assertEqual({"title": "How to call your foo", "type": "string"}, foofy.response)

    def test_raw_description(self):
        foo = fields.Raw({"type": "string"}, description="Foo bar")
        self.assertEqual({"description": "Foo bar", "type": "string"}, foo.response)

    def test_raw_io(self):
        foo = fields.Raw({"type": "number"}, io="r")
        self.assertEqual("r", foo.io)

    def test_raw_format(self):
        pass

    def test_raw_convert(self):
        pass

    def test_raw_output(self):
        pass

