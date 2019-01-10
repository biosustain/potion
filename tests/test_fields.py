from operator import itemgetter
from unittest import TestCase
from uuid import uuid4
import unittest
from datetime import datetime, date, timedelta
from werkzeug.exceptions import BadRequest
from flask_potion.exceptions import ValidationError
from flask_potion import fields


try:
    from datetime import timezone
except ImportError:
    from datetime import tzinfo

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
        self.assertEqual({"anyOf": [{"$ref": "#/some/other/schema"}, {"type": "null"}]}, foo_ref.response)

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
        self.assertEqual(12, fields.Raw({"type": "number"}).format(12))

    def test_raw_convert(self):
        self.assertEqual(12, fields.Raw({"type": "number"}).convert(12))

    def test_raw_output(self):
        foo = fields.Raw({"type": "number"})
        self.assertEqual(12, foo.output("age", {"age": 12}))

        foo_attribute = fields.Raw({"type": "number"}, attribute="yearsBornAgo")
        self.assertEqual(12.5, foo_attribute.output("age", {"yearsBornAgo": 12.5}))

    def test_array_unique(self):
        foo = fields.Array(fields.Integer, unique=True)

        self.assertEqual([1,2,3], foo.convert([1,2,3]))

        with self.assertRaises(ValidationError):
            self.assertEqual([1,2,3], foo.convert([1,1,2,3]))

    def test_array_default(self):
        foo = fields.Array(fields.Integer)

        self.assertEqual([], foo.default)
        self.assertEqual(True, isinstance(foo.default, list))

    def test_number_convert(self):
        with self.assertRaises(ValidationError):
            fields.Number().convert("nope")

        with self.assertRaises(ValidationError):
            fields.Number(nullable=False).convert(None)

        with self.assertRaises(ValidationError):
            fields.Number(minimum=3).convert(2)

        with self.assertRaises(ValidationError):
            fields.Number(minimum=3, exclusive_minimum=True).convert(3)

        with self.assertRaises(ValidationError):
            fields.Number(maximum=3, exclusive_maximum=True).convert(3)

        self.assertEqual(3, fields.Number(maximum=3).convert(3))
        self.assertEqual(3, fields.Number(minimum=3).convert(3))
        self.assertEqual(None, fields.Number(nullable=True).convert(None))
        self.assertEqual(1.23, fields.Number().convert(1.23))

    def test_date_convert(self):
        with self.assertRaises(ValidationError):
            fields.Date().convert({"$nope": True})

        self.assertEqual(date(2009, 2, 13), fields.Date().convert({"$date": 1234567000000}))
        self.assertEqual({"$date": 1329177600000}, fields.Date().format(date(2012, 2, 14)))

    def test_date_time_convert(self):
        with self.assertRaises(ValidationError):
            fields.DateTime().convert({"$nope": True})

        self.assertEqual(datetime(2009, 2, 13, 23, 16, 40, 0, timezone.utc),
                         fields.DateTime().convert({"$date": 1234567000000}))

        self.assertEqual({"$date": 1329177600000},
                         fields.DateTime().format(datetime(2012, 2, 14, 0, 0, 0, 0, timezone.utc)))

    def test_date_time_string_convert(self):
        with self.assertRaises(ValidationError):
            fields.DateTimeString().convert('01.01.2016')

        self.assertEqual(datetime(2009, 2, 13, 23, 16, 40, 0, timezone.utc),
                         fields.DateTimeString().convert('2009-02-13T23:16:40Z'))

    def test_date_time_string_format(self):
        timestamp = datetime(
            2009, 2, 13, 23, 16, 40, 0, timezone(timedelta(hours=2)))
        self.assertEqual(
            '2009-02-13T23:16:40+02:00',
            fields.DateTimeString().format(timestamp))

    def test_date_time_string_format_default_utc(self):
        timestamp = datetime(2009, 2, 13, 23, 16, 40, 0)
        self.assertEqual(
            '2009-02-13T23:16:40+00:00',
            fields.DateTimeString().format(timestamp))

    def test_uri_convert(self):
        with self.assertRaises(ValidationError):
            fields.Uri().convert('foo bad')

        self.assertEqual('http://www.ietf.org/rfc/rfc2396.txt',
                         fields.Uri().convert('http://www.ietf.org/rfc/rfc2396.txt'))

    def test_uuid_schema(self):
        self.assertEqual({
                            "type": "string",
                            "pattern": "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                            "minLength": 36,
                            "maxLength": 36
                         }, fields.UUID().response)

    def test_uuid_convert(self):
        with self.assertRaises(ValidationError):
            fields.UUID().convert(123456)

        with self.assertRaises(ValidationError):
            fields.UUID().convert("123456")

        with self.assertRaises(ValidationError):
            fields.UUID().convert("abcdefghijklmnopqrstuvwxyz")

        uuid = str(uuid4())
        self.assertEqual(uuid, fields.UUID().convert(uuid))

    def test_string_schema(self):
        self.assertEqual({
                             "type": "string",
                             "minLength": 2,
                             "maxLength": 3,
                             "pattern": "[A-Z][0-9]{1,2}",
                         }, fields.String(min_length=2, max_length=3, pattern="[A-Z][0-9]{1,2}").response)

    def test_string_convert(self):
        with self.assertRaises(ValidationError):
            fields.String(min_length=8).convert("123456")

        with self.assertRaises(ValidationError):
            fields.String(max_length=10).convert("abcdefghijklmnopqrstuvwxyz")

        with self.assertRaises(ValidationError):
            fields.String(pattern="^[fF]oo$").convert("Boo")

        self.assertEqual("foo", fields.String(pattern="^[fF]oo$").convert("foo"))
        self.assertEqual("123456", fields.String().convert("123456"))
        self.assertEqual(None, fields.String(nullable=True).convert(None))

    def test_string_enum(self):
        foo = fields.String(enum=['foo', 'bar'])
        foo_nullable = fields.String(enum=['foo', 'bar'], nullable=True)

        with self.assertRaises(ValidationError):
            foo.convert("fork")

        self.assertEqual("foo", foo.convert("foo"))
        self.assertEqual("foo", foo_nullable.convert("foo"))
        self.assertEqual(None, foo_nullable.convert(None))

    def test_object_convert(self):
        o = fields.Object(fields.Integer, nullable=False)

        self.assertEqual({"x": 123}, o.convert({"x": 123}))

        self.assertEqual(o.request, o.response)
        self.assertEqual({
                             "type": "object",
                             "additionalProperties": {
                                 "type": "integer"
                             }
                         }, o.response)

        with self.assertRaises(ValidationError):
            o.convert({"y": "string"})

        with self.assertRaises(ValidationError):
            o.convert(None)

    # TODO object nullable field

    def test_object_format_any(self):
        o = fields.Object(fields.Any)
        self.assertEqual({"x": 123}, o.format({"x": 123}))

    @unittest.SkipTest
    def test_object_convert_properties(self):
        pass

    def test_object_pattern_schema(self):
        o = fields.Object(fields.Integer, pattern="[A-Z][0-9]+")

        self.assertEqual({
                             "type": "object",
                             "additionalProperties": False,
                             "patternProperties": {
                                 "[A-Z][0-9]+": {"type": "integer"}
                             }
                         }, o.response)

        o = fields.Object(pattern_properties={"[A-Z][0-9]+": fields.Integer})

        self.assertEqual({
                             "type": "object",
                             "additionalProperties": False,
                             "patternProperties": {
                                 "[A-Z][0-9]+": {"type": "integer"}
                             }
                         }, o.response)

    def test_object_convert_pattern(self):
        o = fields.Object(fields.Integer, pattern="[A-Z][0-9]+")

        self.assertEqual({"A3": 1, "B12": 2}, o.convert({"A3": 1, "B12": 2}))

        with self.assertRaises(ValidationError):
            o.convert({"A2": "string"})

        with self.assertRaises(ValidationError):
            o.convert({"Wrong": 1})

    def test_attribute_mapped(self):
        o = fields.AttributeMapped(fields.Object({
            "foo": fields.Integer()
        }), mapping_attribute="key", pattern="[A-Z][0-9]+")

        self.assertEqual([{'foo': 1, 'key': 'A3'}, {'foo': 1, 'key': 'B12'}],
                         sorted(o.convert({"A3": {"foo": 1}, "B12": {"foo": 1}}), key=itemgetter("key")))

        self.assertEqual({"A3": {"foo": 1}, "B12": {"foo": 2}},
                         o.format([{'foo': 1, 'key': 'A3'}, {'foo': 2, 'key': 'B12'}]))

        self.assertEqual({
                             "type": "object",
                             "additionalProperties": False,
                             "patternProperties": {
                                 "[A-Z][0-9]+": {
                                    "additionalProperties": False,
                                     "properties": {
                                         "foo": {"type": "integer"}
                                     },
                                     "type": "object"
                                 }
                             }
                         }, o.response)

    def test_attribute_mapped_no_pattern(self):
        o = fields.AttributeMapped(fields.Object({
            "foo": fields.Integer()
        }), mapping_attribute="key")

        self.assertEqual([{'foo': 1, 'key': 'A3'}, {'foo': 1, 'key': 'B12'}],
                         sorted(o.convert({"A3": {"foo": 1}, "B12": {"foo": 1}}), key=itemgetter("key")))

        self.assertEqual({"A3": {"foo": 1}, "B12": {"foo": 2}},
                         o.format([{'foo': 1, 'key': 'A3'}, {'foo': 2, 'key': 'B12'}]))

        self.assertEqual({
                             "type": "object",
                             "additionalProperties": {
                                 "additionalProperties": False,
                                 "properties": {
                                     "foo": {"type": "integer"}
                                 },
                                 "type": "object"
                             }
                         }, o.response)

    def test_any(self):
        self.assertEqual(3, fields.Any().format(3))
        self.assertEqual('Hi', fields.Any().format('Hi'))
        self.assertEqual(None, fields.Any().format(None))
        self.assertEqual({}, fields.Any().format({}))
        self.assertEqual(1.23, fields.Any().format(1.23))
        self.assertEqual(3, fields.Any().convert(3))
        self.assertEqual('Hi', fields.Any().convert('Hi'))
        self.assertEqual(None, fields.Any().convert(None))
        self.assertEqual(1.23, fields.Any().convert(1.23))
