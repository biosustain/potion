# Potion

<p style="text-align:center">
    <img src="https://raw.githubusercontent.com/biosustain/potion/master/docs/_static/Potion.png">
</p>

## Inspiration & Alternatives

Potion used to be based on Flask-RESTful. It no longer shares any code with Flask-RESTful, but there are some residual
similarities, particularly when it comes to fields. Python-Eve and Flask-Classy are the other two major inspirations.
Eve is a good alternative for those seeking to work with MongoDB, which is not yet supported in Potion.

## Planned Features

- RESTful API for SQLAlchemy-driven web services
- Self-documenting
- Built-in filtering, sorting, pagination, caching, object & role-based permissions
- Built-in Python Client


## Description (Planned)

Potion is an opinionated self-documenting JSON-based RESTful API framework for SQLAlchemy. It ships complete with an
object & role-based permission system, resource-to-resource references, sub–routes & collections, validation, caching,
pagination, filtering & sorting.

Potion aims to be accessible to individuals using the command-line and to software clients. This expresses itself, among
other things, in the option to define _natural keys_ for referring to resource-item references. Potion is an all-round
API solution with both a Python- and a HTTP-API. To avoid database inconsistency issues, all importing & exporting
should be done through the Potion API and not the underlying SQLAlchemy models.

Potion strongly encourages a flat relational structure without many levels of sub-resources. Shallow relationships are
easy to add; deep relationships can be modeled where necessary — however not as resource-items with IDs, but rather as
ID-free objects and lists. Relationships in Potion encourage an API that is somewhere in-between of what MongoDB/NoSQL
and PostgreSQL/SQL can be in terms of relational structure. Some level of aggregation is still expected to be done on
the client side.

Furthermore, Potion's caching structure — still under development — is designed to work best where those resources that
have sub-collections are relatively small in number. The sub-collection in a relationship is best placed on the resource
that typically has the most children (e.g. `/group/{id}/members` and not `/user/{id}/groups`).

While Potion can be used with any database supported by SQLAlchemy, it primarily targets PostgreSQL and has
PostgreSQL-specific features relying on text-search indexes & JSON/JSONB column types.

Long-term aims of the framework include support for message-driven communication with the client, potentially using
WebSocket and `asyncio`.
