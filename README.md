# Potion

<p style="text-align:center">
    <img src="https://raw.githubusercontent.com/biosustain/potion/master/docs/_static/Potion.png" width="100">
</p>


## Description

Potion is an opinionated self-documenting JSON-based RESTful API framework for Flask and SQLAlchemy. It ships complete with an
object & role-based permission system, resource-to-resource references, customizable routes and all sorts of route-generation
goodies, a validation system that actually tells you where the errors are, signals, pagination, filtering & sorting.

Relationships in Potion encourage an API that is somewhere in-between of what MongoDB/NoSQL and PostgreSQL/SQL
can be in terms of relational structure. Some level of aggregation is still expected to be done on the client side.

The problem of RESTful referencing has been solved in Potion by including references as JSON-ref objects (e.g.
 `{"$ref": "/resource/1"}`). A REST client can resolve these references on the fly when parsing JSON from the API and the
 result is RESTful and cachable because there is always exactly one endpoint for each resource instance.
 Due to the extra requests this sometimes requires, you should use Potion with SPDY or the upcoming HTTP/2.

Potion can be used with any database supported by SQLAlchemy and it supports several PostgreSQL specific features
 such as text-search indexes & JSON/JSONB column types. Due to the way Potion is written,
it can very easily be extended for other storage engines.

# Immediate goals (add this to the description after release):

Potion aims to be accessible to individuals using the command-line and to software clients. This expresses itself, among
other things, in the option to define _natural keys_ for referring to resource-item references. Potion is an all-round
API solution with both a Python- and a HTTP-API. To avoid database inconsistency issues, all importing & exporting
should be done through the Potion API and not the underlying SQLAlchemy models.

# Long-term goals

Potion is written in a way that makes it very cachable and it is planned to eventually include an automatic and thorough
caching solution with Potion. The optional permissions system adds some complexity to the caching, but it's a problem
that can be solved.

Long-term aims of the framework also include support for message-driven communication with the client using
WebSocket and `asyncio`. Web applications today are push not pull, and any modern API should support subscriptions.
(If you need push notification today, you can already roll your own solution using Potion's signaling system).

## Python client

[Potion-client](https://github.com/biosustain/potion-client) is a Python REST client written to leverage the JSON Schema
and referencing features of Potion.

## Inspiration & Alternatives

The predecessor to Potion was to built on Flask-RESTful. There are still some similarities, particularly when it comes
to fields. Python-Eve and Flask-Classy are the other two major inspirations.
Eve is a good alternative for those seeking to work with MongoDB, which is not yet supported by Potion.

## Authors

Potion is written and maintained by [Lars Schöning](https://github.com/lyschoening).

[Thanks to our contributors](https://github.com/biosustain/potion/graphs/contributors).