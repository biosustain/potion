import unittest
from flask_potion.exceptions import ItemNotFound, ValidationError
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.natural_keys import RefKey, IDKey, PropertiesKey, PropertyKey
from flask_potion import fields
from flask_potion import Api
from flask_potion.resource import Resource, ModelResource
from tests import BaseTestCase

FOO_REFERENCE = {
    "type": "object",
    "properties": {
        "$ref": {
            "type": "string",
            "format": "uri",
            "pattern": "^\/api\/foo\/[^/]+$"
        }
    },
     "additionalProperties": False
}

FOO_REFERENCE_NULLABLE = {
    "type": ["object", "null"],
    "properties": {
        "$ref": {
            "type": "string",
            "format": "uri",
            "pattern": "^\/api\/foo\/[^/]+$"
        }
    },
     "additionalProperties": False
}

class NaturalKeyTestCase(BaseTestCase):

    def setUp(self):
        super(NaturalKeyTestCase, self).setUp()
        self.api = Api(self.app, prefix='/api')

    def test_simple_key(self):
        class Foo(ModelResource):
            class Meta:
                key_converters = [
                    RefKey()
                ]
                model = 'foo'
                manager = MemoryManager

            class Schema:
                inception = fields.ToOne('foo')

        self.api.add_resource(Foo)

        foo_field = fields.ToOne(Foo)

        self.assertJSONEqual(FOO_REFERENCE, foo_field.response)
        self.assertJSONEqual(FOO_REFERENCE, foo_field.request)

    def test_multiple_keys(self):
        with self.assertRaises(RuntimeError) as cx:
            class Bar(ModelResource):
                class Meta:
                    key_converters = (
                        RefKey(),
                        PropertyKey('name')
                    )
                    model = 'bar'
                    natural_key = 'alias'
                    manager = MemoryManager

                class Schema:
                    name = fields.String()
                    alias = fields.String()

            self.api.add_resource(Bar)
        self.assertEqual('Multiple keys of type string defined for bar', cx.exception.args[0])


    def test_property_key(self):
        class Foo(ModelResource):
            class Schema:
                name = fields.String()

            class Meta:
                natural_key = 'name'
                manager = MemoryManager
                model = 'foo'

        self.api.add_resource(Foo)

        foo_field = fields.ToOne(Foo)

        self.assertJSONEqual(FOO_REFERENCE, foo_field.response)
        self.assertJSONEqual({
                                 "anyOf": [
                                     FOO_REFERENCE,
                                     {
                                         "type": "integer"
                                     },
                                     {
                                         "type": "string"
                                     }
                                 ]
                             }, foo_field.request)


        response = self.client.post('/api/foo', data={
            "name": "Jane"
        })
        self.assert200(response)

        response = self.client.post('/api/foo', data={
            "name": "John"
        })
        self.assert200(response)

        self.assertEqual(
            {'id': 2, 'name': 'John'},
            foo_field.convert(2)
        )

        self.assertEqual(
            {'id': 1, 'name': 'Jane'},
            foo_field.convert('Jane')
        )

        with self.assertRaises(ValidationError):
            foo_field.convert(['John'])

        with self.assertRaises(ItemNotFound) as cx:
            foo_field.convert('Joanne')

        self.assertEqual({
            "message": "Not Found",
            "status": 404,
            "item": {
                "$type": "foo",
                "$where": {
                    "name": "Joanne"
                }
            }
        }, cx.exception.as_dict())

    def test_properties_key(self):
        class Foo(ModelResource):
            class Schema:
                first_name = fields.String()
                last_name = fields.String()

            class Meta:
                natural_key = ['first_name', 'last_name']
                manager = MemoryManager
                model = 'foo'
                name = 'foo'

        self.api.add_resource(Foo)

        foo_field = fields.ToOne(Foo, nullable=True)

        self.assertJSONEqual(FOO_REFERENCE_NULLABLE, foo_field.response)
        self.assertJSONEqual({
                                 "anyOf": [
                                     FOO_REFERENCE,
                                     {
                                         "type": "integer"
                                     },
                                     {
                                         "type": "array",
                                         "items": [{"type": "string"}, {"type": "string"}],
                                         "additionalItems": False
                                     },
                                     {
                                         "type": "null"
                                     }
                                 ]
                             }, foo_field.request)

        response = self.client.post('/api/foo', data={
            "first_name": "Jane",
            "last_name": "Doe"
        })
        self.assert200(response)

        response = self.client.post('/api/foo', data={
            "first_name": "John",
            "last_name": "Doe"
        })
        self.assert200(response)

        self.assertEqual(
            {'first_name': 'Jane', 'id': 1, 'last_name': 'Doe'},
            foo_field.convert(1)
        )

        self.assertEqual(
            {'first_name': 'John', 'id': 2, 'last_name': 'Doe'},
            foo_field.convert(['John', 'Doe'])
        )

        self.assertEqual(
            {'first_name': 'John', 'id': 2, 'last_name': 'Doe'},
            foo_field.convert({"$ref": "/api/foo/2"})
        )

        with self.assertRaises(ItemNotFound) as cx:
            foo_field.convert(['John', 'Joe'])

        self.assertEqual({
            "message": "Not Found",
            "status": 404,
            "item": {
                "$type": "foo",
                "$where": {
                    "first_name": "John",
                    "last_name": "Joe"
                }
            }
        }, cx.exception.as_dict())

        with self.assertRaises(ValidationError):
            foo_field.convert(['John', None])
