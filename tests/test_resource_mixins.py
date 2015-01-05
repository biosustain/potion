from flask_potion.routes import Route
from flask_potion import fields, Api
from flask_potion.resource import ModelResource, Resource
from tests import BaseTestCase


class MixinTestCase(BaseTestCase):
    def setUp(self):
        super(MixinTestCase, self).setUp()
        self.api = Api(self.app)

    def test_mixin(self):
        class FooMixin(object):
            class Schema:
                field_b = fields.Integer(io='r')
                field_c = fields.Integer(io='r')

            @Route.GET(response_schema=fields.String())
            def success(self):
                return 'success'

        class FooResource(FooMixin, Resource):
            class Schema:
                field_a = fields.String()
                field_b = fields.String()


        self.assertEqual({'schema', 'success'}, set(FooResource.routes.keys()))

        data, code, headers = FooResource().described_by()

        self.assertEqual({
                             "field_a": {
                                 "type": "string"
                             },
                             "field_b": {
                                 "type": "string"
                             },
                             "field_c": {
                                 "readOnly": True,
                                 "type": "integer"
                             }
                         }, data["properties"])
