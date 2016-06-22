from functools import wraps
import unittest
from flask import current_app, request
from flask_principal import Identity, identity_changed, identity_loaded, RoleNeed, UserNeed, Principal, ItemNeed
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from werkzeug.exceptions import Unauthorized

from flask_potion.contrib.memory import MemoryManager
from flask_potion.contrib.alchemy import SQLAlchemyManager
from flask_potion.routes import Relation
from flask_potion import Api, fields
from flask_potion.contrib.principals import principals
from flask_potion.resource import ModelResource
from tests import ApiClient, BaseTestCase


class AuthorizedApiClient(ApiClient):
    def open(self, *args, **kw):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        auth = kw.pop('auth', True)
        headers = kw.pop('headers', [])

        if auth:
            headers.append(('Authorization', 'Basic OnBhc3N3b3Jk'))
        return super(AuthorizedApiClient, self).open(*args, headers=headers, **kw)


class PrincipalResource(ModelResource):
    class Meta:
        manager = principals(SQLAlchemyManager)


class PrincipalTestCase(BaseTestCase):
    def create_app(self):
        app = super(PrincipalTestCase, self).create_app()
        app.test_client_class = AuthorizedApiClient

        self.principal = Principal(app)
        self.sa = sa = SQLAlchemy(app)

        class User(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String())

        class BookStore(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String())

            owner_id = sa.Column(sa.Integer, sa.ForeignKey(User.id))
            owner = sa.relationship(User, backref=backref('stores', lazy='dynamic'))

        class Book(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String(), nullable=False)

            author_id = sa.Column(sa.Integer, sa.ForeignKey(User.id))
            author = sa.relationship(User, backref=backref('books', lazy='dynamic'))

        class BookSigning(sa.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            book_id = sa.Column(sa.Integer, sa.ForeignKey(Book.id), nullable=False)
            store_id = sa.Column(sa.Integer, sa.ForeignKey(BookStore.id), nullable=False)

            book = sa.relationship(Book)
            store = sa.relationship(BookStore)

        sa.create_all()

        for model in (BookStore, User, Book, BookSigning):
            setattr(self, model.__tablename__.upper(), model)

        return app

    def setUp(self):
        super(PrincipalTestCase, self).setUp()
        self.mock_user = None

        @identity_loaded.connect_via(self.app)
        def on_identity_loaded(sender, identity):
            identity.provides.add(UserNeed(identity.id))

            for role in self.mock_user.get('roles', []):
                identity.provides.add(RoleNeed(role))

            for need in self.mock_user.get('needs', []):
                identity.provides.add(need)

        def authenticate(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                auth = request.authorization

                if not auth:
                    raise Unauthorized()

                if auth.password == 'password':
                    identity_changed.send(current_app._get_current_object(), identity=Identity(self.mock_user['id']))
                else:
                    raise Unauthorized()
                return fn(*args, **kwargs)

            return wrapper

        self.api = Api(self.app, decorators=[authenticate])

    def test_role(self):
        with self.assertRaises(RuntimeError):
            manager = principals(MemoryManager)

    def test_role(self):
        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'create': 'author'
                }

        self.api.add_resource(BookResource)

        response = self.client.post('/book', data={'title': 'Foo'}, auth=False)
        self.assert401(response)

        self.mock_user = {'id': 1}
        response = self.client.post('/book', data={'title': 'Foo'})
        self.assert403(response)

        self.mock_user = {'id': 1, 'roles': ['author']}
        response = self.client.post('/book', data={'title': 'Foo'})
        self.assert200(response)
        self.assertEqual({'title': 'Foo', '$uri': '/book/1'}, response.json)

        self.assert200(self.client.patch('/book/1', data={'title': 'Foo I'}))

        self.mock_user = {'id': 1}
        self.assert403(self.client.patch('/book/1', data={'title': 'Bar'}))

        self.assert403(self.client.delete('/book/1'))

        # self.user = {'id': 1, 'roles': ['author']}
        # self.assert200(self.client.delete('/book/1'))

        # response = self.client.post('/book', data={'title': 'Foo'})
        #
        # self.assert200(response)

    def test_access_forbidden_to_resource_collection(self):
        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': 'author',
                    'create': 'author',
                }

        self.api.add_resource(BookResource)
        self.mock_user = {'id': 1, 'roles': ['author']}
        response = self.client.post('/book', data={'title': 'Foo'})
        self.assert200(response)
        self.assertEqual({'title': 'Foo', '$uri': '/book/1'}, response.json)
        self.assert200(self.client.get('/book'))
        self.mock_user = {'id': 1}
        self.assert403(self.client.get('/book'))

    def test_inherit_role_to_one_field(self):

        class BookStoreResource(PrincipalResource):
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin']
                }

        class BookSigningResource(PrincipalResource):
            class Schema:
                book = fields.ToOne('book')
                store = fields.ToOne('book_store')

            class Meta:
                model = self.BOOK_SIGNING
                permissions = {
                    'create': 'update:store'
                }

        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'create': 'yes'
                }

        self.api.add_resource(BookStoreResource)
        self.api.add_resource(BookSigningResource)
        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book_store', data={
            'name': 'Foo Books'
        }))

        self.assert200(self.client.post('/book', data={
            'title': 'Bar'
        }))

        self.mock_user = {'id': 2}

        response = self.client.post('/book_signing', data={
            'book': {'$ref': '/book/1'},
            'store': {'$ref': '/book_store/1'}
        })
        self.assert403(response)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book_signing', data={
            'book': {'$ref': '/book/1'},
            'store': {'$ref': '/book_store/1'}
        }))

    def test_user_need(self):

        class BookStoreResource(PrincipalResource):
            class Schema:
                owner = fields.ToOne('user')

            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin', 'user:owner']
                }

        class UserResource(PrincipalResource):
            class Meta:
                model = self.USER
                permissions = {
                    'create': 'admin',
                    'update': 'user:$uri'
                }

        self.api.add_resource(BookStoreResource)
        self.api.add_resource(UserResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        self.assert200(self.client.post('/user', data={'name': 'Admin'}))
        self.assert200(self.client.patch('/user/1', data={'name': 'Other'}))

        for i, store in enumerate([
            {
                'name': 'Books & More',
                'owner': {
                    'name': 'Mr. Moore'
                }
            },
            {
                'name': 'Foo Books',
                'owner': {
                    'name': 'Foo'
                }
            }
        ]):
            response = self.client.post('/user', data=store['owner'])

            owner = {'$ref': response.json['$uri']}
            response = self.client.post('/book_store', data={
                'name': store['name'],
                'owner': owner
            })

            self.assertEqual({'$uri': '/book_store/{}'.format(i + 1), 'name': store['name'], 'owner': owner},
                             response.json)

        response = self.client.patch('/book_store/1', data={'name': 'books & moore'})
        self.assert200(response)

        self.mock_user = {'id': 3}
        response = self.client.patch('/book_store/1', data={'name': 'Books & Foore'})
        self.assert403(response)

        self.mock_user = {'id': 2}
        response = self.client.patch('/book_store/1', data={'name': 'Books & Moore'})

        self.assert200(response)

        self.assertEqual({
            '$uri': '/book_store/1',
            'name': 'Books & Moore',
            'owner': {'$ref': '/user/2'}
        }, response.json)

        response = self.client.patch('/book_store/2', data={'name': 'Moore Books'})
        self.assert403(response)

    def test_item_need_update(self):

        class BookStoreResource(PrincipalResource):
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': 'update'
                }

        self.api.add_resource(BookStoreResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        # response = self.client.post('/book_store', data=[
        # {'name': 'Bar Books'},
        #     {'name': 'Foomazon'}
        # ])
        response = self.client.post('/book_store', data={'name': 'Bar Books'})
        self.assert200(response)
        response = self.client.post('/book_store', data={'name': 'Foomazon'})
        self.assert200(response)

        self.mock_user = {'id': 1, 'needs': [ItemNeed('update', 2, 'book_store')]}

        self.assert403(self.client.patch('/book_store/1', data={'name': 'Foo'}))

        response = self.client.patch('/book_store/2', data={'name': 'Foo'})
        self.assert200(response)
        self.assertEqual({'$uri': '/book_store/2', 'name': 'Foo'}, response.json)

        # TODO DELETE

    def test_yes_no(self):
        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': 'yes',
                    'create': 'admin',
                    'update': 'no'
                }

        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book', data={'title': 'Foo'}))
        self.assert403(self.client.patch('/book/1', data={'title': 'Bar'}))
        self.assert200(self.client.get('/book/1'))
        self.assert200(self.client.get('/book'))

    def test_item_need_read(self):

        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': ['owns-copy', 'admin'],
                    'create': 'admin',
                    'owns-copy': 'owns-copy'
                }

        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        # TODO Bulk inserts
        # response = self.client.post('/book', data=[
        # {'title': 'GoT Vol. {}'.format(i + 1)} for i in range(20)
        # ])

        for i in range(20):
            self.client.post('/book', data={'title': 'GoT Vol. {}'.format(i + 1)})

        self.assertEqual(20, len(self.client.get('/book').json))

        self.mock_user = {'id': 2, 'needs': [ItemNeed('owns-copy', i, 'book') for i in (1, 4, 6, 8, 11, 15, 19)]}
        self.assertEqual(7, len(self.client.get('/book').json))

        self.mock_user = {'id': 3, 'needs': [ItemNeed('owns-copy', i, 'book') for i in (2, 7, 19)]}

        self.assertEqual([
            {'$uri': '/book/2', 'title': 'GoT Vol. 2'},
            {'$uri': '/book/7', 'title': 'GoT Vol. 7'},
            {'$uri': '/book/19', 'title': 'GoT Vol. 19'}
        ], self.client.get('/book').json)

        self.assert404(self.client.get('/book/15'))
        self.assert200(self.client.get('/book/2'))
        self.assert200(self.client.get('/book/7'))
        self.assert404(self.client.get('/book/1'))
        self.assert404(self.client.get('/book/99'))

        self.mock_user = {'id': 4}
        self.assertEqual([], self.client.get('/book').json)

    def test_relationship(self):
        "should require update permission on parent resource for updating, read permissions on both"

        class BookResource(PrincipalResource):
            class Schema:
                author = fields.ToOne('user', nullable=True)

            class Meta:
                model = self.BOOK
                permissions = {
                    'read': ['owns-copy', 'update', 'admin'],
                    'create': 'writer',
                    'update': 'user:author',
                    'owns-copy': 'owns-copy'
                }

        class UserResource(PrincipalResource):
            books = Relation(BookResource)

            class Meta:
                model = self.USER
                permissions = {
                    'create': 'admin'
                }

        self.api.add_resource(UserResource)
        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        for user in [
            {'name': 'Admin'},
            {'name': 'Author 1'},
            {'name': 'Author 2'}
        ]:
            response = self.client.post('/user', data=user)
            self.assert200(response)

        response = self.client.post('/book', data={
            'title': 'Foo'
        })
        self.assert403(response)

        self.mock_user = {'id': 2, 'roles': ['writer']}
        response = self.client.post('/book', data={
            'author': {'$ref': '/user/2'},
            'title': 'Bar'
        })

        self.assert200(response)

        self.mock_user = {'id': 3, 'roles': ['writer']}

        response = self.client.post('/book', data={'title': 'Spying: Novel'})
        self.assert200(response)

        response = self.client.post('/book', data={'title': 'Spied: The Sequel'})
        self.assert200(response)

        response = self.client.post('/book', data={'title': 'Spy: The Prequel'})
        self.assert200(response)
        self.assertJSONEqual({'$uri': '/book/4', 'author': None, 'title': 'Spy: The Prequel'}, response.json)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.client.post('/user/3/books', data={'$ref': '/book/2'})
        self.client.post('/user/3/books', data={'$ref': '/book/3'})
        self.client.post('/user/3/books', data={'$ref': '/book/4'})

        self.mock_user = {'id': 3, 'roles': ['writer']}
        self.assert200(response)

        response = self.client.get('/user/3/books')
        self.assert200(response)
        self.assertEqual(3, len(response.json))  # read -> update -> user:author

        self.mock_user = {'id': 4, 'needs': [ItemNeed('owns-copy', 3, 'book')]}

        response = self.client.get('/user/3/books')
        self.assertEqual(1, len(response.json))  # read -> owns-copy

        self.assert200(self.client.get('/book/3'))
        self.assert404(self.client.get('/book/2'))

        self.mock_user = {'id': 5}
        response = self.client.get('/user/3/books')
        self.assertEqual(0, len(response.json))
        self.assert404(self.client.get('/book/2'))

    @unittest.SkipTest
    def test_item_route(self):
        "should require read permission on parent resource plus any additional permissions"
        pass

    def test_permission_circular(self):
        class BookResource(PrincipalResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': 'create',
                    'create': 'read',
                    'update': 'create',
                    'delete': 'update'
                }

        self.api.add_resource(BookResource)

        with self.assertRaises(RuntimeError):
            BookResource.manager._needs
