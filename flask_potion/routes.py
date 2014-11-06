"""



sub-resources:

strict sub-resources are no problem.


one-to-one:

use filters.




one-to-many:

/project/1/tasks
/task.project


/task/1/project?

/project/tasks






many-to-many:


/group/1/members
/user/1.groups


/user/1/memberships
/membership/1,1



Relationships should be references rather than full items so that the cache only has to be invalidated if an item is
added or removed, but not if any other values change.


/user/{userID}/groups/{groupID}
should do a HTTP redirect to:
/memberships/{uuid}





"""
from functools import wraps
import re
from flask import request
from .schema import Schema, FieldSet


def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)

def attribute_to_route_uri(s):
    return s.replace('_', '-')


class PotionView(Schema):

    def __init__(self, view_func, request_schema=None, response_schema=None):
        self.view_func = view_func
        self.request_schema = request_schema
        self.response_schema = response_schema

    @property
    def schema(self):
        raise NotImplementedError()

    def dispatch_request(self, instance, *args, **kwargs):
        """

        If :attr:`schema` is a :class:`FieldSet`, the parsed arguments are spread over the view function `kwargs`. If
        it is any other type of schema, the function is called with a single argument containing the entire object.

        :param instance:
        :param args:
        :param kwargs:
        :return:
        """
        # TODO move most of this into Route()
        if isinstance(self.request_schema, FieldSet):
            kwargs.update(self.request_schema.parse_request(request))

        response = self.view_func(instance, *args, **kwargs)

        # TODO add 'described_by' header.

        if self.response_schema is None:
            return response
        else:
            self.response_schema.format_response(response)


class Route(object):
    def __init__(self, view_func,
                 rule=None,
                 rel=None,
                 binding=None,
                 attribute=None,
                 schema=None,
                 response_schema=None,
                 **view_kwargs):
        self.binding = binding
        self.attribute = attribute
        self.relationship = rel
        self.rule = rule

        annotations = getattr(view_func, '__annotations__', None)

        if isinstance(annotations, dict):
            self.request_schema = FieldSet({name: field for name, field in annotations.items() if name != 'return'})
            self.response_schema = annotations.get('return', response_schema)
        else:
            self.request_schema = schema
            self.response_schema = response_schema

        self._view_func = view_func

    # @classmethod
    # def GET(cls, *args, **kwargs):
    #     return MultiRouteRoute(*args, initial_method='GET', **kwargs)

    def view_factory(self, name, binding):
        def view(*args, **kwargs):
            instance = binding()

            if isinstance(self.request_schema, FieldSet):
                kwargs.update(self.request_schema.parse_request(request))
            elif isinstance(self.request_schema, Schema):
                args += [self.request_schema.parse_request(request)]

            response = self._view_func(instance, *args, **kwargs)

            # TODO add 'described_by' header if response schema is a ToOne/ToMany/Set field.

            if self.response_schema is None:
                return response
            else:
                self.response_schema.format_response(response)

        return view



def route(rule=None, method='GET', **view_kwargs):
    def wrapper(fn):
        return wraps(fn)(Route(fn, rule, method, **view_kwargs))

    return wrapper





class MultiRoute(Route):
    def __init__(self,
                 method_func,
                 initial_method='GET',
                 route=None,
                 attribute=None,
                 binding=None,
                 view_class=SchemaView,
                 view_methods=None,
                 **view_kwargs):

        super(MultiRoute, self).__init__(binding, attribute)
        self.route = route

        self._view_class = view_class
        self._view_methods = view_methods = view_methods.copy() if view_methods else {}
        self._current_view = view = view_class(method_func, **view_kwargs)
        view_methods[initial_method] = view

    def __getattr__(self, name):
        return getattr(self._current_view, name)

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self
        return lambda *args, **kwargs: self._current_view._fn.__call__(obj, *args, **kwargs)

    def _add_method(self, method, fn, rel=None):
        return type(self)(method_func=fn,
                          method=method,
                          attribute=self.attribute,
                          route=self.route,
                          view_class=self._view_class,
                          view_methods=self._view_methods)

    def GET(self, fn, **kwargs):
        return self._add_method('GET', fn, **kwargs)

    def PUT(self, fn, **kwargs):
        return self._add_method('PUT', fn, **kwargs)

    def POST(self, fn, **kwargs):
        return self._add_method('POST', fn, **kwargs)

    def PATCH(self, fn, **kwargs):
        return self._add_method('PATCH', fn, **kwargs)

    def DELETE(self, fn, **kwargs):
        return self._add_method('DELETE', fn, **kwargs)

    # @property
    # def methods(self):
    #     return list(self._view_methods.keys())

    def view_factory(self, name, binding):
        def view(*args, **kwargs):
            view = self._view_methods[request.method.upper()]
            resource_instance = binding()
            return view.dispatch_request(resource_instance, *args, **kwargs)
        return view


class ItemRoute(Route):
    pass


class ItemAttributeRoute(ItemRoute):

    def __init__(self, attribute_field, **kwargs):
        super(ItemAttributeRoute, self).__init__(**kwargs)
        self.attribute_field = attribute_field


class ItemMapAttributeRoute(ItemRoute):
    """
    Adds a route that includes the keys to a dictionary attribute and allows these to be read, set, and deleted
    either individually or in bulk.

    class Schema:
        scores = fields.Object(field.Integer)

    GET /item/:id/scores/:key/
    PUT /item/:id/scores/:key/
    DELETE /item/:id/scores/:key/
    """
    pass


class ItemSetRoute(ItemRoute):

    def __init__(self, target_resource=None, **kwargs):
        pass

    def get(self):
        raise NotImplementedError()

    def put(self, item, child):
        raise NotImplementedError()

    def delete(self, item, child):
        raise NotImplementedError()


class RelationshipRoute(ItemSetRoute):
    """

    A relationship route returns `{"$ref"}` objects for purposes of cache-ability, a core principle of REST.
    """

    def __init__(self, resource, backref=None, io="rw", attribute=None, **kwargs):
        super(RelationshipRoute, self).__init__(kwargs.pop('binding', None), attribute)
        self.resource = resource
        self.backref = backref
        self.io = io


class MethodDecoratorMixin(object):

    def GET(self):
        pass

    def POST(self):
        pass

    def PATCH(self):
        pass

    def DELETE(self):
        pass


class Index(MethodDecoratorMixin):

    def __init__(self):
        pass


index = Index

route = Route