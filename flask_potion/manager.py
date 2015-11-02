import datetime
import six
from werkzeug.utils import cached_property
from .fields import String, Boolean, Number, Integer, Date, DateTime, Array, Object
from .instances import Pagination
from .exceptions import ItemNotFound
from .filters import FILTER_NAMES, FILTERS_BY_TYPE, filters_for_fields

class Manager(object):
    """

    :param flask_potion.resource.Resource resource: resource class
    :param model: model read from ``Meta.model`` or ``None``
    """
    FILTER_NAMES = FILTER_NAMES
    FILTERS_BY_TYPE = FILTERS_BY_TYPE
    PAGINATION_TYPES = (Pagination,)

    def __init__(self, resource, model):
        self.resource = resource
        self.filters = {}

        self._init_model(resource, model, resource.meta)
        self._init_filters(resource, resource.meta)
        self._init_key_converters(resource, resource.meta)

    def _create_filter(self, filter_class, name, field, attribute):
        return filter_class(name,
                            field=field,
                            attribute=field.attribute or attribute)

    def _init_model(self, resource, model, meta):
        self.model = model

    def _init_filters(self, resource, meta):
        fields = resource.schema.fields
        field_filters = filters_for_fields(resource.schema.fields,
                                           meta.filters,
                                           filter_names=self.FILTER_NAMES,
                                           filters_by_type=self.FILTERS_BY_TYPE)
        self.filters = {
            field_name: {
                name: self._create_filter(filter, name, fields[field_name], field_name)
                for name, filter in field_filters.items()
                }
            for field_name, field_filters in field_filters.items()
        }

    def _is_sortable_field(self, field):
        return isinstance(field, (String, Boolean, Number, Integer, Date, DateTime))

    def _init_key_converters(self, resource, meta):
        if 'natural_key' in meta:
            from flask_potion.natural_keys import PropertyKey, PropertiesKey
            if isinstance(meta.natural_key, str):
                meta['key_converters'] += (PropertyKey(meta.natural_key),)
            elif isinstance(meta.natural_key, (list, tuple)):
                meta['key_converters'] += (PropertiesKey(*meta.natural_key),)

        if 'key_converters' in meta:
            meta.key_converters = [k.bind(resource) for k in meta['key_converters']]
            meta.key_converters_by_type = {}
            for nk in meta.key_converters:
                if nk.matcher_type() in meta.key_converters_by_type:
                    raise RuntimeError(
                        'Multiple keys of type {} defined for {}'.format(nk.matcher_type(), meta.name))
                meta.key_converters_by_type[nk.matcher_type()] = nk

    @staticmethod
    def _get_field_from_python_type(python_type):
        try:
            return {
                str: String,
                six.text_type: String,
                int: Integer,
                float: Number,
                bool: Boolean,
                list: Array,
                dict: Object,
                datetime.date: Date,
                datetime.datetime: DateTime
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def get_field_comparators(self, field):
        pass

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