
.. _field_types:

Field types
===========

.. module:: fields

:class:`Raw` field class
------------------------

.. autoclass:: Raw
   :members:

Reference field types
---------------------

.. autoclass:: ToOne

.. autoclass:: ToMany


Basic field types
-----------------

.. autoclass:: Any
   :members:

.. autoclass:: String
   :members:

.. autoclass:: Integer
   :members:

.. autoclass:: PositiveInteger
   :members:

.. autoclass:: Number
   :members:

.. autoclass:: Boolean
   :members:

.. autoclass:: Date
   :members:

.. autoclass:: DateTime
   :members:

.. autoclass:: DateString
   :members:

.. autoclass:: DateTimeString
   :members:

.. autoclass:: Uri
   :members:

.. autoclass:: UUID
   :members:

.. autoclass:: Custom
   :members:


Composite field types
---------------------

.. autoclass:: Array
   :members:

.. autoclass:: Object
   :members:

.. autoclass:: AttributeMapped
   :members:



SQLAlchemy-specific field types
-------------------------------

.. class:: contrib.alchemy.fields.InlineModel

   .. versionchanged:: 0.11
      Renamed from :class:`fields.sa.InlineModel` to :class:`contrib.alchemy.fields.InlineModel`.

   For creating SQLAlchemy models without having to give them their own resource.

   Usage example:

   .. code-block:: python

      class FooResource(Resource):
         class Meta:
            model = Foo

         class Schema:
            # Here, Foo.bars is a collection of Bar items
            bars = fields.List(fields.InlineModel({
                "name": fields.String(description="Bar name"),
                "height": fields.Integer(description="Height of bar")
            }, model=Bar))


   :param dict properties: A dictionary of :class:`Raw` objects
   :param model: An SQLAlchemy model


Internal types
--------------

Field types
^^^^^^^^^^^
.. autoclass:: Inline
   :members:


.. autoclass:: ItemType
   :members:


.. autoclass:: ItemUri
   :members:

Schema types
^^^^^^^^^^^^

.. module:: schema

.. autoclass:: Schema
    :members:

.. autoclass:: FieldSet
    :members:
