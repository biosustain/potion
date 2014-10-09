from collections import namedtuple, OrderedDict
import json

from flask import url_for, request
from flask.views import MethodViewType
import itertools

from flask.ext.potion import fields
from flask.ext.potion.routes import route
from flask.ext.potion.schema import Schema


class Link(namedtuple('Link', ('uri', 'rel'))):
    pass

class Set(Schema):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """

    def __init__(self, type, default_sort=None):
        pass

    def get(self, items, where=None, sort=None, page=None, per_page=None):

        items = self._filter_where(items, where)
        items = self._sort_by(items, sort)
        items = self._paginate(items, page, per_page)


        return items, 200, {
            "Link": ','.join(str(link) for link in (
                Link(self.resource.schema.uri, rel="describedBy"),
            ))
        }

    def put(self, item, child):
        raise NotImplementedError()

    def delete(self, item, child):
        raise NotImplementedError()



class ResourceMeta(MethodViewType):
    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)

        if hasattr(class_, '_meta'):
            meta = {}
            schema = {}
            routes = {}

            try:
                meta = dict(getattr(class_, 'Meta').__dict__)
            except AttributeError:
                pass



def read(resource, attribute="self", *args, **kwargs):
    pass



class Resource(object):
    items = Set('resource-type')
    meta = None
    routes = None
    schema = None

    @classmethod
    def get_item_id(cls, item):
        pass

    @classmethod
    def get_item_url(cls, item):
        return url_for(cls.read.endpoint, id=cls.get_item_id(item.id))

    # XXX move somewhere better if possible
    @classmethod
    def get_item_from_id(cls, id):
        pass

    @classmethod
    def get_items_query(cls):

    @route.GET('/', rel="instances")
    def instances(self) -> Set('resource-type'):
        where = None
        sort = None

        try:
            if "where" in request.args:
                where = json.loads(request.args["where"])
        except:
            abort(400, message='Bad filter: Must be valid JSON object')
            # FIXME XXX proper aborts & error messages

        self.items.get(self.get_items_query(),
                       where=resource.)

    @instances.POST(rel="create")
    def create(self, item_or_items) -> fields.Inline('self'):
        pass # TODO handle integrity errors

    create.schema = fields.Inline('self') # TODO
    create.response_schema = fields.Inline('self')

    @route.GET(lambda r: '/<{}:{}>'.format(r.meta.id_attribute, r.meta.id_converter), rel="self")
    def read(self, id) -> fields.Inline('self'):
        pass

    @read.PATCH(rel="update")
    def update(self, item, **kwargs) -> fields.Inline('self'):
        pass

    update.schema = None # TODO

    @update.DELETE(rel="destroy")
    def destroy(self, item):
        pass

    @route.GET('/schema', rel="describedBy")
    def schema(self): # No "targetSchema" because that would be way too meta.
        defn = OrderedDict()

        # copy title, description from Resource.meta
        for property in ('title', 'description'):
            value = getattr(self.meta, property)
            if value:
                defn[property] = value

        links = itertools.chain(*[route.get_links(self) for name, route in sorted(self.routes.items())])

        defn['type'] = 'object'
        defn.update(self.schema.response_schema)
        defn['links'] = list(links)

        # TODO enforce Content-Type: application/schema+json (overwritten by Flask-RESTful)
        return defn

    class Schema:
        pass

    class Meta:
        title = None
        description = None
        id_attribute = 'id'
        id_converter = 'int'
        id_field = fields.PositiveInteger()  # Must inherit from Integer or String
        include_fields = None
        exclude_fields = None
        allowed_filters = "*"
        permissions = {
            "read": "anyone",  # anybody, yes
            "create": "nobody",  # noone, no
            "update": "create",
            "delete": "update"
        }
        postgres_text_search_fields = ()
        postgres_full_text_index = None  # $fulltext
        read_only_fields = ()
        write_only_fields = ()
        natural_keys = ()
        cache = False


class StrainResource(Resource):

    class Meta:
        natural_keys = (

        )
        natural_keys_by_type = {
            'int': [resolvers.IDResolver()],
            'string': [],
            'object': [],
            'array': []
        }