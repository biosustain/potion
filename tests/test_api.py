from flask_potion import Api, fields
from flask_potion.manager import MemoryManager
from flask_potion.resource import Resource
from tests import BaseTestCase


class ApiTestCase(BaseTestCase):
    def setUp(self):
        super(ApiTestCase, self).setUp()
        self.api = Api(self.app)

    def test_api_register_resource(self):
        class BookResource(Resource):
            class Meta:
                name = "book"
                manager = MemoryManager

        self.api.add_resource(BookResource)

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

    def test_api_crud_resource(self):
        class BookResource(Resource):
            class Schema:
                title = fields.String(attribute='name')

            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

        self.api.add_resource(BookResource)

        response = self.client.get("/book/schema")

        print("RESPONSE", response.json)
        self.maxDiff = None
        self.assertEqual({
                             "title": {
                                 "type": "string"
                             },
                             "id": {
                                 "type": "integer",
                                 "minimum": 1,
                                 "readOnly": True
                             }
                         }, response.json['properties'])

        response = self.client.post("/book", data={"title": "Foo"})

        print("RESPONSE", response.data)
        self.assertEqual({
                             "id": 1,
                             "title": "Foo"
                         }, response.json)

        response = self.client.patch("/book/1", data={"title": "Bar"})
        print("RESPONSE", response.data)

        self.assertEqual({
                             "id": 1,
                             "title": "Bar"
                         }, response.json)

        response = self.client.post("/book", data={"title": "Bat"})
        response = self.client.post("/book", data={"title": "Foo"})
        response = self.client.get("/book")
        print("RESPONSE", response.data)
        print("RESPONSE", response.json)

        self.assertEqual([
                             {
                                 "id": 1,
                                 "title": "Bar"
                             },
                             {
                                 "id": 2,
                                 "title": "Bat"
                             },
                             {
                                 "id": 3,
                                 "title": "Foo"
                             }
                         ], response.json)

        print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
        response = self.client.get('/book?where={"title": {"$startswith": "B"}}&sort={"id": true}')
        print("RESPONSE", response.data)

        self.assertEqual([
                             {
                                 "id": 2,
                                 "title": "Bat"
                             },
                             {
                                 "id": 1,
                                 "title": "Bar"
                             }
                         ], response.json)