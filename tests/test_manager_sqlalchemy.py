import unittest
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask_potion.routes import Relation
from flask_potion.backends.sqlalchemy import SQLAlchemyManager
from flask_potion import Api, fields
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class SQLAlchemyTestCase(BaseTestCase):
    def setUp(self):
        super(SQLAlchemyTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app)

        class Type(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)

        class Machine(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)

            wattage = sa.Column(sa.Float)

            type_id = sa.Column(sa.Integer, sa.ForeignKey(Type.id))
            type = sa.relationship(Type, backref=backref('machines', lazy='dynamic', uselist=True))

        sa.create_all()

        class MachineResource(ModelResource):
            class Meta:
                model = Machine

            class Schema:
                type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type

            class Schema:
                machines = fields.ToMany(MachineResource)

        self.MachineResource = MachineResource
        self.TypeResource = TypeResource

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def tearDown(self):
        self.sa.drop_all()

    def test_field_discovery(self):
        self.assertEqual(set(self.MachineResource.schema.fields.keys()), {'$id', '$type', 'name', 'type', 'wattage'})
        self.assertEqual(set(self.TypeResource.schema.fields.keys()), {'$id', '$type', 'name', 'machines'})
        self.assertEqual(self.MachineResource.meta.name, 'machine')
        self.assertEqual(self.TypeResource.meta.name, 'type')

    def test_create_no_json(self):
        response = self.client.post('/machine', data='invalid')
        self.assert400(response)

    def test_create_json_string(self):
        response = self.client.post('/machine', data='invalid', force_json=True)
        self.assert400(response)

    def test_create(self):
        response = self.client.post('/type', data={"name": "x-ray", "machines": []}) # FIXME "machines": [] should not be necessary
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'type', 'machines': [], "name": "x-ray"}, response.json)

        response = self.client.post('/machine', data={"name": "Irradiator I", "type": {"$ref": "/type/1"}})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": None, "name": "Irradiator I"}, response.json)

        response = self.client.post('/machine', data={"name": "Sol IV", "type": {"$ref": "/type/1"}, "wattage": 1.23e45})
        self.assert200(response)
        self.assertJSONEqual({'$id': 2, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage":  1.23e45, "name": "Sol IV"}, response.json)

        response = self.client.get('/type/1') # FIXME "machines": [] should not be necessary
        self.assert200(response)
        self.assertJSONEqual({
                                 '$id': 1,
                                 '$type': 'type',
                                 'machines': [
                                     {'$ref': '/machine/1'},
                                     {'$ref': '/machine/2'}
                                 ],
                                 "name": "x-ray"
                             }, response.json)

    def test_get(self):
        type_ = lambda i: {"$id": i, "$type": "type", "name": "Type-{}".format(i), "machines": []}

        for i in range(1, 10):
            expected = {"$id": i, "$type": "type", "name": "Type-{}".format(i), "machines": []}
            response = self.client.post('/type', data={"name": "Type-{}".format(i), "machines": []})
            self.assert200(response)
            self.assertJSONEqual(type_(i), response.json)

            response = self.client.get('/type/{}'.format(i))
            self.assert200(response)
            self.assertJSONEqual(type_(i), response.json)

            response = self.client.get('/type')
            self.assert200(response)
            self.assertJSONEqual([type_(i) for i in range(1, i + 1)], response.json)

            response = self.client.get('/type/{}'.format(i + 1))
            self.assert404(response)
            self.assertJSONEqual({
                                     'item': {'$id': i + 1, '$type': 'type'},
                                     'message': 'Not Found',
                                     'status': 404
                                 }, response.json)

    @unittest.SkipTest
    def test_pagination(self):
        pass # TODO

    def test_update(self):
        response = self.client.post('/type', data={"name": "T1", "machines": []}) # FIXME "machines": [] should not be necessary
        self.assert200(response)

        response = self.client.post('/type', data={"name": "T2", "machines": []}) # FIXME "machines": [] should not be necessary
        self.assert200(response)

        response = self.client.post('/machine', data={"name": "Robot", "type": {"$ref": "/type/1"}})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": None, "name": "Robot"}, response.json)

        response = self.client.patch('/machine/1', data={"wattage": 10000})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": 10000, "name": "Robot"}, response.json)

        response = self.client.patch('/machine/1', data={"type": {"$ref": "/type/2"}})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/2"}, "wattage": 10000, "name": "Robot"}, response.json)


        response = self.client.patch('/machine/1', data={"type": None})
        self.assert400(response)
        self.assertJSONEqual({
                                 'errors': [
                                     {
                                         'path': ['type'],
                                         'validationOf': {'type': 'object'}
                                     }
                                 ],
                                 'message': 'Bad Request',
                                 'status': 400
                             }, response.json)

        response = self.client.patch('/machine/1', data={"name": "Foo"})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/2"}, "wattage": 10000, "name": "Foo"}, response.json)

    def test_delete(self):
        response = self.client.delete('/type/1')
        self.assert404(response)

        response = self.client.post('/type', data={"name": "Foo", "machines": []})
        self.assert200(response)

        response = self.client.delete('/type/1')
        self.assertStatus(response, 204)

        response = self.client.delete('/type/1')
        self.assert404(response)


# class SQLAlchemyRelationTestCase(BaseTestCase):
#
#     def setUp(self):
#         super(SQLAlchemyRelationTestCase, self).setUp()
#         self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
#         self.api = Api(self.app)
#         self.sa = sa = SQLAlchemy(self.app)
#
#         class User(sa.Model):
#             id = sa.Column(sa.Integer, primary_key=True)
#             name = sa.Column(sa.String(60), nullable=False)
#
#         class Group(sa.Model):
#             id = sa.Column(sa.Integer, primary_key=True)
#             name = sa.Column(sa.String(60), nullable=False)
#
#         sa.create_all()
#
#         class UserResource(SAResource):
#             class Meta:
#                 model = User
#
#             friends = Relation('user')
#
#
#         class GroupResource(SAResource):
#             class Meta:
#                 model = Group
#
#             members = Relation('user')
#
#         self.api.add_resource(UserResource)
#         self.api.add_resource(GroupResource)
#
#
#
#     # def test_relationship_post(self):
#     #     self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': 'Apple tree', '_uri': '/tree/1'}, 200)
#     #     self.request('GET', '/tree/1/fruits', None, [], 200)
#     #
#     #     self.request('POST', '/fruit', {'name': 'Apple'},
#     #                  {'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': None}, 200)
#     #
#     #     self.request('POST', '/tree/1/fruits', '/fruit/1',
#     #                  {'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': '/tree/1'}, 200)
#     #
#     # def test_relationship_get(self):
#     #     self.test_relationship_post()
#     #     self.request('GET', '/tree/1/fruits', None,
#     #                  [{'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': '/tree/1'}], 200)
#     #
#     # def test_relationship_delete(self):
#     #     self.test_relationship_post()
#     #     self.request('DELETE', '/tree/1/fruits', '/fruit/1', None, 204)
#     #     #self.request('GET', '/apple/seed_count', None, 2, 200)