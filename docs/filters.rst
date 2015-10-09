
.. _filters:


Field filters
=============


``Meta.allowed_filters`` can take one of three general formats:

- ``"*"`` filtering allowed on all supported field types
- ``["f1", "f2"]`` filtering allowed on fields ``'f1'`` and ``'f2'``, provided they are supported by any comparators.
- ``{"f1": ["$eq", "$lt"], "f2": "*"}`` for each field specify available comparators.


Built-in comparators
--------------------

=============  ============================================  ========================================
Comparator     Description                                   Used with
=============  ============================================  ========================================
---            Equal                                         :class:`fields.Boolean`, :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.ToOne`
$ne            Not equal                                     :class:`fields.Boolean`, :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`, :class:`fields.ToOne`
$in            In (expects a list)                           :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`
$lt            Less than                                     :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`
$gt            Greater than                                  :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`
$lte           Less than or equal                            :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`
$gte           Greater than or equal                         :class:`fields.String`, :class:`fields.Integer`, :class:`fields.Number`
$text          Text search (PostgreSQL)                      :class:`fields.String`
$startswith    Starts with                                   :class:`fields.String`
$endswith      Ends with                                     :class:`fields.String`
$istartswith   Starts with (case insensitive)                :class:`fields.String`
$iendswith     Ends with (case insensitive)                  :class:`fields.String`
=============  ============================================  ========================================
