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

Potion is designed to handle SQLAlchemy models, but it is also possible to integrate other data stores,
or even to use parts of Potion without any data store at all.


User's Guide
^^^^^^^^^^^^

The user's guide and documentation is published here:

   `http://potion.readthedocs.org/ <http://potion.readthedocs.org/en/latest/>`_


Features
========

- Powerful API framework both for data-store-linked and plain resources
- JSON-based and fully self-documenting with JSON Hyper-Schema
- *Flask-SQLAlchemy* integration
- Filtering, sorting, pagination, validation, built right in
- Smart system for handling relations between resources
- Easy-to-use, yet highly flexible, optional permissions system
- Signals for pre- and post-processing of requests
- Very customizable — everything is just a resource, route, or schema
- Natural keys for extra simple relation querying


Long-term goals
===============

The web nowadays is increasingly push rather than pull, so Potion is gradually building up to providing a scalable WebSocket 
service (using ``asyncio`` and a message queue). This service will mirror the RESTful API so that every GET request can be done *"live"*. (In the meantime, you can use the ``signals`` module to roll your own solution).

Potion is written in a way that makes it very easy to cache resources. A natural goal is to eventually ship Potion with a built-in server-side caching solution.


Authors
=======

Potion is written and maintained by `Lars Schöning <https://github.com/lyschoening>`_.

`Thanks to our contributors <https://github.com/biosustain/potion/graphs/contributors>`_.
