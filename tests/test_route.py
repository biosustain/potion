from flask.ext.potion import fields
from flask.ext.potion.resource import PotionResource
from flask.ext.potion.routes import Route, MethodRoute
from flask.ext.potion.schema import FieldSet, Schema
from tests import BaseTestCase


class RouteTestCase(BaseTestCase):
    def test_route(self):

        class FooResource(PotionResource):
            class Meta:
                name = 'foo'

        route = Route(lambda resource: {
            'success': True,
            'boundToResource': resource.meta['name']
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
                                     "href": "/schema",
                                     "method": "GET",
                                     "schema": {
                                         "additionalProperties": False,
                                         "type": "object",
                                         "properties": {}
                                     }
                                 }
                             ]
        }, data)


    def test_resource_routes(self):

        class FooResource(PotionResource):



            class Meta:
                name = 'foo'

    def test_resource_schema(self):

        class UserResource(PotionResource):
            class Schema:
                name = fields.String()
                age = fields.Integer()

            class Meta:
                name = 'user'

        self.assertEqual({}, UserResource.schema)
