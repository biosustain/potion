import unittest
from flask_potion import Api, fields
from flask_potion.backends.memory import MemoryManager
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class RelationTestCase(BaseTestCase):

    def setUp(self):
        super(RelationTestCase, self).setUp()
        self.api = Api(self.app)

    def test_pagination(self):
        pass

    def test_where_to_one(self):
        class Person(ModelResource):
            class Schema:
                name = fields.String()
                mother = fields.ToOne('person', nullable=True)

            class Meta:
                name = "person"
                model = name
                manager = MemoryManager

        self.api.add_resource(Person)

        response = self.client.post('/person', data={
            'name': 'Anna'
        })  # No. Bad

        self.assert200(response)
        self.assertJSONEqual({'$uri': '/person/1',
                              'mother': None,
                              'name': 'Anna'}, response.json)

        self.client.post('/person', data={
            'name': 'Betty',
            'mother': {"$ref": "/person/1"}
        })

        self.client.post('/person', data={
            'name': 'Bob',
            'mother': {"$ref": "/person/1"}
        })

        self.client.post('/person', data={
            'name': 'Foo',
            'mother': {"$ref": "/person/2"}
        })

        self.client.post('/person', data={
            'name': 'Clare',
            'mother': {"$ref": "/person/2"}
        })

        response = self.client.get('/person?where={"mother": null}')
        self.assertJSONEqual([
            {'$uri': '/person/1', 'mother': None, 'name': 'Anna'}
        ], response.json)

        response = self.client.get('/person?where={"mother": {"$ref": "/person/1"}}')
        self.assertJSONEqual([
            {'$uri': '/person/2', 'mother': {'$ref': '/person/1'}, 'name': 'Betty'},
            {'$uri': '/person/3', 'mother': {'$ref': '/person/1'}, 'name': 'Bob'}
        ], response.json)

        response = self.client.get('/person?where={"mother": {"$ref": "/person/2"}, "name": {"$startswith": "C"}}')
        self.assertJSONEqual([
            {'$uri': '/person/5', 'mother': {'$ref': '/person/2'}, 'name': 'Clare'}
        ], response.json)
