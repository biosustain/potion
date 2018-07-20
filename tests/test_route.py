import json
from operator import itemgetter
from six import wraps
from werkzeug.exceptions import Unauthorized
from flask_potion import fields, Api
from flask_potion.resource import Resource
from flask_potion.routes import Route
from flask_potion.schema import FieldSet, Schema
from tests import BaseTestCase


class RouteTestCase(BaseTestCase):
    def test_route(self):
        class FooResource(Resource):
            class Meta:
                name = 'foo'

        route = Route(rule='/test')
        route = route.GET(rel='test')(lambda resource: {
            'success': True,
            'boundToResource': resource.meta.name
        })

        view = route.view_factory('', FooResource)

        with self.app.test_request_context('/foo/test'):
            self.assertEqual({'success': True, 'boundToResource': 'foo'}, view())

    def test_route_schema(self):
        route = Route.GET(title="foo", description="bar")(lambda *args, **kwargs: None)
        route.attribute = 'attr'

        self.assertEqual({
            "description": "bar",
            "href": "attr",
            "method": "GET",
            "rel": "readAttr",
            "title": "foo"
        }, route.schema_factory(Resource))

    def test_route_success_code(self):
        route = Route.GET(success_code=201, rule='/test')(lambda *args, **kwargs: None)
        view = route.view_factory('', Resource)

        self.assertEqual((None, 201), view())


class ResourceTestCase(BaseTestCase):
    def test_potion_resource(self):
        class FooResource(Resource):
            class Meta:
                title = 'Foo bar'

        self.assertEqual(['describedBy'], list(FooResource.routes.keys()))
        self.assertEqual(None, FooResource.schema)
        self.assertEqual('Foo bar', FooResource.meta.title)
        self.assertEqual('fooresource', FooResource.meta.name)
        self.assertEqual(None, FooResource.meta.description)

        data, code, headers = FooResource().described_by()
        self.assertEqual({'Content-Type': 'application/schema+json'}, headers)
        self.assertEqual(200, code)
        self.assertJSONEqual({
            "$schema": "http://json-schema.org/draft-04/hyper-schema#",
            "title": "Foo bar",
            "links": [
                {
                    "rel": "describedBy",
                    "href": "schema",
                    "method": "GET"
                }
            ]
        }, data)


    def test_resource_simple_route(self):
        class FooResource(Resource):
            @Route.POST()
            def foo(self):
                return True

            foo.response_schema = fields.Boolean()

            class Meta:
                name = 'foo'

        data, code, headers = FooResource().described_by()
        self.assertJSONEqual({
            "$schema": "http://json-schema.org/draft-04/hyper-schema#",
            "links": [
                {
                    "rel": "createFoo",
                    "href": "foo",
                    "method": "POST",
                    "targetSchema": {
                        "type": "boolean"
                    }
                },
                {
                    "rel": "describedBy",
                    "href": "schema",
                    "method": "GET"
                }
            ]
        }, data)

    def test_resource_route_rule_resolution(self):
        class FooResource(Resource):
            @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter), rel="self")
            def read(self, id):
                return {"id": id}

            read.response_schema = fields.Object({"id": fields.Integer()})

            class Meta:
                name = 'foo'
                id_converter = 'int'

        Api(prefix="/v1").add_resource(FooResource)
        self.assertEqual('/v1/foo/<int:id>', FooResource.read.rule_factory(FooResource))
        self.assertEqual('<int:id>', FooResource.read.rule_factory(FooResource, True))

        data, code, headers = FooResource().described_by()
        self.assertJSONEqual({
            "rel": "self",
            "href": "/v1/foo/{id}",
            "method": "GET",
            "targetSchema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer"
                    }
                },
                "additionalProperties": False
            }
        }, data["links"][1])

    def test_resource_method_route(self):
        class FooResource(Resource):
            @Route.POST()
            def bar(self, value):
                pass

            bar.request_schema = FieldSet({"value": fields.Boolean(nullable=True)})

            @bar.GET()
            def bar(self):
                pass

            bar.response_schema = FieldSet({"value": fields.Boolean(nullable=True)})

            class Meta:
                name = 'foo'

        data, code, headers = FooResource().described_by()
        self.assertJSONEqual([
            {
                "rel": "createBar",
                "href": "bar",
                "method": "POST",
                "schema": {
                    "additionalProperties": False,
                    "properties": {
                        "value": {
                            "type": [
                                "boolean",
                                "null"
                            ]
                        }
                    },
                    "type": "object"
                }
            },
            {
                "rel": "describedBy",
                "href": "schema",
                "method": "GET"
            },
            {
                "rel": "readBar",
                "href": "bar",
                "method": "GET",
                "targetSchema": {
                    "properties": {
                        "value": {
                            "type": [
                                "boolean",
                                "null"
                            ]
                        }
                    },
                    "type": "object"
                }
            },
        ], sorted(data['links'], key=itemgetter('rel')))

    def test_route_replace(self):
        class FooResource(Resource):
            @Route.GET('', rel='read')
            def read(self):
                return 'read-foo'

            @read.POST(rel='create')
            def create(self):
                return 'foo'

            class Meta:
                name = 'foo'

        class BarResource(FooResource):

            @Route.POST('', rel='create')
            def create(self):
                return 'bar'

            class Meta:
                name = 'bar'

        self.assertEqual({
            'read': FooResource.read,
            'describedBy': FooResource.described_by,
            'create': FooResource.create
        }, FooResource.routes)

        self.assertEqual({
            'read': FooResource.read,
            'describedBy': BarResource.described_by,
            'create': BarResource.create
        }, BarResource.routes)

        self.assertEqual('foo', FooResource().create())
        self.assertEqual('bar', BarResource().create())

    def test_route_decorator(self):

        def unauthorize(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                raise Unauthorized()
            return wrapper

        def denormalize(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return 'not ' + fn(*args, **kwargs)
            return wrapper

        class FooResource(Resource):

            @Route.GET
            def no_decorator(self):
                return 'normal'

            @Route.GET
            def simple_decorator(self):
                return 'normal'

            @Route.GET
            def unauthorize_decorator(self):
                return 'normal'

            class Meta:
                name = 'foo'
                title = 'Foo bar'
                route_decorators = {
                    'readSimpleDecorator': denormalize,
                    'readUnauthorizeDecorator': unauthorize
                }

        self.assertEqual('normal', FooResource().no_decorator())
        self.assertEqual('normal', FooResource().simple_decorator())
        self.assertEqual('normal', FooResource().unauthorize_decorator())

        api = Api(self.app)
        api.add_resource(FooResource)

        response = self.client.get("/foo/no-decorator")
        self.assertEqual('normal', response.json)

        response = self.client.get("/foo/simple-decorator")
        self.assertEqual('not normal', response.json)

        response = self.client.get("/foo/unauthorize-decorator")
        self.assert401(response)

    def test_route_success_code(self):
        class FooResource(Resource):
            @Route.GET(success_code=201)
            def foo(self):
                return 'foo'

            class Meta:
                name = 'foo'

        api = Api(self.app)
        api.add_resource(FooResource)

        foo = self.app

        response = self.client.get("/foo/foo")
        self.assertEqual(201, response.status_code)
        self.assertEqual('foo', response.json)

    def test_route_disabling(self):

        class FooResource(Resource):
            @Route.GET
            def foo(self):
                return 'foo'

            @Route.GET
            def baz(self):
                return 'baz'

            @baz.POST
            def baz(self, value):
                return 'baz: {}'.format(value)

            baz.request_schema = fields.String()

            class Meta:
                name = 'foo'
                exclude_routes = ('readBaz',)

        class BarResource(FooResource):
            class Meta:
                name = 'bar'

        class BazResource(BarResource):
            class Meta:
                name = 'baz'
                exclude_routes = ('readFoo',)

        api = Api(self.app)
        api.add_resource(FooResource)
        api.add_resource(BarResource)
        api.add_resource(BazResource)

        self.assertEqual({
            'describedBy': Resource.described_by,
            'readFoo': FooResource.foo,
            'createBaz': FooResource.baz
        }, FooResource.routes)

        self.assertEqual({
            'describedBy': Resource.described_by,
            'readFoo': FooResource.foo,
            'createBaz': FooResource.baz
        }, BarResource.routes)

        self.assertIsNone(BazResource.routes.get('readFoo', None))
        self.assertIsNotNone(BazResource.routes.get('readBaz', None))
        self.assertIsNotNone(BazResource.routes.get('createBaz', None))

        response = self.client.get("/foo/foo")
        self.assertEqual('foo', response.json)

        response = self.client.get("/foo/baz")
        self.assert405(response)

        response = self.client.get("/bar/foo")
        self.assert200(response)
        self.assertEqual('foo', response.json)

        response = self.client.get("/bar/baz")
        self.assert405(response)

        response = self.client.post("/bar/baz", data='xyz', force_json=True)
        self.assert200(response)
        self.assertEqual('baz: xyz', response.json)

        response = self.client.get("/baz/foo")
        self.assert404(response)

        response = self.client.get("/baz/baz")
        self.assertEqual('baz', response.json)

        response = self.client.post("/baz/baz", data='123', force_json=True)
        self.assert200(response)
        self.assertEqual('baz: 123', response.json)


    def test_resource_schema(self):
        class UserResource(Resource):
            @Route.GET('/<int:id>', rel="self")
            def read(self, id):
                return {"name": "Foo", "age": 123}

            read.response_schema = fields.Inline("self")

            class Schema:
                name = fields.String()
                age = fields.PositiveInteger(nullable=True)

            class Meta:
                name = 'user'

        data, code, headers = UserResource().described_by()
        self.assertEqual({
            "name": {
                "type": "string"
            },
            "age": {
                "type": ["integer", "null"],
                "minimum": 1
            }
        }, data["properties"])
