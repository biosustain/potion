from functools import partial
from flask_mongoengine import MongoEngine
from mongoengine import IntField, StringField, ReferenceField, ListField
from flask_potion.backends.mongoengine import MongoEngineManager
from flask_potion import signals
from flask_potion.routes import Relation
from flask_potion.resource import ModelResource
from flask_potion import Api
from tests import BaseTestCase
from blinker._utilities import contextmanager
from blinker import ANY


class MongoEngineSignalTestCase(BaseTestCase):
    def setUp(self):
        super(MongoEngineSignalTestCase, self).setUp()
        self.app.config['MONGODB_DB'] = 'potion-test-db'
        self.api = Api(self.app, default_manager=MongoEngineManager)
        self.me = me = MongoEngine(self.app)

        class User(me.Document):
            name = StringField(max_length=60, null=False)
            gender = StringField(max_length=1, null=True)

            children = ListField(ReferenceField("User"))

            def __eq__(self, other):
                return self.name == other.name

            def __repr__(self):
                return 'User({})'.format(self.name)

        class Group(me.Document):
            name = StringField(max_length=60, null=False)

        class GroupMembership(me.Document):
            user = ReferenceField(User)
            group = ReferenceField(Group)

        class UserResource(ModelResource):
            class Meta:
                model = User

            children = Relation('self')

        class GroupResource(ModelResource):
            class Meta:
                model = Group

            members = Relation(UserResource)

        self.User = User
        self.Group = Group
        self.UserResource = UserResource
        self.GroupResource = GroupResource
        self.api.add_resource(UserResource)
        self.api.add_resource(GroupResource)

    def tearDown(self):
        self.me.connection.drop_database('potion-test-db')

    @contextmanager
    def assertSignals(self, expected_events, sender=ANY):
        events = []

        def receiver_(signal, sender, **kwargs):
            events.append((signal, sender, kwargs))

        receivers = {
            signal: partial(receiver_, signal) for signal in [
            signals.before_create,
            signals.after_create,
            signals.before_update,
            signals.after_update,
            signals.before_delete,
            signals.after_delete,
            signals.before_add_to_relation,
            signals.after_add_to_relation,
            signals.before_remove_from_relation,
            signals.after_remove_from_relation
        ]
        }

        for signal, receiver in receivers.items():
            signal.connect(receiver, sender=sender, weak=False)

        try:
            yield None
        except:
            for signal, receiver in receivers.items():
                signal.disconnect(receiver)
            raise
        else:
            for signal, receiver in receivers.items():
                signal.disconnect(receiver)

            self.assertEqual(events, expected_events)

    def test_create_signal(self):
        with self.assertSignals([
            (signals.before_create, self.UserResource, {'item': self.User(name="Foo")}),
            (signals.after_create, self.UserResource, {'item': self.User(name="Foo")})
        ]):
            response = self.client.post('/user', data={"name": "Foo"})
            self.assert200(response)
            self.assertJSONEqual({'$uri': response.json["$uri"], "name": "Foo", "gender": None}, response.json)

    def test_update_signal(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)

        with self.assertSignals([
            (signals.before_update, self.UserResource, {'changes': {'gender': 'M', 'name': 'Bar'},
                                                        'item': self.User(name="Bar")}),
            (signals.after_update, self.UserResource, {'changes': {'gender': 'M', 'name': 'Bar'},
                                                       'item': self.User(name="Bar")})
        ]):
            uri = response.json["$uri"]
            response = self.client.patch(uri, data={"name": "Bar", "gender": "M"})
            self.assert200(response)
            self.assertJSONEqual({'$uri': uri, "name": "Bar", "gender": "M"}, response.json)

    def test_delete_signal(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)

        with self.assertSignals([
            (signals.before_delete, self.UserResource, {'item': self.User(name="Foo")}),
            (signals.after_delete, self.UserResource, {'item': self.User(name="Foo")})
        ]):
            response = self.client.delete(response.json["$uri"])
            self.assertStatus(response, 204)

    def test_relation_signal(self):

        response = self.client.post('/user', data={"name": "Foo"})
        user1_uri = response.json["$uri"]
        self.assert200(response)

        with self.assertSignals([
            (signals.before_create, self.UserResource, {'item': self.User(name="Bar")}),
            (signals.after_create, self.UserResource, {'item': self.User(name="Bar")}),
            (signals.before_add_to_relation, self.UserResource, {'item': self.User(name="Foo"),
                                                                 'attribute': 'children',
                                                                 'child': self.User(name="Bar")}),
            (signals.after_add_to_relation, self.UserResource, {'item': self.User(name="Foo"),
                                                                'attribute': 'children',
                                                                'child': self.User(name="Bar")}),
            (signals.before_remove_from_relation, self.UserResource, {'item': self.User(name="Foo"),
                                                                      'attribute': 'children',
                                                                      'child': self.User(name="Bar")}),
            (signals.after_remove_from_relation, self.UserResource, {'item': self.User(name="Foo"),
                                                                     'attribute': 'children',
                                                                     'child': self.User(name="Bar")})
        ]):
            response = self.client.post('/user', data={"name": "Bar"})
            user2_uri = response.json["$uri"]
            user2_id = user2_uri.split("/")[-1]
            self.assert200(response)

            response = self.client.post('{}/children'.format(user1_uri), data={"$ref": user2_uri})

            self.assert200(response)

            response = self.client.delete('{}/children/{}'.format(user1_uri, user2_id))
            self.assertStatus(response, 204)