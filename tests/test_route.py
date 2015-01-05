import json
from flask_potion import fields, Api
from flask_potion.resource import Resource
from flask_potion.routes import Route, DeferredSchema
from flask_potion.schema import FieldSet, Schema
from tests import BaseTestCase


class RouteTestCase(BaseTestCase):
    def test_route(self):
        class FooResource(Resource):
            class Meta:
                name = 'foo'

        route = Route(rule='/test')
        route.GET(rel='test')(lambda resource: {
            'success': True,
            'boundToResource': resource.meta.name
        })

        view = route.view_factory('', FooResource)

        with self.app.test_request_context('/foo/test'):
            self.assertEqual({'success': True, 'boundToResource': 'foo'}, view())


class ResourceTestCase(BaseTestCase):
    def test_potion_resource(self):
        class FooResource(Resource):
            class Meta:
                title = 'Foo bar'

        self.assertEqual(['schema'], list(FooResource.routes.keys()))
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
                                         "rel": "describedBy",
                                         "href": "schema",
                                         "method": "GET"
                                     },
                                     {
                                         "rel": "foo",
                                         "href": "foo",
                                         "method": "POST",
                                         "targetSchema": {
                                             "type": "boolean"
                                         }
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

        Api().add_resource(FooResource)
        self.assertEqual('/foo/<int:id>', FooResource.read.rule_factory(FooResource))

        data, code, headers = FooResource().described_by()
        self.assertJSONEqual({
                                 "rel": "self",
                                 "href": "{id}",
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
        self.assertJSONEqual({
                                 "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                                 "links": [
                                     {
                                         "rel": "GET_bar",
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
                                     {
                                         "rel": "POST_bar",
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
                                     }
                                 ]
                             }, data)


    def test_resource_schema(self):
        class UserResource(Resource):
            @Route.GET('/<int:id>', rel="self")
            def read(self, id):
                return {"name": "Foo", "age": 123}

            read.response_schema = DeferredSchema(fields.Inline, "self")

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
