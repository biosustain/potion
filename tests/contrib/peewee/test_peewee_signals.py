from functools import partial
from peewee import CharField, ForeignKeyField
from flask_potion.contrib.peewee import PeeweeManager
from flask_potion import signals
from flask_potion.routes import Relation
from flask_potion.resource import ModelResource
from flask_potion import Api
from tests import BaseTestCase
from blinker._utilities import contextmanager
from blinker import ANY
from tests.contrib.peewee import PeeweeTestDB


class PeeweeSignalTestCase(BaseTestCase):
    def setUp(self):
        super(PeeweeSignalTestCase, self).setUp()
        app = self.app
        app.config['DATABASE'] = 'sqlite://'

        self.db = db = PeeweeTestDB(self.app)
        self.api = Api(self.app, default_manager=PeeweeManager)

        class User(db.Model):
            name = CharField(max_length=60)
            gender = CharField(max_length=1, null=True)

            parent = ForeignKeyField('self', null=True, related_name='children')

            def __eq__(self, other):
                return self.name == other.name

            def __repr__(self):
                return 'User({})'.format(self.name)

        class Group(db.Model):
            name = CharField(max_length=60)

        class GroupMembership(db.Model):
            user = ForeignKeyField(User)
            group = ForeignKeyField(Group)

        db.database.connect()
        db.database.create_tables([User, Group, GroupMembership])


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
            self.assertJSONEqual({'$uri': '/user/1', "name": "Foo", "gender": None}, response.json)


    def test_update_signal(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)

        with self.assertSignals([
            (signals.before_update, self.UserResource, {'changes': {'gender': 'M', 'name': 'Bar'},
                                                        'item': self.User(name="Bar")}),
            (signals.after_update, self.UserResource, {'changes': {'gender': 'M', 'name': 'Bar'},
                                                       'item': self.User(name="Bar")})
        ]):
            response = self.client.patch('/user/1', data={"name": "Bar", "gender": "M"})
            self.assert200(response)
            self.assertJSONEqual({'$uri': '/user/1', "name": "Bar", "gender": "M"}, response.json)

    def test_delete_signal(self):
        response = self.client.post('/user', data={"name": "Foo"})
        self.assert200(response)

        with self.assertSignals([
            (signals.before_delete, self.UserResource, {'item': self.User(name="Foo")}),
            (signals.after_delete, self.UserResource, {'item': self.User(name="Foo")})
        ]):
            response = self.client.delete('/user/1')
            self.assertStatus(response, 204)

    def test_relation_signal(self):

        response = self.client.post('/user', data={"name": "Foo"})
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
            self.assert200(response)

            response = self.client.post('/user/1/children', data={"$ref": "/user/2"})
            self.assert200(response)

            response = self.client.delete('/user/1/children/2')
            self.assertStatus(response, 204)