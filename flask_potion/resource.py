from collections import namedtuple
from flask import url_for
from flask.views import MethodViewType
from flask.ext.potion import fields
from flask.ext.potion.schema import Schema
import resolvers


class Link(namedtuple('Link', ('uri', 'rel'))):
    pass

class Set(Schema):
    """
    This is what implements all of the pagination, filter, and sorting logic.
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

    @route.get(rel="self")
    def read(self, id_) -> fields.Inline('resource-type'):
        pass

    @route.GET(rel="instances")
    def instances(self) -> Set('resource-type'):
        pass

    @route.POST(rel="create")
    def create(self, item_or_items) -> fields.Inline('resource-type'):
        pass

    create.schema = None # TODO

    @item_route.PATCH(rel="update")
    def update(self, item, **kwargs) -> fields.Inline('resource-type'):
        pass

    update.schema = None # TODO

    @item_route.DELETE(rel="destroy")
    def destroy(self, item):
        pass

    @route.GET(rel="describedBy")
    def schema(self): # No "targetSchema" because that would be way too meta.
        pass

    class Meta:
        id_attribute = 'id'
        id_converter = 'int'
        id_field = fields.Integer()  # Must inherit from Integer or String
        include_fields = None
        exclude_fields = None
        allowed_filters = "*"
        permissions = {
            "read": "anyone",
            "create": "nobody",
            "update": "create",
            "delete": "update"
        }
        postgres_text_search_fields = ()
        postgres_full_text_index = ()  # $fulltext
        read_only_fields = ()
        write_only_fields = ()
        natural_keys = ()
        cache = False

