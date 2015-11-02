import collections
from flask import json, request, current_app
from werkzeug.utils import cached_property
from .filters import convert_filters
from .exceptions import InvalidJSON
from .backends import Pagination
from .fields import ToMany
from .reference import ResourceBound
from .schema import Schema

PAGINATION_TYPES = (Pagination,)

try:
    from flask_sqlalchemy import Pagination as SAPagination
    PAGINATION_TYPES += (SAPagination,)
except ImportError:
    pass

try:
    from flask_mongoengine import Pagination as MEPagination
    PAGINATION_TYPES += (MEPagination,)
except ImportError:
    pass


class PaginationMixin(object):
    query_params = ()

    def format_response(self, data):
        if not isinstance(data, PAGINATION_TYPES):
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
    pass


class Instances(PaginationMixin, Schema, ResourceBound):
    """
    This is what implements all of the pagination, filter, and sorting logic.

    Works like a field, but reads 'where' and 'sort' query string parameters as well as link headers.
    """
    query_params = ('where', 'sort')

    def __init__(self, default_sort=None, filters=None):
        self.sort_fields = []

    def _on_bind(self, resource):
        fs = resource.schema
        sort = {name: fs.fields[name] for name in resource.manager.filters}
        self.sort_fields = {name: field for name, field in sort.items()}

    def rebind(self, resource):
        return self.__class__().bind(resource)

    def _field_filters_schema(self, filters):
        if len(filters) == 1:
            return next(iter(filters.values())).request
        else:
            return {"anyOf": [filter.request for filter in filters.values()]}

    @cached_property
    def _filter_schema(self):
        return {
            "type": "object",
            "properties": {
                name: self._field_filters_schema(filters)
                for name, filters in self.resource.manager.filters.items()
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
                             for name, field in self.sort_fields.items()
                             if self.resource.manager.is_sortable_field(field)
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
            filters = self.resource.manager.filters[name]
            yield convert_filters(value, filters)

    def _convert_sort(self, sort):
        for name, reverse in sort.items():
            field = self.sort_fields[name]
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
