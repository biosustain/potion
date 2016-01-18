from flask_potion.contrib.memory import MemoryManager
from flask_potion import fields, Api, Resource, ModelResource
from tests import BaseTestCase


class ModelResourceTestCase(BaseTestCase):

    def setUp(self):
        super(ModelResourceTestCase, self).setUp()
        self.api = Api(self.app, default_manager=MemoryManager)

    def test_schema_io(self):

        class FooResource(ModelResource):
            class Schema:
                name = fields.String()
                secret = fields.String(io="c")
                slug = fields.String(io="cr")

            class Meta:
                name = "foo"

        self.api.add_resource(FooResource)

        response = self.client.post("/foo", data={
            "name": "Foo",
            "secret": "mystery",
            "slug": "foo"
        })

        self.assert200(response)
        self.assertEqual({
            "$uri": "/foo/1", 
            "name": "Foo",
            "slug": "foo"
        }, response.json)

        self.assertEqual({
            "id": 1,
            "name": "Foo",
            "slug": "foo",
            "secret": "mystery"
        }, FooResource.manager.items[1])

        response = self.client.patch("/foo/1", data={
            "name": "Bar",
            "secret": "123456"
        })

        self.assert400(response)

        response = self.client.patch("/foo/1", data={
            "name": "Bar"
        })

        self.assert200(response)

        self.assertEqual({
            "$uri": "/foo/1",
            "name": "Bar",
            "slug": "foo"
        }, response.json)

        self.assertEqual({
            "id": 1,
            "name": "Bar",
            "slug": "foo",
            "secret": "mystery"
        }, FooResource.manager.items[1])
