import unittest
from flask_sqlalchemy import SQLAlchemy
from flask_potion import ModelResource, fields, Api
from tests import BaseTestCase



class FilterTestCase(BaseTestCase):
    def setUp(self):
        super(FilterTestCase, self).setUp()
        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.api = Api(self.app)
        self.sa = sa = SQLAlchemy(app)

        class User(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            first_name = sa.Column(sa.String(60), nullable=False)
            last_name = sa.Column(sa.String(60), nullable=False)

            gender = sa.Column(sa.String(1))

            age = sa.Column(sa.Integer)

            is_staff = sa.Column(sa.Boolean, default=None)

        class Thing(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)

            name = sa.Column(sa.String(60), nullable=False)

            belongs_to_id = sa.Column(sa.Integer, sa.ForeignKey(User.id))
            belongs_to = sa.relationship(User)

            date_time = sa.Column(sa.DateTime)
            date = sa.Column(sa.Date)

        sa.create_all()


        class UserResource(ModelResource):
            class Schema:
                gender = fields.String(enum=['f', 'm'], nullable=True)

            class Meta:
                model = User
                include_id = True

        class ThingResource(ModelResource):
            class Schema:
                belongs_to = fields.ToOne('user', nullable=True)

            class Meta:
                model = Thing

        class AllowUserResource(ModelResource):
            class Meta:
                model = User
                name = 'allow-user'
                filters = {
                    'first_name': ['eq'],
                    'is_staff': True
                }

        self.api.add_resource(UserResource)
        self.api.add_resource(ThingResource)
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

        response = self.client.get('/user?where={"age": {"$lt": 21.0}}')
        self.assert400(response)

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

    def test_sort_relationship(self):
        self.post_sample_set_a()

        response = self.client.get('/user')
        user_ids = [user['$id'] for user in response.json]

        for thing in [
            {'name': 'A', 'belongs_to': user_ids[0]},
            {'name': 'B', 'belongs_to': user_ids[2]},
            {'name': 'C', 'belongs_to': user_ids[1]},
            {'name': 'D', 'belongs_to': user_ids[4]},
            {'name': 'E', 'belongs_to': user_ids[3]}
        ]:
            response = self.client.post('/thing', data=thing)
            self.assert200(response)

        response = self.client.get('/thing?sort={"belongs_to": false}')
        self.assertEqual(sorted(response.json, key=lambda thing: thing['belongs_to']['$ref']), response.json)

        response = self.client.get('/thing?sort={"name": false, "belongs_to": false}')
        self.assertEqual(sorted(response.json, key=lambda thing: thing['name']), response.json)

    def test_sort_filter_date(self):
        for thing in [
            {'name': 'A', 'date_time': {'$date': 1446561100000}},
            {'name': 'B', 'date_time': {'$date': 1000000000000}},
            {'name': 'C', 'date_time': {'$date': 1446561110000}},
            {'name': 'D', 'date_time': {'$date': 1446561120000}},
            {'name': 'E', 'date_time': {'$date': 1446561130000}}
        ]:
            response = self.client.post('/thing', data=thing)
            self.assert200(response)

        response = self.client.get('/thing?sort={"date_time": false}')
        self.assertEqual(sorted(response.json, key=lambda thing: thing['date_time']['$date']), response.json)

        response = self.client.get('/thing?where={"date_time": {"$eq": {"$date": 1000000000000}}}')
        print(response.json)

        self.assertEqualWithout([
            {'name': 'B', 'date_time': {'$date': 1000000000000}},
        ], response.json,
            without=['$uri', 'date', 'belongs_to'])

        response = self.client.get('/thing?where={"date_time": {"$gt": {"$date": 1000000000000}}}')
        self.assertEqualWithout([
            {'name': 'A', 'date_time': {'$date': 1446561100000}},
            {'name': 'C', 'date_time': {'$date': 1446561110000}},
            {'name': 'D', 'date_time': {'$date': 1446561120000}},
            {'name': 'E', 'date_time': {'$date': 1446561130000}}
        ], response.json,
            without=['$uri', 'date', 'belongs_to'])

        response = self.client.get('/thing?where={"date_time": {"$lt": {"$date": 1000000000000}}}')
        self.assertEqualWithout([], response.json, without=['$uri', 'date', 'belongs_to'])

        response = self.client.get('/thing?where={"date_time": {"$between": [{"$date": 1446561110000}, {"$date": 1446561120000}]}}')
        self.assertEqualWithout([
            {'name': 'C', 'date_time': {'$date': 1446561110000}},
            {'name': 'D', 'date_time': {'$date': 1446561120000}},
        ], response.json, without=['$uri', 'date', 'belongs_to'])

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
