from functools import wraps

from flask_potion.routes import Route, ItemRoute
from flask_potion import Api, fields
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.resource import ModelResource, Resource
from tests import BaseTestCase


class ApiTestCase(BaseTestCase):
    def test_api_register_resource(self):
        class BookResource(ModelResource):
            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

        api = Api(self.app)
        api.add_resource(BookResource)

        response = self.client.get("/schema")

        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "properties": {
                                 "book": {"$ref": "/book/schema#"}
                             }
                         }, response.json)

        response = self.client.get("/book/schema")
        self.assert200(response)

    def test_api_schema(self):
        api = Api(self.app, title="Welcome to Foo API!", description="...")

        response = self.client.get("/schema")
        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "title": "Welcome to Foo API!",
                             "description": "...",
                             "properties": {}
                         }, response.json)

    def test_api_prefix(self):
        api = Api(self.app, prefix='/api/v1')

        class BookResource(ModelResource):
            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

            @Route.GET
            def genres(self):
                return ['fiction', 'non-fiction']

            @ItemRoute.GET
            def rating(self):
                return 4.5

        api.add_resource(BookResource)

        response = self.client.get("/schema")
        self.assert404(response)

        response = self.client.get("/api/v1/schema")

        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "properties": {
                                 "book": {"$ref": "/api/v1/book/schema#"}
                             }
                         }, response.json)

        response = self.client.get("/api/v1/book/schema")
        self.assert200(response)
        self.assertEqual({
                    "/api/v1/book",
                    "/api/v1/book/schema",
                    "/api/v1/book/genres",
                    "/api/v1/book/{id}",
                    "/api/v1/book/{id}/rating"
                 }, {l['href'] for l in response.json['links']})

    def test_schema_decoration(self):
        def is_teapot(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return '', 418, {}
            return wrapper

        api = Api(self.app, decorators=[is_teapot])

        class FooResource(Resource):
            class Meta:
                name = 'foo'

        api.add_resource(FooResource)

        response = self.client.get("/schema")
        self.assertEqual(response.status_code, 418)

        response = self.client.get("/foo/schema")
        self.assertEqual(response.status_code, 418)

    def test_schema_decoration_disable(self):
        def is_teapot(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return '', 418, {}

            return wrapper

        self.app.config['POTION_DECORATE_SCHEMA_ENDPOINTS'] = False
        api = Api(self.app, decorators=[is_teapot])

        class FooResource(Resource):
            class Meta:
                name = 'foo'

        api.add_resource(FooResource)

        response = self.client.get("/schema")
        self.assert200(response)

        response = self.client.get("/foo/schema")
        self.assert200(response)

    def test_api_crud_resource(self):
        class BookResource(ModelResource):
            class Schema:
                title = fields.String(attribute='name')

            class Meta:
                name = "book"
                model = "book"
                manager = MemoryManager

        self.assertEqual('id', BookResource.manager.id_attribute)

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
                                     'validationOf': {'type': 'string'},
                                     'message': "None is not of type 'string'"
                                 }
                             ],
                         }, response.json)

        self.app.debug = False

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
