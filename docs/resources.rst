
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

A data store connection is maintained by a :class:`manager.Manager` instance.
The manager class can be specified in ``Meta.manager``; if no manager is specified, ``Api.default_manager`` is used.
Managers are configured through attributes in ``Meta``. Most managers expect a *model* to be defined under ``Meta.model``.

.. autoclass:: ModelResource
    :members:

