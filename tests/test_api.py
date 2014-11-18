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
                title = fields.String()

            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

        self.api.add_resource(BookResource)

        response = self.client.get("/book/schema")

        print("RESPONSE", response.json)
        self.maxDiff = None
        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "type": "object",
                             "properties": {
                                 "title": {
                                     "type": "string"
                                 },
                                 "id": {
                                     "type": "integer",
                                     "minimum": 1,
                                     "readOnly": True
                                 }
                             },
                             "links": [
                                 {
                                     "method": "POST",
                                     "rel": "create",
                                     "schema": {"$ref": "#"},
                                     "targetSchema": {"$ref": "#"},
                                     "href": "" # TODO /api/book or .
                                 },
                                 {
                                     "method": "GET",
                                     "rel": "describedBy",
                                     "href": "schema"
                                 },
                                 {
                                     "method": "DELETE",
                                     "rel": "destroy",
                                     "href": "{id}"
                                 },
                                 {
                                     "method": "GET",
                                     "rel": "instances",
                                     "schema": {
                                         "additionalProperties": False,
                                         "type": "object",
                                         "properties": {  # TODO
                                                          "page": {
                                                              "type": "integer"
                                                          },
                                                          "sort": {
                                                              "type": "string"
                                                          },
                                                          "per_page": {
                                                              "type": "integer"
                                                          },
                                                          "where": {
                                                              "type": "string"
                                                          }
                                         }
                                     },
                                     "targetSchema": {"TODO": True},
                                     "href": ""
                                 },
                                 {
                                     "targetSchema": {"$ref": "#"},
                                     "method": "GET",
                                     "rel": "self",
                                     "href": "{id}"
                                 },
                                 {
                                     "schema": {"$ref": "#"},
                                     "method": "PATCH",
                                     "rel": "update",
                                     "targetSchema": {"$ref": "#"}, # TODO different schema without required fields
                                     "href": "{id}"
                                 }
                             ]
                         }, response.json)

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
        response = self.client.get("/book")
        print("RESPONSE", response.data)

        self.assertEqual([
                             {
                                 "id": 1,
                                 "title": "Bar"
                             },
                             {
                                 "id": 2,
                                 "title": "Bat"
                             }
                         ], response.json)
