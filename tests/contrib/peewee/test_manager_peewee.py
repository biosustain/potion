import unittest

import peewee as pw
from playhouse.fields import ManyToManyField

from flask_potion import Api, fields
from flask_potion.contrib.peewee import PeeweeManager
from flask_potion.resource import ModelResource
from flask_potion.routes import Relation
from tests import BaseTestCase
from tests.contrib.peewee import PeeweeTestDB


class PeeweeTestCase(BaseTestCase):
    def setUp(self):
        super(PeeweeTestCase, self).setUp()
        self.app.config['DATABASE'] = 'sqlite://'
        self.db = db = PeeweeTestDB(self.app)
        self.api = Api(self.app)

        class Type(db.Model):
            name = pw.CharField(max_length=60, null=False, unique=True)

        class Machine(db.Model):
            name = pw.CharField(max_length=60, null=False)
            wattage = pw.FloatField(null=True)
            type = pw.ForeignKeyField(Type, related_name='machines')

        self.db.database.connect()
        self.db.database.create_tables([Type, Machine])

        class MachineResource(ModelResource):
            class Meta:
                model = Machine
                include_id = True
                include_type = True
                manager = PeeweeManager

            class Schema:
                type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type
                include_id = True
                include_type = True
                manager = PeeweeManager

            class Schema:
                machines = fields.ToMany(MachineResource)

        self.MachineResource = MachineResource
        self.TypeResource = TypeResource

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def tearDown(self):
        self.db.database.close()

    def test_field_discovery(self):
        self.assertEqual(
            set(self.MachineResource.schema.fields.keys()),
            {'$id', '$type', 'name', 'type', 'wattage'})
        self.assertEqual(
            set(self.TypeResource.schema.fields.keys()),
            {'$id', '$type', 'name', 'machines'})
        self.assertEqual(self.MachineResource.meta.name, 'machine')
        self.assertEqual(self.TypeResource.meta.name, 'type')

    def test_create_no_json(self):
        response = self.client.post('/machine', data='invalid')
        self.assert400(response)

    def test_create_json_string(self):
        response = self.client.post(
            '/machine', data='invalid', force_json=True)
        self.assert400(response)

    def test_conflict(self):
        response = self.client.post('/type', data={'name': 'foo'})
        self.assert200(response)

        response = self.client.post('/type', data={'name': 'foo'})
        self.assertStatus(response, 409)

    def test_create(self):
        response = self.client.post('/type', data={})
        self.assert400(response)
        self.assertEqual({
            'errors': [
                {
                    'message': "'name' is a required property",
                    'path': [],
                    'validationOf': {
                        'required': [
                            'name'
                        ]
                    }
                }
            ],
            'message': 'Bad Request',
            'status': 400
        }, response.json)

        response = self.client.post('/type', data={'name': 'x-ray'})
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'type',
            'machines': [],
            'name': 'x-ray'},
            response.json)

        response = self.client.post(
            '/machine', data={'name': 'Irradiator I', 'type': 1})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'machine',
            'type': {'$ref': '/type/1'},
            'wattage': None,
            'name': 'Irradiator I'},
            response.json)

        response = self.client.post(
            '/machine', data={'name': 'Sol IV', 'type': 1, 'wattage': 1.23e45})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 2,
            '$type': 'machine',
            'type': {'$ref': '/type/1'},
            'wattage': 1.23e45,
            'name': 'Sol IV'},
            response.json)

        response = self.client.get('/type/1')
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'type',
            'machines': [
                {'$ref': '/machine/1'},
                {'$ref': '/machine/2'}],
            'name': 'x-ray'},
            response.json)

    def test_get(self):
        def type_(i):
            return {
                '$id': i,
                '$type': 'type',
                'name': 'Type-{}'.format(i),
                'machines': []}

        for i in range(1, 10):
            response = self.client.post(
                '/type',
                data={'name': 'Type-{}'.format(i), 'machines': []})
            self.assert200(response)
            self.assertJSONEqual(type_(i), response.json)

            response = self.client.get('/type/{}'.format(i))
            self.assert200(response)
            self.assertJSONEqual(type_(i), response.json)

            response = self.client.get('/type')
            self.assert200(response)
            self.assertJSONEqual(
                [type_(i) for i in range(1, i + 1)],
                response.json)

            response = self.client.get('/type/{}'.format(i + 1))
            self.assert404(response)
            self.assertJSONEqual({
                'item': {'$id': i + 1, '$type': 'type'},
                'message': 'Not Found',
                'status': 404},
                response.json)

    def test_pagination(self):
        for i in range(1, 51):
            response = self.client.post('/type', data={'name': 'T{}'.format(i)})
            self.assert200(response)

        response = self.client.get('/type')
        self.assert200(response)
        self.assertEqual('50', response.headers.get('X-Total-Count'))

        response = self.client.get('/type?where={"name": {"$in": ["T1", "T5", "T6"]}}')
        self.assert200(response)
        self.assertEqual('3', response.headers.get('X-Total-Count'))

    def test_update(self):
        response = self.client.post('/type', data={'name': 'T1'})
        self.assert200(response)

        response = self.client.post('/type', data={'name': 'T2'})
        self.assert200(response)

        response = self.client.post(
            '/machine', data={'name': 'Robot', 'type': 1})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'machine',
            'type': {'$ref': '/type/1'},
            'wattage': None,
            'name': 'Robot'},
            response.json)

        response = self.client.patch('/machine/1', data={})
        self.assert200(response)

        response = self.client.patch('/machine/1', data={'wattage': 10000})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'machine',
            'type': {'$ref': '/type/1'},
            'wattage': 10000,
            'name': 'Robot'},
            response.json)

        response = self.client.patch(
            '/machine/1', data={'type': {'$ref': '/type/2'}})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'machine',
            'type': {'$ref': '/type/2'},
            'wattage': 10000,
            'name': 'Robot'},
            response.json)

        response = self.client.patch('/machine/1', data={'type': None})
        self.assert400(response)
        self.assertJSONEqual({
            'errors': [{
                'message': 'None is not valid under any of the given schemas',
                'path': [
                    'type'],
                'validationOf': {
                    'anyOf': [{
                        'additionalProperties': False,
                        'properties': {
                            '$ref': {
                                'pattern': '^\\/type\\/[^/]+$',
                                'type': 'string'}},
                            'type': 'object'}, {
                                'type': 'integer'}]}}],
            'message': 'Bad Request',
            'status': 400},
            response.json)

        response = self.client.patch('/machine/1', data={'name': 'Foo'})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'machine',
            'type': {'$ref': '/type/2'},
            'wattage': 10000,
            'name': 'Foo'},
            response.json)

    def test_delete(self):
        response = self.client.delete('/type/1')
        self.assert404(response)

        response = self.client.post(
            '/type', data={'name': 'Foo', 'machines': []})
        self.assert200(response)

        response = self.client.delete('/type/1')
        self.assertStatus(response, 204)

        response = self.client.delete('/type/1')
        self.assert404(response)


class PeeweeRelationTestCase(BaseTestCase):
    def setUp(self):
        super(PeeweeRelationTestCase, self).setUp()

        self.app.config['DATABASE'] = 'sqlite://'
        self.db = db = PeeweeTestDB(self.app)
        self.api = Api(self.app)

        class User(db.Model):
            parent = pw.ForeignKeyField('self', related_name='children',
                                        null=True)
            name = pw.CharField(max_length=60, null=False)

        class Group(db.Model):
            name = pw.CharField(max_length=60, null=False)
            members = ManyToManyField(User, related_name='memberships')

        db.database.connect()
        db.database.create_tables([
            User,
            Group,
            Group.members.get_through_model()])

        self.User = User
        self.Group = Group

        class UserResource(ModelResource):
            class Meta:
                model = User
                include_id = True
                include_type = True
                manager = PeeweeManager

            children = Relation('self')

        class GroupResource(ModelResource):
            class Meta:
                model = Group
                include_id = True
                include_type = True
                manager = PeeweeManager

            members = Relation('user')

        self.api.add_resource(UserResource)
        self.api.add_resource(GroupResource)

    def tearDown(self):
        self.db.database.drop_tables([
            self.Group.members.get_through_model(),
            self.Group,
            self.User])

        if not self.db.database.is_closed():
            self.db.database.close()

    def test_relationship_secondary(self):
        response = self.client.post('/group', data={'name': 'Foo'})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'group',
            'name': 'Foo'},
            response.json)

        response = self.client.post('/user', data={'name': 'Bar'})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'user',
            'name': 'Bar'},
            response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

        response = self.client.post(
            '/group/1/members', data={'$ref': '/user/1'})
        self.assert200(response)
        self.assertJSONEqual({'$ref': '/user/1'}, response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([{'$ref': '/user/1'}], response.json)

    def test_relationship_secondary_delete_missing(self):
        response = self.client.post('/group', data={"name": "Foo"})
        response = self.client.post('/user', data={"name": "Bar"})

        response = self.client.delete('/group/1/members/1')
        self.assertStatus(response, 204)

    def test_relationship_post(self):
        response = self.client.post('/user', data={'name': 'Foo'})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 1,
            '$type': 'user',
            'name': 'Foo'},
            response.json)

        response = self.client.post('/user', data={'name': 'Bar'})
        self.assert200(response)
        self.assertJSONEqual({
            '$id': 2,
            '$type': 'user',
            'name': 'Bar'},
            response.json)

        response = self.client.post(
            '/user/1/children', data={'$ref': '/user/2'})
        self.assert200(response)
        self.assertJSONEqual({'$ref': '/user/2'}, response.json)

    def test_relationship_get(self):
        self.test_relationship_post()

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([{'$ref': '/user/2'}], response.json)

    def test_relationship_delete(self):
        self.test_relationship_post()

        response = self.client.delete('/user/1/children/2')
        self.assertStatus(response, 204)

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

    def test_relationship_pagination(self):
        response = self.client.post('/user', data={'name': 'Foo'})
        self.assert200(response)

        for i in range(2, 50):
            response = self.client.post('/user', data={'name': str(i)})
            self.assert200(response)
            response = self.client.post(
                '/user/1/children',
                data={'$ref': '/user/{}'.format(response.json['$id'])})
            self.assert200(response)

        response = self.client.get('/user/1/children')

        self.assert200(response)
        self.assertEqual('48', response.headers.get('X-Total-Count'))
        self.assertJSONEqual(
            [{'$ref': '/user/{}'.format(i)} for i in range(2, 22)],
            response.json)

        response = self.client.get('/user/1/children?page=3')
        self.assert200(response)
        self.assertEqual('48', response.headers.get('X-Total-Count'))
        self.assertJSONEqual(
            [{'$ref': '/user/{}'.format(i)} for i in range(42, 50)],
            response.json)
