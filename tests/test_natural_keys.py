from flask_potion.backends.memory import MemoryManager
from flask_potion.natural_keys import PropertyResolver, IDResolver
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


class NaturalKeyTestCase(BaseTestCase):
    def setUp(self):
        super(NaturalKeyTestCase, self).setUp()
        self.api = Api(self.app, prefix='/api')

    def test_simple_key(self):
        class Foo(Resource):
            class Schema:
                inception = fields.ToOne('foo')

        self.api.add_resource(Foo)

        print(Foo.schema.schema())
        self.maxDiff = None

        self.assertJSONEqual(FOO_REFERENCE, Foo.schema.response['properties']['inception'])

        self.assertJSONEqual(FOO_REFERENCE, Foo.schema.request['properties']['inception'])

    def test_property_key(self):
        class Foo(ModelResource):
            class Schema:
                name = fields.String()
                inception = fields.ToOne('foo')

            class Meta:
                natural_keys = [
                    PropertyResolver('name')
                ]
                manager = MemoryManager
                model = 'foo'

        self.api.add_resource(Foo)

        self.assertJSONEqual(FOO_REFERENCE, Foo.schema.response['properties']['inception'])

        self.assertJSONEqual({
                                 "anyOf": [
                                     FOO_REFERENCE,
                                     {
                                         "type": "string"
                                     }
                                 ]
                             }, Foo.schema.request['properties']['inception'])


    def test_multiple_property_keys(self):
        class Foo(ModelResource):
            class Schema:
                name = fields.String()
                inception = fields.ToOne('foo')

            class Meta:
                natural_keys = [
                    IDResolver(),
                    PropertyResolver('name')
                ]
                manager = MemoryManager
                model = 'foo'

        self.api.add_resource(Foo)

        print(Foo.schema.schema())
        self.maxDiff = None

        self.assertJSONEqual(FOO_REFERENCE, Foo.schema.response['properties']['inception'])

        self.assertJSONEqual({
                                 "anyOf": [
                                     FOO_REFERENCE,
                                     {
                                         "minimum": 1,
                                         "readOnly": True,  # TODO FIXME strip "readOnly"
                                         "type": "integer"
                                     },
                                     {
                                         "type": "string"
                                     }
                                 ]
                             }, Foo.schema.request['properties']['inception'])

        # TODO test resolving
