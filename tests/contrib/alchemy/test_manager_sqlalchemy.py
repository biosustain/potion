import unittest
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref, joinedload
from flask_potion.routes import Relation
from flask_potion.contrib.alchemy import SQLAlchemyManager
from flask_potion import Api, fields
from flask_potion.resource import ModelResource
from tests import BaseTestCase, DBQueryCounter


class SQLAlchemyTestCase(BaseTestCase):
    def setUp(self):
        super(SQLAlchemyTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app, default_manager=SQLAlchemyManager)
        self.sa = sa = SQLAlchemy(self.app, session_options={"autoflush": False})

        class Type(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False, unique=True)
            version = sa.Column(sa.Integer(), nullable=True)

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
        self.sa.drop_all()

    def test_field_discovery(self):
        self.assertEqual(set(self.MachineResource.schema.fields.keys()), {'$id', '$type', 'name', 'type', 'wattage'})
        self.assertEqual(set(self.TypeResource.schema.fields.keys()), {'$id', '$type', 'name', 'version', 'machines'})
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
        self.assertJSONEqual({'$id': 1, '$type': 'type', 'machines': [], "name": "x-ray", 'version': None}, response.json)

        response = self.client.post('/machine', data={"name": "Irradiator I", "type": 1})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": None, "name": "Irradiator I"}, response.json)

        response = self.client.post('/machine', data={"name": "Sol IV", "type": 1, "wattage": 1.23e45})
        self.assert200(response)
        self.assertJSONEqual({'$id': 2, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage":  1.23e45, "name": "Sol IV"}, response.json)

        response = self.client.get('/type/1')
        self.assert200(response)
        self.assertJSONEqual({
                                 '$id': 1,
                                 '$type': 'type',
                                 'machines': [
                                     {'$ref': '/machine/1'},
                                     {'$ref': '/machine/2'}
                                 ],
                                 "name": "x-ray",
                                 'version': None
                             }, response.json)

    def test_get(self):
        type_ = lambda i: {"$id": i, "$type": "type", "name": "Type-{}".format(i), "machines": [], 'version': None}

        for i in range(1, 10):
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
        response = self.client.post('/type', data={"name": "T1"})
        self.assert200(response)

        response = self.client.post('/type', data={"name": "T2"})
        self.assert200(response)

        response = self.client.post('/machine', data={"name": "Robot", "type": 1})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": None, "name": "Robot"}, response.json)

        response = self.client.patch('/machine/1', data={})
        self.assert200(response)

        response = self.client.patch('/machine/1', data={"wattage": 10000})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/1"}, "wattage": 10000, "name": "Robot"}, response.json)

        response = self.client.patch('/machine/1', data={"type": {"$ref": "/type/2"}})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'machine', 'type': {"$ref": "/type/2"}, "wattage": 10000, "name": "Robot"}, response.json)

        response = self.client.patch('/type/1', data={"version": 1})
        self.assertJSONEqual({'$id': 1, '$type': 'type', 'name': 'T1', 'version': 1, 'machines': []}, response.json)

        response = self.client.patch('/type/1', data={"version": None})
        self.assertJSONEqual({'$id': 1, '$type': 'type', 'name': 'T1', 'machines': [], 'version': None}, response.json)

        response = self.client.patch('/machine/1', data={"type": None})
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
                                                             "pattern": "^\\/type\\/[^/]+$",
                                                             "type": "string"
                                                         }
                                                     },
                                                     "type": "object"
                                                 },
                                                 {
                                                     "type": "integer"
                                                 }
                                             ]
                                         }
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


class SQLAlchemyRelationTestCase(BaseTestCase):

    def setUp(self):
        super(SQLAlchemyRelationTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app, session_options={"autoflush": False})

        group_members = sa.Table('group_members',
                               sa.Column('group_id', sa.Integer(), sa.ForeignKey('group.id')),
                               sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')))

        class User(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            parent_id = sa.Column(sa.Integer, sa.ForeignKey(id))
            name = sa.Column(sa.String(60), nullable=False)

            parent = sa.relationship('User', remote_side=[id], backref=backref('children', lazy='dynamic'))

        class Group(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)
            members = sa.relationship('User', secondary=group_members,
                                      backref=backref('memberships', lazy='dynamic'))

        sa.create_all()

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
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'group', "name": "Foo"}, response.json)

        response = self.client.post('/user', data={"name": "Bar"})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'user', "name": "Bar"}, response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

        response = self.client.post('/group/1/members', data={"$ref": "/user/1"})
        self.assert200(response)
        self.assertJSONEqual({"$ref": "/user/1"}, response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/1"}], response.json)

    def test_relationship_secondary_delete_missing(self):
        response = self.client.post('/group', data={"name": "Foo"})
        response = self.client.post('/user', data={"name": "Bar"})

        response = self.client.delete('/group/1/members/1')
        self.assertStatus(response, 204)

    def test_relationship_post(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)
        self.assertJSONEqual({'$id': 1, '$type': 'user', "name": "Foo"}, response.json)

        response = self.client.post('/user', data={"name": "Bar"})
        self.assert200(response)
        self.assertJSONEqual({'$id': 2, '$type': 'user', "name": "Bar"}, response.json)

        response = self.client.post('/user/1/children', data={"$ref": "/user/2"})
        self.assert200(response)
        self.assertJSONEqual({"$ref": "/user/2"}, response.json)

    def test_relationship_get(self):
        self.test_relationship_post()

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/2"}], response.json)

    def test_relationship_delete(self):
        self.test_relationship_post()

        response = self.client.delete('/user/1/children/2')
        self.assertStatus(response, 204)

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

    def test_relationship_delete_missing(self):
        self.test_relationship_post()

        response = self.client.delete('/user/1/children/2')
        self.assertStatus(response, 204)

        response = self.client.delete('/user/1/children/2')
        self.assertStatus(response, 204)

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

    def test_relationship_pagination(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)

        for i in range(2, 50):
            response = self.client.post('/user', data={"name": str(i)})
            self.assert200(response)
            response = self.client.post('/user/1/children', data={"$ref": "/user/{}".format(response.json['$id'])})
            self.assert200(response)

        response = self.client.get('/user/1/children')
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(i)} for i in range(2, 22)], response.json)

        response = self.client.get('/user/1/children?page=3')
        self.assert200(response)
        self.assertJSONEqual([{"$ref": "/user/{}".format(i)} for i in range(42, 50)], response.json)

        self.assertEqual('48', response.headers['X-Total-Count'])
        self.assertEqual('</user/1/children?page=3&per_page=20>; rel="self",'
                         '</user/1/children?page=1&per_page=20>; rel="first",'
                         '</user/1/children?page=2&per_page=20>; rel="prev",'
                         '</user/1/children?page=3&per_page=20>; rel="last"', response.headers['Link'])


class SQLAlchemyInspectionTestCase(BaseTestCase):

    def setUp(self):
        super(SQLAlchemyInspectionTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app, session_options={"autoflush": False})

    def test_inspection_auto_id_attribute_type(self):
        sa = self.sa

        class User(sa.Model):
            username = sa.Column(sa.String, primary_key=True)
            first_name = sa.Column(sa.String)
            last_name = sa.Column(sa.String)

        sa.create_all()

        class UserResource(ModelResource):
            class Schema:
                username = fields.String()

            class Meta:
                model = User
                include_id = True

        self.api.add_resource(UserResource)
        self.assertEqual(User.username, UserResource.manager.id_column)
        self.assertEqual('username', UserResource.manager.id_field.attribute)
        self.assertIsInstance(UserResource.manager.id_field, fields.String)

        response = self.client.post('/user', data={"username": "foo", "first_name": "Foo"})
        self.assert200(response)

        self.assertJSONEqual({
            "$id": "foo",
            "first_name": "Foo",
            "last_name": None,
            "username": "foo"
        }, response.json)


class SQLAlchemySequenceTestCase(BaseTestCase):

    def setUp(self):
        super(SQLAlchemySequenceTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(self.app, session_options={"autoflush": False})

    def test_sequence_primary_key(self):
        sa = self.sa

        user_id_seq = sa.Sequence('user_id_seq')

        class User(sa.Model):
            id = sa.Column(sa.Integer, user_id_seq, primary_key=True)
            username = sa.Column(sa.String, unique=True)

        sa.create_all()

        class UserResource(ModelResource):
            class Schema:
                username = fields.String()

            class Meta:
                model = User
                include_id = True

        self.api.add_resource(UserResource)

        response = self.client.post('/user', data={"username": "foo"})
        self.assert200(response)

        self.assertJSONEqual({
            "$id": 1,
            "username": "foo"
        }, response.json)


class SQLAlchemySortTestCase(BaseTestCase):

    def setUp(self):
        super(SQLAlchemySortTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(
            self.app, session_options={"autoflush": False})

        class Type(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)

        class Machine(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)

            type_id = sa.Column(sa.Integer, sa.ForeignKey(Type.id))
            type = sa.relationship(Type, foreign_keys=[type_id])

        sa.create_all()

        class MachineResource(ModelResource):
            class Meta:
                model = Machine

            class Schema:
                type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type
                sort_attribute = ('name', True)

        self.MachineResource = MachineResource
        self.TypeResource = TypeResource

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def test_default_sorting_with_desc(self):
        self.client.post('/type', data={"name": "aaa"})
        self.client.post('/type', data={"name": "ccc"})
        self.client.post('/type', data={"name": "bbb"})
        response = self.client.get('/type')
        self.assert200(response)
        self.assertJSONEqual(
            [{'$uri': '/type/2', 'name': 'ccc'},
             {'$uri': '/type/3', 'name': 'bbb'},
             {'$uri': '/type/1', 'name': 'aaa'}],
            response.json)

    def test_sort_by_related_field(self):
        response = self.client.post('/type', data={"name": "aaa"})
        self.assert200(response)
        aaa_uri = response.json["$uri"]
        response = self.client.post('/type', data={"name": "bbb"})
        self.assert200(response)
        bbb_uri = response.json["$uri"]
        self.client.post(
            '/machine', data={"name": "foo", "type": {"$ref": aaa_uri}})
        self.assert200(response)
        self.client.post(
            '/machine', data={"name": "bar", "type": {"$ref": bbb_uri}})
        self.assert200(response)
        response = self.client.get('/machine?sort={"type": true}')
        self.assert200(response)
        type_uris = [entry['type']['$ref'] for entry in response.json]
        self.assertTrue(type_uris, [bbb_uri, aaa_uri])
        response = self.client.get('/machine?sort={"type": false}')
        self.assert200(response)
        type_uris = [entry['type']['$ref'] for entry in response.json]
        self.assertTrue(type_uris, [bbb_uri, aaa_uri])


class QueryOptionsSQLAlchemyTestCase(BaseTestCase):
    def setUp(self):
        super(QueryOptionsSQLAlchemyTestCase, self).setUp()
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.api = Api(self.app, default_manager=SQLAlchemyManager)
        self.sa = sa = SQLAlchemy(self.app, session_options={"autoflush": False})

        class Type(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False, unique=True)
            version = sa.Column(sa.Integer(), nullable=True)
            machines = sa.relationship('Machine', back_populates='type')

        class Machine(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(60), nullable=False)

            wattage = sa.Column(sa.Float)

            type_id = sa.Column(sa.Integer, sa.ForeignKey(Type.id))
            type = sa.relationship(Type, back_populates='machines')

        sa.create_all()

        class MachineResource(ModelResource):
            class Meta:
                model = Machine
                include_type = True

            class Schema:
                type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type
                include_type = True
                query_options = [joinedload(Type.machines)]

            class Schema:
                machines = fields.ToMany('machine')

        self.MachineResource = MachineResource
        self.TypeResource = TypeResource

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def tearDown(self):
        self.sa.drop_all()

    def test_get(self):
        response = self.client.post('/type', data={"name": "aaa"})
        self.assert200(response)
        aaa_uri = response.json["$uri"]

        response = self.client.post(
            '/machine', data={"name": "foo", "type": {"$ref": aaa_uri}})
        self.assert200(response)
        machine_uri = response.json['$uri']

        with DBQueryCounter(self.sa.session) as counter:
            response = self.client.get(aaa_uri)
            self.assert200(response)
        self.assertJSONEqual(
            response.json,
            {'$type': 'type',
             '$uri': aaa_uri,
             'machines': [{'$ref': machine_uri}],
             'name': 'aaa',
             'version': None,
             })
        counter.assert_count(1)
