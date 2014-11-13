from flask.ext.potion.resource import PotionResource
from flask.ext.potion.routes import Route
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
    def test_route(self):
        pass

