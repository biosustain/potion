import unittest
from flask_potion import Api, fields
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class RelationTestCase(BaseTestCase):

    def setUp(self):
        super(RelationTestCase, self).setUp()
        self.api = Api(self.app)

    def test_pagination(self):
        class Person(ModelResource):
            class Schema:
                name = fields.String()

            class Meta:
                name = "person"
                model = name
                manager = MemoryManager

        self.api.add_resource(Person)

        response = self.client.get('/person')
        self.assert200(response)

        self.assertEqual('0', response.headers.get('X-Total-Count'))
        self.assertEqual('</person?page=1&per_page=20>; rel="self",'
                         '</person?page=1&per_page=20>; rel="last"', response.headers['Link'])

        for i in range(1, 51):
            response = self.client.post('/person', data={"name": str(i)})
            self.assert200(response)

        response = self.client.get('/person')
        self.assert200(response)
        self.assertJSONEqual([{"$uri": "/person/{}".format(i), "name": str(i)} for i in range(1, 21)], response.json)

        response = self.client.get('/person?page=3')
        self.assert200(response)

        self.assertEqual('50', response.headers.get('X-Total-Count'))
        self.assertEqual('</person?page=3&per_page=20>; rel="self",'
                         '</person?page=1&per_page=20>; rel="first",'
                         '</person?page=2&per_page=20>; rel="prev",'
                         '</person?page=3&per_page=20>; rel="last"', response.headers['Link'])
        self.assertJSONEqual([{"$uri": "/person/{}".format(i), "name": str(i)} for i in range(41, 51)], response.json)




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
        })

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
