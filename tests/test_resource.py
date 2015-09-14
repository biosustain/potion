from flask import json
from flask_potion import fields, Api, Resource
from tests import BaseTestCase


class ResourceTestCase(BaseTestCase):

    def setUp(self):
        super(ResourceTestCase, self).setUp()
        self.api = Api(self.app)

    def test_resource(self):

        class FooResource(Resource):
            class Schema:
                name = fields.String()

            class Meta:
                name = 'foo'

        self.api.add_resource(FooResource)

        #self.assertEqual(['create', 'update', 'schema'], list(FooResource.routes.()))

        data, code, headers = FooResource().described_by()
        self.assertEqual({
                             "name": {
                                 "type": "string"
                             }
                         }, data["properties"])
