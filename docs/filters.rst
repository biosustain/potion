
.. module:: flask_potion

.. _sec_filters:

=======
Filters
=======

Filter expressions
------------------

.. versionchanged:: 0.11
   ``Meta.allowed_filters`` has been renamed to ``Meta.filters`` and the format for filter expressions has changed.

``Meta.filters`` may contain an expression used to specify which properties of items belonging to a resource can be filtered, and how.

The `filters` expression can be a :class:`bool` or a :class:`dict` keyed by field names. The values of the
:class:`dict` can be either a :class:`bool` or a list of filter names. The ``'*'`` attribute is a wildcard
for any remaining field names.

For example, the following allows all filters:

::

    filters = True

The following allows filtering on the ``"name"`` field:

::

    filters = {
        "name": True
    }

The following allows filtering by equals and not equals on the ``"name"`` field:

::

    filters = {
        "name": ['eq', 'ne']
    }

In addition it is also possible to specify custom filters this way:

::

    filters = {
        "name": {
            "text": MyTextFilter
        },
        "*": True
    }


Built-in default filters
------------------------

Filters are implemented for each contributed backend individually. The following filter classes are implemented for
most or all backends:

=============  ========================================  ============================================  ================================================================================================================================================================================================================================================
Name           Filter class                              Description                                   Used with
=============  ========================================  ============================================  ================================================================================================================================================================================================================================================
---            :class:`filters.EqualFilter`              Equal                                         :class:`fields.Boolean`, :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.ToOne`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
ne             :class:`filters.NotEqualFilter`           Not equal                                     :class:`fields.Boolean`, :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.ToOne`
in             :class:`filters.InFilter`                 In (expects an Array)                         :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
contains       :class:`filters.ContainsFilter`           Contains                                      :class:`fields.Array`, :class:`fields.ToMany`
lt             :class:`filters.LessThanFilter`           Less than                                     :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
gt             :class:`filters.GreaterThanFilter`        Greater than                                  :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
lte            :class:`filters.LessThanEqualFilter`      Less than or equal                            :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
gte            :class:`filters.GreaterThanEqualFilter`   Greater than or equal                         :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
contains       :class:`filters.StringContainsFilter`     Contains (String)                             :class:`fields.String`
icontains      :class:`filters.StringIContainsFilter`    Contains (String, case-insensitive)           :class:`fields.String`
startswith     :class:`filters.StartsWithFilter`         Starts with                                   :class:`fields.String`
endswith       :class:`filters.EndsWithFilter`           Ends with                                     :class:`fields.String`
istartswith    :class:`filters.IStartsWithFilter`        Starts with (case-insensitive)                :class:`fields.String`
iendswith      :class:`filters.IEndsWithFilter`          Ends with (case-insensitive)                  :class:`fields.String`
between        :class:`filters.DateBetweenFilter`        Date between                                  :class:`fields.Date`, :class:`fields.DateTime`, :class:`fields.DateString`, :class:`fields.DateTimeString`
=============  ========================================  ============================================  ================================================================================================================================================================================================================================================

.. note::

   :class:`filters.EqualFilter` uses both the keys ``'eq'`` and ``None``. This is so that you can write an equality comparison both ways:

   ::

      GET /user?where={"name": "foo"}
      GET /user?where={"name": {"$eq": "foo"}}


.. module:: flask_potion.filters

:class:`filters.BaseFilter`
---------------------------

.. versionadded:: 0.11

.. autoclass:: BaseFilter
   :members:
