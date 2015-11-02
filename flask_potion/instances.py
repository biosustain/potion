from __future__ import division
import collections
from math import ceil
from flask import json, request, current_app
from werkzeug.utils import cached_property
from .filters import convert_filters
from .exceptions import InvalidJSON
from .fields import ToMany
from .reference import ResourceBound
from .schema import Schema


class PaginationMixin(object):
    query_params = ()

    @cached_property
    def _pagination_types(self):
        raise NotImplemented()

    def format_response(self, data):
        if not isinstance(data, self._pagination_types):
            return self.format(data)

        links = [(request.path, data.page, data.per_page, 'self')]

        if data.has_prev:
            links.append((request.path, 1, data.per_page, 'first'))
            links.append((request.path, data.page - 1, data.per_page, 'prev'))
        if data.has_next:
            links.append((request.path, data.page + 1, data.per_page, 'next'))

        # HACK max(data.pages, 1): Flask-SQLAlchemy returns pages=0 when no results are returned
        links.append((request.path, max(data.pages, 1), data.per_page, 'last'))

        # FIXME links must contain filters & sort
        # TODO include query_params

        headers = {
            'Link': ','.join(('<{0}?page={1}&per_page={2}>; rel="{3}"'.format(*link) for link in links)),
            'X-Total-Count': data.total
        }

        return self.format(data.items), 200, headers


class RelationInstances(PaginationMixin, ToMany):

    @cached_property
    def _pagination_types(self):
        return self.container.target.manager.PAGINATION_TYPES


class Instances(PaginationMixin, Schema, ResourceBound):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """
    query_params = ('where', 'sort')

    def rebind(self, resource):
        return self.__class__().bind(resource)

    @cached_property
    def _pagination_types(self):
        return self.resource.manager.PAGINATION_TYPES

    def _field_filters_schema(self, filters):
        if len(filters) == 1:
            return next(iter(filters.values())).request
        else:
            return {"anyOf": [filter.request for filter in filters.values()]}

    @cached_property
    def _filters(self):
        return self.resource.manager.filters

    @cached_property
    def _sort_fields(self):
        return {
            name: field for name, field in self.resource.schema.fields.items()
            if name in self._filters and self.resource.manager._is_sortable_field(field)
        }

    @cached_property
    def _filter_schema(self):
        return {
            "type": "object",
            "properties": {
                name: self._field_filters_schema(filters)
                for name, filters in self._filters.items()
            },
            "additionalProperties": False
        }

    @cached_property
    def _sort_schema(self):
        return {
            "type": "object",
            "properties": {  # FIXME switch to tuples
                             name: {
                                 "type": "boolean",
                                 "description": "Sort by {} in descending order if 'true', ascending order if 'false'.".format(name)
                             }
                             for name, field in self._sort_fields.items()
            },
            "additionalProperties": False
        }

    def schema(self):
        request_schema = {
            "type": "object",
            "properties": {
                "where": self._filter_schema,
                "sort": self._sort_schema,
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": current_app.config['POTION_MAX_PER_PAGE'],
                    "default": current_app.config['POTION_DEFAULT_PER_PAGE'],
                }
            },
            "additionalProperties": True
        }

        response_schema = {
            "type": "array",
            "items": {"$ref": "#"}
        }

        return response_schema, request_schema

    def _convert_filters(self, where):
        for name, value in where.items():
            yield convert_filters(value, self._filters[name])

    def _convert_sort(self, sort):
        for name, reverse in sort.items():
            field = self._sort_fields[name]
            yield field, field.attribute or name, reverse

    def parse_request(self, request):

        # TODO convert instances to FieldSet
        # TODO (implement in FieldSet too:) load values from request.args
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', current_app.config['POTION_DEFAULT_PER_PAGE'], type=int)
            where = json.loads(request.args.get('where', '{}'))  # FIXME
            sort = json.loads(request.args.get('sort', '{}'), object_pairs_hook=collections.OrderedDict)
        except ValueError:
            raise InvalidJSON()

        result = self.convert({
            "page": page,
            "per_page": per_page,
            "where": where,
            "sort": sort
        })

        result['where'] = tuple(self._convert_filters(result['where']))
        result['sort'] = tuple(self._convert_sort(result['sort']))
        return result

    def format(self, items):
        return [self.resource.schema.format(item) for item in items]


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