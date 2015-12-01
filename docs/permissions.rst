
.. _permissions:

===================================
Permissions with *Flask-Principal*
===================================

.. module:: flask_potion

Flask-Potion includes a permission system. The permissions system is
built on `Flask-Principal <https://pythonhosted.org/Flask-Principal/>`_.
and enabled by decorating a :class:`manager.RelationalManager` with :class:`contrib.principals.principals`, which returns a class
extending both the manager and :class:`contrib.principals.PrincipalMixin`.

Permissions are specified as a ``dict`` in ``Meta.permissions``.


Defining Permissions
====================

There are four basic *actions* --- read, create, update, delete --- for which permissions must be defined. Additional
virtual actions can be declared for various purposes.

For example, the default permission declaration looks somewhat like this:

.. code-block:: python

    class Meta:
        permissions = {
            'read': 'yes',
            'create': 'no',
            'update': 'create',
            'delete': 'update'
        }


Patterns and *Needs* they produce:

==================== ===================================== ===================================================
Pattern              Matches                               Description
==================== ===================================== ===================================================
{action}             a key in the ``permissions`` dict  If equal to the action it is declared for
                                                           --- e.g. ``{'create': 'create'}`` --- evaluate to:

                                                           ``HybridItemNeed({action}, resource_name)``

                                                           Otherwise re-use needs from other action.
{role}               not a key in the ``permissions`` dict ``RoleNeed({role})``
{action}:{field}     *\*:\**                               Copy ``{action}`` permissions from ``ToOne``
                                                           linked resource at ``{field}``.
user:{field}         *user:\**                             ``UserNeed(item.{field}.id)`` for ``ToOne`` fields.
no, nobody           *no*                                  Do not permit.
yes, everybody       *yes*                                 Always permit.
==================== ===================================== ===================================================


.. note::

    When protecting an :class:`ItemRoute`, read access permissions, and updates using the resource manager  are checked automatically;
    for other actions, permissions have to be checked manually from within the function. The manager has helper functions such as
    :meth:`PrincipalMixin.can_update_item` to facilitate this.



Example API with permissions
============================

.. versionchanged:: 0.11
    The ``PrincipalManager`` extending ``SQLAlchemyManager`` has been replaced by a :meth:`principals` class-decorator.

We're going to go ahead and create an example API using :class:`PrincipalMixin` with
`Flask-Login <https://flask-login.readthedocs.org>`_ for authentication. Since there are quite a few moving parts, this
example is split up into several sections.

Our example is a simple blog with *articles* and *comments*. First, let's create the database models:

.. code-block:: python

    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import UserMixin
    from sqlalchemy.orm import relationship

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret'  # XXX replace with actual secret and don't keep it in source code

    db = SQLAlchemy(app)


    class User(UserMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(), nullable=False)
        is_admin = db.Column(db.Boolean(), default=False)
        is_editor = db.Column(db.Boolean(), default=False)


    class Article(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        author_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
        author = relationship(User)
        content = db.Column(db.Text)


    class Comment(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        article_id = db.Column(db.Integer, db.ForeignKey(Article.id), nullable=False)
        author_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
        article = relationship(Article)
        author = relationship(User)
        message = db.Column(db.Text)


    db.create_all()

We're going to use *Flask-Login* to authenticate requests using *Basic Authentication*:

.. code-block:: python

    from flask_login import LoginManager, current_user

    login_manager = LoginManager(app)


    @login_manager.request_loader
    def load_user_from_request(request):
        if request.authorization:
            username, password = request.authorization.username, request.authorization.password

            # XXX replace this with an actual password check.
            if username == password:
                return User.query.filter_by(username=username).first()
        return None


This is where *Flask-Principal* comes in. With every request it adds the *needs* the identity should provide.
Authenticated users are given a *user need* and maybe some *role needs*. If this example had some top-level object based permissions
(think groups, projects, teams, etc.) they would also be added here.

.. code-block:: python

    from flask_principal import Principal, Identity, UserNeed, AnonymousIdentity, identity_loaded, RoleNeed

    principals = Principal(app)

    @principals.identity_loader
    def read_identity_from_flask_login():
        if current_user.is_authenticated():
            return Identity(current_user.id)
        return AnonymousIdentity()


    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        if not isinstance(identity, AnonymousIdentity):
            identity.provides.add(UserNeed(identity.id))

            if current_user.is_editor:
                identity.provides.add(RoleNeed('editor'))

            if current_user.is_admin:
                identity.provides.add(RoleNeed('admin'))


Finally, we create our API with the ``login_required`` decorator from *Flask-Login*.


.. code-block:: python

    from flask_login import login_required
    from flask_potion import fields, signals, Api, ModelResource
    from flask_potion.contrib.alchemy import SQLAlchemyManager
    from flask_potion.contrib.principals import principals

    api = Api(app, decorators=[login_required])

    class PrincipalResource(ModelResource):
        class Meta:
            manager = principals(SQLAlchemyManager)


    class UserResource(PrincipalResource):
        class Meta:
            model = User


    class ArticleResource(PrincipalResource):
        class Schema:
            author = fields.ToOne('user')

        class Meta:
            model = Article
            read_only_fields = ['author']
            permissions = {
                'create': 'editor',
                'update': ['user:author', 'admin']
            }


    class CommentResource(PrincipalResource):
        class Schema:
            article = fields.ToOne('article')
            author = fields.ToOne('user')

        class Meta:
            model = Comment
            read_only_fields = ['author']
            permissions = {
                'create': 'anybody',
                'update': 'user:author',
                'delete': ['update:article', 'admin']
            }

    api.add_resource(UserResource)
    api.add_resource(ArticleResource)
    api.add_resource(CommentResource)

    # add the author to articles & comments when they are created:
    @signals.before_create.connect_via(ANY)
    def before_create_article_comment(sender, item):
        if issubclass(sender, (ArticleResource, CommentResource)):
            item.author_id = current_user.id


We've implemented the following permissions:

- only editors can create articles
- articles can be updated or deleted by either their authors or by admins
- comments can be created by anyone who is authenticated
- comments can updated only by the person who wrote the comment, but deleted both by admins
  and the author of the article

Now we just need to start the app:

.. code-block:: python

    if __name__ == '__main__':
        # add some example users & run the application
        db.session.add(User(username='editorA', is_editor=True))
        db.session.add(User(username='editorB', is_editor=True))
        db.session.add(User(username='admin', is_admin=True))
        db.session.add(User(username='user'))
        db.session.commit()

        app.run()

You can find the complete example code on
GitHub under::

    examples/permissions_example.py


.. code-block:: bash

    http --auth editorA:editorA :5000/article content=foo

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 71
    Content-Type: application/json
    Date: Sun, 08 Feb 2015 10:48:03 GMT
    Server: Werkzeug/0.9.6 Python/3.3.2
    Set-Cookie: session=.eJyrVorPTFGyUjK3SEw0TDOzSDRPtDRJtUxNMzZKM0pNNE4zNks1TU6zVNJRykxJzSvJLKnUSywtyYgvqSxIVbLKK83JQZIBGWVYCwBQWxtd.B7jQYw.Nhh6qE-h5WrGPfsYibXnDzCaJQM; HttpOnly; Path=/

    {
        "$uri": "/article/2",
        "author": {
            "$ref": "/user/1"
        },
        "content": "foo"
    }

Object-based permissions
------------------------

The example above did already *sort of* touch on object-based permissions, with the ``'user:author'`` pattern that restricts
access to the user who has authored a *comment* or *article*. We've also used permissions options, with more than one *need* potentially providing access. Finally, you have seen a hint of cascading object-based permissions with the
``'update:article'`` pattern that conditions access to the permissions on a relation.

There is another permission layer, building on :class:`flask_principal.ItemNeed`, for object-specific permissions. You would want to use them on something important, such as this *project* resource:

.. code-block:: python


    class ProjectResource(ModelResource):
        class Meta:
            manager = principals(SQLAlchemyManager)
            model = Project
            permissions = {
                'create': 'anybody',
                'update': 'manage',
                'manage': 'manage'
            }

To update a project, your identity needs this *need*::

    ItemNeed('manage', PROJECT_ID, 'project')

The pair ``{'manage': 'manage'}`` makes manage a new virtual action, which is why the :class:`flask_principals.ItemNeed` wants
a ``'manage'`` permission. We could also have written ``{'update': 'update'}`` --- then the required *need* would have been::

    ItemNeed('update', PROJECT_ID, 'project')

With cascading permissions, role-based, user-based, and object-based permissions you should now have all the tools to
implement all sorts of complex permissions setups.


:class:`PrincipalMixin` class
===============================

.. module:: flask_potion.contrib.principals

.. autoclass:: PrincipalMixin
    :members:


Efficiency
----------


Those who have worked with Flask-Principal know that it is on its own not well-suited for object-based permissions where large numbers of objects are involved, because each permission has
to be loaded into memory as ``ItemNeed`` at the start of the session.

The permission system built into Potion introduces the :class:`HybridNeed` and :class:`HybridPermission` classes to solve this issue.
They can either be evaluated directly or be applied to SQLAlchemy queries, and are therefore efficient with any number of object-based permissions.


.. module:: flask_potion.contrib.principals.needs

.. autoclass:: HybridNeed
    :members:

.. module:: flask_potion.contrib.principals.permission

.. autoclass:: HybridPermission
    :members:




