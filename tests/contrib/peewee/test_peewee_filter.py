import unittest
from peewee import CharField, IntegerField, BooleanField
from flask_potion.contrib.peewee import PeeweeManager
from flask_potion import ModelResource, fields, Api
from tests import BaseTestCase
from tests.contrib.peewee import PeeweeTestDB


class PeeeeFilterTestCase(BaseTestCase):
    def setUp(self):
        super(PeeeeFilterTestCase, self).setUp()
        app = self.app
        app.config['DATABASE'] = 'sqlite://'

        self.db = db = PeeweeTestDB(self.app)
        self.api = Api(self.app, default_manager=PeeweeManager)
        app.debug = True

        class User(db.Model):
            id = IntegerField(primary_key=True)
            first_name = CharField(max_length=60, null=False)
            last_name = CharField(max_length=60, null=False)

            gender = CharField(max_length=1, null=True)

            age = IntegerField()

            is_staff = BooleanField(default=None)

        db.database.connect()
        db.database.create_tables([User])

        class UserResource(ModelResource):
            class Schema:
                gender = fields.String(enum=['f', 'm'], nullable=True)

            class Meta:
                model = User

        class AllowUserResource(ModelResource):
            class Meta:
                model = User
                name = 'allow-user'
                filters = {
                    'first_name': ['eq'],
                    'is_staff': True
                }

        self.api.add_resource(UserResource)
        self.api.add_resource(AllowUserResource)

    def post_sample_set_a(self):
        for user in [
            {'first_name': 'John', 'last_name': 'Doe', 'age': 32, 'is_staff': True, 'gender': 'm'},
            {'first_name': 'Jonnie', 'last_name': 'Doe', 'age': 25, 'is_staff': False, 'gender': 'm'},
            {'first_name': 'Jane', 'last_name': 'Roe', 'age': 18, 'is_staff': False, 'gender': 'f'},
            {'first_name': 'Joe', 'last_name': 'Bloggs', 'age': 21, 'is_staff': True, 'gender': 'm'},
            {'first_name': 'Sue', 'last_name': 'Watts', 'age': 25, 'is_staff': True}
        ]:
            response = self.client.post('/user', data=user)
            self.assert200(response)

    def test_equality(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": "Doe"}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                ], response.json, without=['$uri', '$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": 25}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe', 'age': 25},
                                    {'first_name': 'Sue', 'last_name': 'Watts', 'age': 25},
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'is_staff'])

        response = self.client.get('/user?where={"last_name": "Doe", "age": 25}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    def test_inequality(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": {"$ne": "Watts"}, "age": {"$ne": 32}}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$gt": 25}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$gte": 25}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$lte": 21}}')

        self.assertEqualWithout([
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$lt": null}}')
        self.assert400(response)

        response = self.client.get('/user?where={"first_name": {"$gt": "Jo"}}')
        self.assert400(response)

    def test_in(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": {"$in": ["Bloggs", "Watts"]}}')

        self.assertEqualWithout([
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"last_name": {"$in": []}}')

        self.assertEqualWithout([], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    def test_startswith(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"first_name": {"$startswith": "Jo"}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"first_name": {"$startswith": "J%e"}}')

        self.assertEqualWithout([], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    def test_istartswith(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"first_name": {"$istartswith": "jo"}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"first_name": {"$istartswith": "j%e"}}')

        self.assertEqualWithout([], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    def test_iendswith(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": {"$iendswith": "Oe"}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Jane', 'last_name': 'Roe'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"first_name": {"$istartswith": "j%e"}}')

        self.assertEqualWithout([], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    @unittest.SkipTest
    def test_text_search(self):
        self.post_sample_set_a()

        response = self.client.get('/user?search=sbc+dedf&rank=1')

    def test_sort(self):
        self.post_sample_set_a()

        response = self.client.get('/user?sort={"last_name": true, "first_name": false}')

        self.assert200(response)
        self.assertEqualWithout([
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json,
                                without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?sort={"age": false, "first_name": false}')

        self.assertEqualWithout([
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                ], response.json,
                                without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])


    def test_sort_and_where(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"first_name": {"$startswith": "Jo"}}&sort={"first_name": false}')

        self.assertEqualWithout([
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'}
                                ], response.json, without=['$uri', '$id', '$type', 'gender', 'age', 'is_staff'])

    @unittest.SkipTest
    def test_sort_pages(self):
        pass

    @unittest.SkipTest
    def test_disallowed_where_filters(self):
        pass

    @unittest.SkipTest
    def test_schema(self):
        pass


if __name__ == '__main__':
    unittest.main()
