
========
Managers
========

Manager base class
^^^^^^^^^^^^^^^^^^

.. module:: flask_potion

:class:`manager.Manager` is used by :class:`ModelResource` to implement a backend integration.

.. autoclass:: flask_potion.manager.Manager
   :members:

.. autoclass:: flask_potion.manager.RelationalManager

Manager implementations
^^^^^^^^^^^^^^^^^^^^^^^

The following backend managers ship with *Flask-Potion*:

.. autoclass:: contrib.memory.MemoryManager
   :members:

.. autoclass:: contrib.alchemy.SQLAlchemyManager
   :members:

.. autoclass:: contrib.peewee.PeeweeManager
   :members:

.. autoclass:: contrib.mongoengine.MongoEngineManager
   :members:

Additionally, :class:`contrib.alchemy.SQLAlchemyManager` can be extended with
:class:`contrib.principals.PrincipalsMixin` to form a new manager that implements a permissions system based on *Flask-Principals*.
