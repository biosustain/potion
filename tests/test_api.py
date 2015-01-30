from flask_potion import Api, fields
from flask_potion.backends.memory import MemoryManager
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class ApiTestCase(BaseTestCase):
    def test_api_register_resource(self):
        class BookResource(ModelResource):
            class Meta:
                name = "book"
                manager = MemoryManager

        api = Api(self.app)
        api.add_resource(BookResource)

        response = self.client.get("/schema")

        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "definitions": {},
                             "properties": {
                                 "book": {"$ref": "/book/schema#"}
                             }
                         }, response.json)

        response = self.client.get("/book/schema")
        self.assert200(response)

    def test_api_prefix(self):
        api = Api(self.app, prefix='/api/v1')

        class BookResource(ModelResource):
            class Meta:
                name = "book"
                manager = MemoryManager

        api.add_resource(BookResource)

        api.add_resource(BookResource)

        response = self.client.get("/schema")
        self.assert404(response)

        response = self.client.get("/api/v1/schema")

        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "definitions": {},
                             "properties": {
                                 "book": {"$ref": "/api/v1/book/schema#"}
                             }
                         }, response.json)

        response = self.client.get("/api/v1/book/schema")
        self.assert200(response)

    def test_api_crud_resource(self):
        class BookResource(ModelResource):
            class Schema:
                title = fields.String(attribute='name')

            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

        api = Api(self.app)
        api.add_resource(BookResource)

        response = self.client.get("/book/schema")

        self.maxDiff = None
        self.assertEqual({
                             "title": {
                                 "type": "string"
                             },
                             "$uri": {
                                 "type": "string",
                                 'pattern': '^\\/book\\/[^/]+$',
                                 "readOnly": True
                             },
                         }, response.json['properties'])

        response = self.client.post("/book", data={"title": "Foo"})

        self.assertEqual({
                             "$uri": "/book/1",
                             "title": "Foo"
                         }, response.json)

        self.assertEqual({
                             'id': 1,
                             'name': 'Foo'
                         }, BookResource.manager.read(1))

        response = self.client.patch("/book/1", data={"title": "Bar"})

        self.assertEqual({
                             "$uri": "/book/1",
                             "title": "Bar"
                         }, response.json)

        self.client.post("/book", data={"title": "Bat"})
        self.client.post("/book", data={"title": "Foo"})
        response = self.client.get("/book")

        self.assertEqual([
                             {
                                "$uri": "/book/1",
                                 "title": "Bar"
                             },
                             {
                                "$uri": "/book/2",
                                 "title": "Bat"
                             },
                             {
                                "$uri": "/book/3",
                                 "title": "Foo"
                             }
                         ], response.json)

        response = self.client.get('/book?where={"title": {"$startswith": "B"}}')

        self.assertEqual([
                             {
                                 "$uri": "/book/1",
                                 "title": "Bar"
                             },
                             {
                                 "$uri": "/book/2",
                                 "title": "Bat"
                             }
                         ], response.json)

        response = self.client.delete("/book/2")
        self.assertStatus(response, 204)

        response = self.client.patch("/book/1", data={"title": None})
        self.assert400(response)

        self.assertEqual({
                             'status': 400,
                             'message': 'Bad Request',
                             'errors': [
                                 {
                                     'path': ['title'],
                                     'validationOf': {'type': 'string'}
                                 }
                             ],
                         }, response.json)
