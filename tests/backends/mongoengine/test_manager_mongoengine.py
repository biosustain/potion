import unittest
from flask_mongoengine import MongoEngine
from mongoengine.fields import StringField, FloatField, ReferenceField, ListField
from flask_potion.backends.mongoengine import MongoEngineManager
from flask_potion.routes import Relation
from flask_potion import Api, fields
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class MongoEngineTestCase(BaseTestCase):
    def setUp(self):
        super(MongoEngineTestCase, self).setUp()
        self.app.config['MONGODB_DB'] = 'potion-test-db'
        self.api = Api(self.app, default_manager=MongoEngineManager)
        self.me = me = MongoEngine(self.app)

        class Type(me.Document):
            meta = {"collection": "type"}
            name = StringField(max_length=60, null=False, unique=True)

            @property
            def machines(self):
                return Machine.objects(type=self)

            @machines.setter
            def machines(self, machines):
                for m in machines:
                    m.type = self

        class Machine(me.Document):
            meta = {"collection": "machine"}
            name = StringField(max_length=60, null=False)

            wattage = FloatField(null=True)

            type = ReferenceField(Type)

        class MachineResource(ModelResource):
            class Meta:
                model = Machine
                include_id = True
                include_type = True

            class Schema:
                type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type
                include_id = True
                include_type = True

            class Schema:
                machines = fields.ToMany('machine')

        self.MachineResource = MachineResource
        self.TypeResource = TypeResource

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def tearDown(self):
        self.me.connection.drop_database('potion-test-db')

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

    def test_conflict(self):
        response = self.client.post('/type', data={"name": "foo"})
        self.assert200(response)

        response = self.client.post('/type', data={"name": "foo"})
        self.assertStatus(response, 409)

    def test_create(self):
        response = self.client.post('/type', data={})
        self.assert400(response)
        self.assertEqual({
            "errors": [
                {
                    "message": "'name' is a required property",
                    "path": [],
                    "validationOf": {
                        "required": [
                            "name"
                        ]
                    }
                }
            ],
            "message": "Bad Request",
            "status": 400
        }, response.json)

        response = self.client.post('/type', data={"name": "x-ray"})
        type_id = response.json["$id"]
        self.assertEqualWithout({'$type': 'type', 'machines': [], "name": "x-ray"}, response.json, without=["$id"])

        response = self.client.post('/machine',
                                    data={"name": "Irradiator I", "type": {"$ref": "/type/{}".format(type_id)}})
        machine1_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type_id)}, "wattage": None, "name": "Irradiator I"},
            response.json,
            without=["$id"])

        response = self.client.post('/machine', data={"name": "Sol IV", "type": type_id, "wattage": 1.23e45})
        machine2_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type_id)}, "wattage":  1.23e45, "name": "Sol IV"},
            response.json,
            without=["$id"])

        response = self.client.get('/type/{}'.format(type_id))
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'type',
             'machines': [
                 {'$ref': '/machine/{}'.format(machine1_id)},
                 {'$ref': '/machine/{}'.format(machine2_id)}
             ],
             "name": "x-ray"},
            response.json,
            without=["$id"])

    def test_get(self):
        type_ = lambda v: {"$type": "type", "name": "Type-{}".format(v), "machines": []}

        for i in range(1, 10):
            response = self.client.post('/type', data={"name": "Type-{}".format(i), "machines": []})
            self.assert200(response)
            self.assertEqualWithout(type_(i), response.json, without=["$id"])

            response = self.client.get('/type/{}'.format(response.json["$id"]))
            self.assert200(response)
            self.assertEqualWithout(type_(i), response.json, without=["$id"])

            response = self.client.get('/type')
            self.assert200(response)
            for i in range(1, i):
                self.assertEqualWithout(type_(i), response.json[i-1], without=["$id"])

            response = self.client.get('/type/{}'.format(i + 1))
            self.assert404(response)
            self.assertJSONEqual({'item': {'$type': 'type', "$id": str(i + 1)},
                                  'message': 'Not Found',
                                  'status': 404}, response.json)

    @unittest.SkipTest
    def test_pagination(self):
        pass  # TODO

    def test_update(self):
        response = self.client.post('/type', data={"name": "T1"})
        type1_id = response.json["$id"]
        self.assert200(response)

        response = self.client.post('/type', data={"name": "T2"})
        type2_id = response.json["$id"]
        self.assert200(response)

        response = self.client.post('/machine', data={"name": "Robot", "type": type1_id})
        machine_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type1_id)}, "wattage": None, "name": "Robot"},
            response.json,
            without=["$id"])

        response = self.client.patch('/machine/{}'.format(machine_id), data={})
        self.assert200(response)

        response = self.client.patch('/machine/{}'.format(machine_id), data={"wattage": 10000})
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type1_id)}, "wattage": 10000, "name": "Robot"},
            response.json,
            without=["$id"])

        response = self.client.patch('/machine/{}'.format(machine_id), data={"type": {"$ref": "/type/{}".format(type2_id)}})
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type2_id)}, "wattage": 10000, "name": "Robot"},
            response.json,
            without=["$id"])

        response = self.client.patch('/machine/{}'.format(machine_id), data={"type": None})
        self.assert400(response)
        self.assertJSONEqual({
                                 'errors': [
                                     {
                                         "message": "None is not valid under any of the given schemas",
                                         "path": [
                                             "type"
                                         ],
                                         "validationOf": {
                                             "anyOf": [
                                                 {
                                                     "additionalProperties": False,
                                                     "properties": {
                                                         "$ref": {
                                                             "format": "uri",
                                                             "pattern": "^\\/type\\/[^/]+$",
                                                             "type": "string"
                                                         }
                                                     },
                                                     "type": "object"
                                                 },
                                                 {
                                                     "type": "string"
                                                 }
                                             ]
                                         }
                                     }
                                 ],
                                 'message': 'Bad Request',
                                 'status': 400
                             }, response.json)

        response = self.client.patch('/machine/{}'.format(machine_id), data={"name": "Foo"})
        self.assert200(response)
        self.assertEqualWithout(
            {'$type': 'machine', 'type': {"$ref": "/type/{}".format(type2_id)}, "wattage": 10000.0, "name": "Foo"},
            response.json,
            without=["$id"])

    def test_delete(self):
        self.client.post('/type', data={"name": "A"})
        response = self.client.delete('/type/1')
        self.assert404(response)

        response = self.client.post('/type', data={"name": "Foo", "machines": []})
        self.assert200(response)

        response = self.client.delete('/type/%s' % response.json["$id"])
        self.assertStatus(response, 204)

        response = self.client.delete('/type/1')
        self.assert404(response)


class MongoEngineRelationTestCase(BaseTestCase):

    def setUp(self):
        super(MongoEngineRelationTestCase, self).setUp()
        self.app.config['MONGODB_DB'] = 'potion-test-db'
        self.api = Api(self.app, default_manager=MongoEngineManager)
        self.me = me = MongoEngine(self.app)

        class User(me.Document):
            name = StringField(max_length=60)
            children = ListField(ReferenceField('User'))

            @property
            def memberships(self):
                return Group.objects(members__in=self)

        class Group(me.Document):
            name = StringField(max_length=60)
            members = ListField(ReferenceField('User'))

        class UserResource(ModelResource):
            class Meta:
                model = User
                include_id = True
                include_type = True

            children = Relation('self')

        class GroupResource(ModelResource):
            class Meta:
                model = Group
                include_id = True
                include_type = True

            members = Relation('user')

        self.api.add_resource(UserResource)
        self.api.add_resource(GroupResource)

    def test_relationship_secondary(self):
        response = self.client.post('/group', data={"name": "Foo"})
        group_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout({'$type': 'group', "name": "Foo"}, response.json, without=["$id"])

        response = self.client.post('/user', data={"name": "Bar"})
        user_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout({'$type': 'user', "name": "Bar"}, response.json, without=["$id"])

        response = self.client.get('/group/{}/members'.format(group_id))
        self.assert200(response)
        self.assertJSONEqual([], response.json)

        response = self.client.post('/group/{}/members'.format(group_id), data={"$ref": "/user/{}".format(user_id)})
        self.assert200(response)
        self.assertJSONEqual({"$ref": "/user/{}".format(user_id)}, response.json)

        response = self.client.get('/group/{}/members'.format(group_id))
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(user_id)}], response.json)

    def test_relationship_post(self):
        response = self.client.post('/user', data={"name": "Foo"})
        user_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout({'$type': 'user', "name": "Foo"}, response.json, without=["$id"])

        response = self.client.post('/user', data={"name": "Bar"})
        children_id = response.json["$id"]
        self.assert200(response)
        self.assertEqualWithout({'$type': 'user', "name": "Bar"}, response.json, without=["$id"])

        response = self.client.post('/user/{}/children'.format(user_id), data={"$ref": "/user/{}".format(children_id)})

        self.assert200(response)
        self.assertJSONEqual({"$ref": "/user/{}".format(children_id)}, response.json)
        return user_id, children_id

    def test_relationship_get(self):
        user_id, children_id = self.test_relationship_post()

        response = self.client.get('/user/{}/children'.format(user_id))
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(children_id)}], response.json)

    def test_relationship_delete(self):
        user_id, children_id = self.test_relationship_post()

        response = self.client.delete('/user/{}/children/{}'.format(user_id, children_id))
        self.assertStatus(response, 204)

        response = self.client.get('/user/{}/children'.format(user_id))
        self.assert200(response)
        self.assertJSONEqual([], response.json)

    def test_relationship_pagination(self):
        response = self.client.post('/user', data={"name": "Foo"})
        user_id = response.json["$id"]
        self.assert200(response)

        children_ids = []
        for i in range(2, 50):
            response = self.client.post('/user', data={"name": str(i)})
            self.assert200(response)
            children_ids.append(response.json["$id"])
            response = self.client.post('/user/{}/children'.format(user_id), data={"$ref": "/user/{}".format(children_ids[i-2])})
            self.assert200(response)

        response = self.client.get('/user/{}/children'.format(user_id))
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(children_ids[i-2])} for i in range(2, 22)], response.json)

        response = self.client.get('/user/{}/children?page=3'.format(user_id))
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(children_ids[i-2])} for i in range(42, 50)], response.json)
        self.assertEqual('48', response.headers['X-Total-Count'])
        self.assertEqual('</user/{}/children?page=3&per_page=20>; rel="self",'
                         '</user/{}/children?page=1&per_page=20>; rel="first",'
                         '</user/{}/children?page=2&per_page=20>; rel="prev",'
                         '</user/{}/children?page=3&per_page=20>; rel="last"'.format(user_id, user_id, user_id, user_id), response.headers['Link'])

    def tearDown(self):
        self.me.connection.drop_database('potion-test-db')