from bson import ObjectId
from bson.errors import InvalidId
from mongoengine import ObjectIdField, MapField, FloatField, StringField, EmbeddedDocumentField, \
    EmbeddedDocument

from flask_potion import Api, ModelResource
from tests.contrib.mongoengine import MongoEngineTestCase


class FieldsTestCase(MongoEngineTestCase):
    def test_object_id_field(self):

        class Model(self.me.Document):
            meta = {
                'collection': 'model'
            }

            an_id = ObjectIdField()

        class Resource(ModelResource):
            class Meta:
                model = Model

        self.api.add_resource(Resource)

        response = self.client.get('/model/schema')
        self.assertEqual(response.json['properties']['an_id'], {'type': 'string'})
        self.assertRaises(InvalidId, self.client.post, '/model', data={'an_id': "abc"})

        hex = 'adfb48a6763c5741b92f6ade'
        object_id = ObjectId('adfb48a6763c5741b92f6ade')
        response = self.client.post('/model', data={'an_id': hex})
        self.assertEqual(object_id, ObjectId(response.json['an_id']))

    def test_map_field(self):

        class ReferenceModel(EmbeddedDocument):
            id = ObjectIdField()
            meta = {
                'collection': 'reference-model'
            }

        class Model(self.me.Document):
            meta = {
                'collection': 'model'
            }

            float_mapping = MapField(FloatField())
            string_mapping = MapField(StringField())
            object_id_mapping = MapField(ObjectIdField())
            reference_mapping = MapField(EmbeddedDocumentField(ReferenceModel))

        class Resource(ModelResource):
            class Meta:
                model = Model

        self.api.add_resource(Resource)

        response = self.client.get('/model/schema')
        self.assertEqual(response.json['properties']['float_mapping']['additionalProperties'], {'type': 'number'})
        self.assertEqual(response.json['properties']['float_mapping']['default'], {})
        self.assertEqual(response.json['properties']['string_mapping']['additionalProperties'], {'type': 'string'})
        self.assertEqual(response.json['properties']['string_mapping']['default'], {})
        self.assertEqual(response.json['properties']['reference_mapping']['additionalProperties'],
                         {
                             'additionalProperties': False,
                             'type': 'object',
                             'properties': {
                                 'id': {'type': 'string'}
                             }
                         })
        self.assertEqual(response.json['properties']['reference_mapping']['default'], {})
        ref_model = dict(id='adfb48a6763c5741b92f6ade')
        response = self.client.post("/model", data={'reference_mapping': {"1": ref_model}, 'object_id_mapping': {"a": ref_model["id"]}})
        self.assertEqualWithout(response.json,
                                {
                                    'reference_mapping': {
                                        '1': {
                                            'id': 'adfb48a6763c5741b92f6ade'
                                        }
                                    },
                                    '$uri': '/model/561e6a807f551ce7d5df1003',
                                    'float_mapping': {},
                                    'object_id_mapping': {
                                        'a': 'adfb48a6763c5741b92f6ade'
                                    }, 'string_mapping': {}
                                },
                                without=["$uri"])