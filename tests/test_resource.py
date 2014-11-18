from flask import json
from flask_potion import fields
from flask_potion.resource import Resource
from tests import BaseTestCase


class ResourceTestCase(BaseTestCase):


    def test_resource(self):

        class FooResource(Resource):

            class Schema:
                name = fields.String()

            class Meta:
                name = 'foo'

        #self.assertEqual(['create', 'update', 'schema'], list(FooResource.routes.()))

        data, code, headers = FooResource().described_by()
        print(json.dumps(data,indent=2))
        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "type": "object",
                             "links": [
                                 {
                                     "href": "",
                                     "method": "POST",
                                     "rel": "create",
                                     "targetSchema": {
                                         "$ref": "#"
                                     }
                                 },
                                 {
                                     "href": "schema",
                                     "method": "GET",
                                     "rel": "describedBy"
                                 },
                                 {
                                     "href": "{id}",
                                     "method": "DELETE",
                                     "rel": "destroy"
                                 },
                                 {
                                     "href": "",
                                     "method": "GET",
                                     "rel": "instances",
                                     "targetSchema": {
                                         "TODO": True
                                     } # TODO Instances()
                                 },
                                 {
                                     "href": "{id}",
                                     "method": "GET",
                                     "rel": "self",
                                     "targetSchema": {
                                         "$ref": "#"
                                     }
                                 },
                                 {
                                     "href": "{id}",
                                     "method": "PATCH",
                                     "rel": "update",
                                     "targetSchema": {
                                         "$ref": "#"
                                     } # TODO patch() mode without required fields
                                 }
                             ],
                             "properties": {
                                 "name": {
                                     "type": "string"
                                 }
                             }
                         }
                         , data)
