============
Flask-Potion
============


.. image:: https://img.shields.io/travis/biosustain/potion/master.svg?style=flat-square
    :target: https://travis-ci.org/biosustain/potion

.. image:: https://img.shields.io/coveralls/biosustain/potion/master.svg?style=flat-square
    :target: https://coveralls.io/r/biosustain/potion

.. image:: https://img.shields.io/pypi/v/Flask-Potion.svg?style=flat-square
    :target: https://pypi.python.org/pypi/Flask-Potion

.. image:: https://img.shields.io/pypi/l/Flask-Potion.svg?style=flat-square
    :target: https://pypi.python.org/pypi/Flask-Potion

.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/biosustain/potion
   :target: https://gitter.im/biosustain/potion?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

|

.. image:: https://raw.githubusercontent.com/biosustain/potion/master/docs/_static/Potion.png
   :alt: Flask-Potion
   :align: center
   :height: 150


Description
===========

**Flask-Potion** is a powerful Flask extension for building RESTful JSON APIs.
Potion features include validation, model resources and routes, relations, object permissions, filtering, sorting,
pagination, signals, and automatic API schema generation.

Potion is ships with backends for **SQLAlchemy**, **peewee** and **MongoEngine** models. It is possible to add backends for other data stores, or even to use a subset of Potion without any data store at all.

API client libraries for `Python <https://github.com/biosustain/potion-client>`_ and `JavaScript/TypeScript <https://github.com/biosustain/potion-node>`_ (generic Node as well as AngularJS 1/2) are available.

User's Guide
^^^^^^^^^^^^

The user's guide and documentation is published here:

   `http://potion.readthedocs.org/ <http://potion.readthedocs.org/en/latest/>`_

Versioning
^^^^^^^^^^

Potion will use semantic versioning from v1.0.0. Until then, the minor version is used for changes known to be breaking.

Features
========

- Powerful API framework both for data-store-linked and plain resources
- JSON-based and fully self-documenting with JSON Hyper-Schema
- Backend integrations:

  - Flask-SQLAlchemy
  - Peewee (contributed by `Michael Lavers <https://github.com/kolanos>`_)
  - Flask-MongoEngine

- Filtering, sorting, pagination, validation, built right in
- Smart system for handling relations between resources
- Natural keys for extra simple relation querying
- Easy-to-use, yet highly flexible, optional permissions system
- Signals for pre- and post-processing of requests
- Very customizable — everything is just a resource, route, or schema
- Access APIs more easily with client libraries for `Python <https://github.com/biosustain/potion-client>`_ and `JavaScript/TypeScript <https://github.com/biosustain/potion-node>`_ (generic Node and AngularJS 1/2)


Example *(SQLAlchemy)*
======================

.. code-block:: python

    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_potion import Api, ModelResource, fields
    from flask_potion.routes import ItemRoute

    app = Flask(__name__)
    db = SQLAlchemy(app)
    api = Api(app)

    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(), nullable=False)

    db.create_all()

    class UserResource(ModelResource):
        class Meta:
            model = User

        @ItemRoute.GET
        def greeting(self, user) -> fields.String():
            return "Hello, {}!".format(user.name)

    api.add_resource(UserResource)

    if __name__ == '__main__':
        app.run()


Long-term goals
===============

The web nowadays is increasingly push rather than pull, so Potion is gradually building up to providing a scalable WebSocket 
service (using ``asyncio`` and a message queue). This service will mirror the RESTful API so that every GET request can be done *"live"*. (In the meantime, you can use the ``signals`` module to roll your own solution).

Potion is written in a way that makes it very easy to cache resources. A natural goal is to eventually ship Potion with a built-in server-side caching solution.


Authors
=======

Potion is written and maintained by `Lars Schöning <https://github.com/lyschoening>`_.

`Peewee <https://peewee.readthedocs.org/en/latest/>`_ backend support has been contributed by `Michael Lavers <https://github.com/kolanos>`_.

`MongoEngine <http://mongoengine.org/>`_ backend support has been contributed by `João Cardoso <https://github.com/joaocardoso>`_.

`See here for the full list of contributors <https://github.com/biosustain/potion/graphs/contributors>`_.
