import json
from flask.ext.potion import fields
from flask.ext.potion.resource import PotionResource
from flask.ext.potion.routes import Route, MethodRoute, DeferredSchema
from flask.ext.potion.schema import FieldSet, Schema
from tests import BaseTestCase


class RouteTestCase(BaseTestCase):
    def test_route(self):
        class FooResource(PotionResource):
            class Meta:
                name = 'foo'

        route = Route(lambda resource: {
            'success': True,
            'boundToResource': resource.meta.name
        }, rule='/test', rel='test')

        view = route.view_factory('', FooResource)

        with self.app.test_request_context('/foo/test'):
            self.assertEqual({'success': True, 'boundToResource': 'foo'}, view())


class ResourceTestCase(BaseTestCase):
    def test_potion_resource(self):
        class FooResource(PotionResource):
            class Meta:
                title = 'Foo bar'

        self.assertEqual(['schema'], list(FooResource.routes.keys()))
        self.assertEqual(None, FooResource.schema)
        self.assertEqual('Foo bar', FooResource.meta.title)
        self.assertEqual('fooresource', FooResource.meta.name)
        self.assertEqual(None, FooResource.meta.description)

        data, code, headers = FooResource().schema_route()
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
        class FooResource(PotionResource):
            @Route.POST()
            def foo(self):
                return True

            foo.response_schema = fields.Boolean()

            class Meta:
                name = 'foo'

        data, code, headers = FooResource().schema_route()
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
        class FooResource(PotionResource):
            @Route.GET(lambda r: '/<{}:id>'.format(r.meta.id_converter), rel="self")
            def read(self, id):
                return {"id": id}

            read.response_schema = fields.Object({"id": fields.Integer()})

            class Meta:
                name = 'foo'
                id_converter = 'int'

        self.assertEqual('/foo/<int:id>', FooResource.read.rule_factory(FooResource))

        data, code, headers = FooResource().schema_route()
        self.assertJSONEqual({
                                 "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                                 "links": [
                                     {
                                         "rel": "describedBy",
                                         "href": "schema",
                                         "method": "GET"
                                     },
                                     {
                                         "rel": "self",
                                         "href": "{id}",
                                         "method": "GET",
                                         "targetSchema": {
                                             "type": "object",
                                             "properties": {
                                                 "id": {
                                                     "type": "integer",
                                                     "default": 0
                                                 }
                                             },
                                             "additionalProperties": False
                                         }
                                     }
                                 ]
                             }, data)

    def test_resource_method_route(self):
        class FooResource(PotionResource):
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

        data, code, headers = FooResource().schema_route()
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
        class UserResource(PotionResource):

            @Route.GET('/<int:id>', rel="self")
            def read(self, id):
                return {"name": "Foo", "age": 123}

            read.response_schema = DeferredSchema(fields.Inline, "self")

            class Schema:
                name = fields.String()
                age = fields.Integer()

            class Meta:
                name = 'user'

        data, code, headers = UserResource().schema_route()
        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "type": "object",
                             "properties": {
                                 "name": {
                                     "type": "string"
                                 },
                                 "age": {
                                     "type": "integer",
                                     "default": 0
                                 }
                             },
                             "links": [
                                 {
                                     "rel": "describedBy",
                                     "href": "schema",
                                     "method": "GET"
                                 },
                                 {
                                     "rel": "self",
                                     "href": "{id}",
                                     "method": "GET",
                                     "targetSchema": {  # FIXME not needed if rel == "self"
                                         "$ref": "#"
                                     }
                                 }
                             ]
                         }, data)
