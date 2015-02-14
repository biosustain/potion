from __future__ import division
import datetime
from math import ceil

import six
from flask_potion.exceptions import ItemNotFound
from flask_potion import fields


class Manager(object):
    """

    .. attribute:: supported_comparators

        A tuple of names filter comparators supported by this manager.

    :param flask_potion.resource.Resource resource: resource class
    :param model: model read from ``Meta.model`` or ``None``
    """
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
                datetime.date: fields.Date,
                datetime.datetime: fields.DateTime
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        """

        :param item:
        :param attribute:
        :param target_resource:
        :param page:
        :param per_page:
        :return:
        """
        raise NotImplementedError()

    def relation_add(self, item, attribute, target_resource, target_item):
        """

        :param item:
        :param attribute:
        :param target_resource:
        :param target_item:
        :return:
        """
        raise NotImplementedError()

    def relation_remove(self, item, attribute, target_resource, target_item):
        """

        :param item:
        :param attribute:
        :param target_resource:
        :param target_item:
        :return:
        """
        raise NotImplementedError()

    def paginated_instances(self, page, per_page, where=None, sort=None):
        """

        :param page:
        :param per_page:
        :param where:
        :param sort:
        :return: a :class:`Pagination` object or similar
        """
        pass

    def instances(self, where=None, sort=None):
        """

        :param where:
        :param sort:
        :return:
        """
        pass

    def first(self, where=None, sort=None):
        """

        :param where:
        :param sort:
        :return:
        :raises exceptions.ItemNotFound:
        """
        try:
            return self.instances(where, sort)[0]
        except IndexError:
            raise ItemNotFound(self.resource, where=where)

    def create(self, properties, commit=True):
        """

        :param properties:
        :param commit:
        :return:
        """
        pass

    def read(self, id):
        """

        :param id:
        :return:
        """
        pass

    def update(self, item, changes, commit=True):
        """

        :param item:
        :param changes:
        :param commit:
        :return:
        """
        pass

    def delete(self, item):
        """

        :param item:
        :return:
        """
        pass

    def delete_by_id(self, id):
        """

        :param id:
        :return:
        """
        return self.delete(self.read(id))

    def commit(self):
        pass

    def begin(self):

        pass


class Pagination(object):
    """
    A pagination class for list-like instances.

    :param items:
    :param page:
    :param per_page:
    :param total:
    """

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total

    @property
    def pages(self):
        return max(1, int(ceil(self.total / self.per_page)))

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