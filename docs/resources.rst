
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

A data store connection is maintained by :class:`backends.Manager`, which is set in ``Meta.manager`` and a *model* is usually provided in ``Meta.model``, with the managers typically making use of additional meta attributes.

.. autoclass:: ModelResource
    :members:


Managers
--------

:class:`Manager` is used by :class:`ModelResource` to implement a backend integration.


Manager base
^^^^^^^^^^^^

.. autoclass:: backends.Manager
   :members:

.. autoclass:: backends.Pagination
   :members:

Manager implementations
^^^^^^^^^^^^^^^^^^^^^^^


.. autoclass:: backends.memory.MemoryManager
   :members:


.. autoclass:: backends.alchemy.SQLAlchemyManager
   :members:

.. autoclass:: backends.peewee.PeeweeManager
   :members:

A third manager not listed here is :class:`contrib.principals.PrincipalManager`, which implements a permissions
system based on *Flask-Principals*.
