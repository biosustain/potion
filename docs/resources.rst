
=========
Resources
=========

:class:`Resource`
=================

:class:`Resource` is the base class for all other resource types and by contains only one route, which returns the schema
for the resource.

.. module:: flask_potion

.. autoclass:: Resource
    :members:

:class:`ModelResource`
======================

:class:`ModelResource` is written for create, read, update, delete actions on collections of items matching the resource schema.

.. autoclass:: ModelResource
    :members:

