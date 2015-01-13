import datetime
from math import ceil
import six
from flask_potion import fields


class Relation(object):
    def __init__(self, manager, resource, attribute, target_resource):
        self.manager = manager
        self.resource = resource
        self.attribute = attribute
        self.target_resource = target_resource

    def instances(self, item, page=None, per_page=None):
        raise NotImplementedError()

    def add(self, item, target_item):
        raise NotImplementedError()

    def remove(self, item, target_item):
        raise NotImplementedError()


class Manager(object):
    relation_type = Relation
    supported_comparators = ()

    def __init__(self, resource, model):
        self.resource = resource
        self.model = model

    @staticmethod
    def _get_field_from_python_type(python_type):
        try:
            return {
                str: fields.String,
                six.text_type: fields.String,
                int: fields.Integer,
                float: fields.Number,
                bool: fields.Boolean,
                list: fields.Array,
                dict: fields.Object,
                datetime.date: fields.DateString,
                datetime.datetime: fields.DateTimeString
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def relation_factory(self, attribute, target_resource=None):
        return self.relation_type(self, self.resource, attribute, target_resource)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        pass

    def instances(self, where=None, sort=None):
        pass

    def create(self, properties, commit=True):
        pass

    def read(self, id):
        pass

    def update(self, item, changes, commit=True):
        pass

    def delete(self, item):
        pass

    def delete_by_id(self, id):
        return self.delete(self.read(id))

    def commit(self):
        pass

    def begin(self):
        pass


class Pagination(object):

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total

    @property
    def pages(self):
        return int(ceil(self.total / self.per_page))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @classmethod
    def from_list(cls, items, page, per_page):
        start = per_page * (page - 1)
        return Pagination(items[start:start + per_page], page, per_page, len(items))