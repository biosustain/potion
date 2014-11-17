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
from collections import OrderedDict
from functools import wraps
import re
from types import MethodType
from flask import request
from .schema import Schema, FieldSet


def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)

def attribute_to_route_uri(s):
    return s.replace('_', '-')

class DeferredSchema(object):
    def __init__(self, class_, *args, **kwargs):
        self.schema_class = class_
        self.schema_args = args
        self.schema_kwargs = kwargs

    def __call__(self, resource):
        schema = self.schema_class(*self.schema_args, **self.schema_kwargs)
        schema.binding = resource
        return schema

    @classmethod
    def resolve(cls, schema, resource):
        if isinstance(schema, cls):
            return schema(resource)
        return schema


class LinkView(object):

    def __init__(self,
                 view_func,
                 rel=None,
                 route=None,
                 method=None,
                 schema=None,
                 response_schema=None,
                 format_response=True):
        self.rel = rel
        self.route = route
        self.method = method
        self.view_func = view_func
        self.format_response = format_response

        annotations = getattr(view_func, '__annotations__', None)

        if isinstance(annotations, dict):
            self.request_schema = FieldSet({name: field for name, field in annotations.items() if name != 'return'})
            self.response_schema = annotations.get('return', response_schema)
        else:
            self.request_schema = schema
            self.response_schema = response_schema

    def schema_factory(self, resource):
        request_schema = DeferredSchema.resolve(self.request_schema, resource)
        response_schema = DeferredSchema.resolve(self.response_schema, resource)
        schema = OrderedDict([
            ("rel", self.rel or "{}_{}".format(self.method, self.route.attribute)),
            ("href", self.route.rule),
            ("method", self.method)
        ])

        if request_schema:
            schema["schema"] = request_schema.request
        if response_schema:
            schema["targetSchema"] = response_schema.response
        return schema


class Route(object):
    def __init__(self,
                 view_func,
                 method='GET',
                 rule=None,
                 rel=None,
                 attribute=None,
                 schema=None,
                 response_schema=None,
                 format_response=True,
                 view_decorator=None):
        self.rule = rule
        self.attribute = attribute
        self.format_response = format_response
        self.view_decorator = view_decorator

        self.link = LinkView(view_func,
                             rel=rel,
                             route=self,
                             schema=schema,
                             method=method,
                             response_schema=response_schema,
                             format_response=format_response)

    def __getattr__(self, name):
        return getattr(self.link, name)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return lambda *args, **kwargs: self.link.view_func.__call__(obj, *args, **kwargs)

    def links(self):
        yield self.link

    def methods(self):
        yield self.link.method

    def rule_factory(self, resource):
        rule = self.rule

        if rule is None:
            rule = '/{}'.format(self.attribute)
        elif callable(rule):
            rule = rule(resource)

        return ''.join((self.resource.meta.name, rule))

    def view_factory(self, name, resource):
        request_schema = DeferredSchema.resolve(self.link.request_schema, resource)
        response_schema = DeferredSchema.resolve(self.link.response_schema, resource)
        view_func = self.link.view_func

        def view(*args, **kwargs):
            instance = resource()

            if isinstance(request_schema, FieldSet):
                kwargs.update(request_schema.parse_request(request))
            elif isinstance(request_schema, Schema):
                args += [request_schema.parse_request(request)]

            response = view_func(instance, *args, **kwargs)

            # TODO add 'described_by' header if response schema is a ToOne/ToMany/Set field.

            if response_schema is None or not self.format_response:
                return response
            else:
                response_schema.format_response(response)

        return view

    # TODO auto-generate these from all available methods
    @classmethod
    def GET(cls, rule, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='GET', **kwargs))
        return wrapper

    @classmethod
    def POST(cls, rule, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='POST', **kwargs))
        return wrapper

    @classmethod
    def PATCH(cls, rule, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='PATCH', **kwargs))
        return wrapper

    @classmethod
    def PUT(cls, rule, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='PUT', **kwargs))
        return wrapper

    @classmethod
    def DELETE(cls, rule, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='DELETE', **kwargs))
        return wrapper


class MethodRoute(Route):

    def __init__(self, view_func, rule=None, rel=None, method='GET', attribute=None):
        super().__init__(view_func, rule=rule, rel=rel, method=method, attribute=attribute)
        self.method_views = {method: self.link}

        for method in ('GET', 'POST', 'PATCH', 'PUT'):
            decorator = lambda **kwargs: \
                lambda func: wraps(func)(self._set_method_view_func(method, func, **kwargs))
            #decorator = MethodType(decorator, self, self.__class__)

            setattr(self, method, decorator) #MethodType(decorator, self, self.__class__))

    def links(self):
        return self.method_views.values()

    def methods(self):
        return self.method_views.keys()

    def _set_method_view_func(self, method, view_func, rel=None, schema=None, response_schema=None):
        self.link = link = LinkView(view_func,
                                    rel=rel,
                                    route=self,
                                    method=method,
                                    schema=schema,
                                    response_schema=response_schema)
        self.method_views = {method: link}
        return self

    # TODO auto-generate these
    def GET(self, **kwargs):
        def wrapper(func):
            return wraps(func)(self._set_method_view_func('GET', func, **kwargs))
        return wrapper

    def PUT(self, **kwargs):
        def wrapper(func):
            return wraps(func)(self._set_method_view_func('PUT', func, **kwargs))
        return wrapper

    def POST(self, **kwargs):
        def wrapper(func):
            return wraps(func)(self._set_method_view_func('POST', func, **kwargs))
        return wrapper

    def DELETE(self, **kwargs):
        def wrapper(func):
            return wraps(func)(self._set_method_view_func('DELETE', func, **kwargs))
        return wrapper

    def PATCH(self, **kwargs):
        def wrapper(func):
            return wraps(func)(self._set_method_view_func('PATCH', func, **kwargs))
        return wrapper

    # TODO
    # def view_factory(self, name, binding):
    #     def view(*args, **kwargs):
    #         view = self._view_methods[request.method.upper()]
    #         resource_instance = binding()
    #         return view.dispatch_request(resource_instance, *args, **kwargs)
    #     return view
    #
    # def view_factory(self, name, resource):
    #     request_schema = self.link.request_schema # TODO resolve deferred schema
    #     response_schema = self.link.response_schema # TODO resolve deferred schema
    #     view_func = self.link.view_func
    #
    #     def view(*args, **kwargs):
    #         instance = resource()
    #
    #         if isinstance(request_schema, FieldSet):
    #             kwargs.update(request_schema.parse_request(request))
    #         elif isinstance(request_schema, Schema):
    #             args += [request_schema.parse_request(request)]
    #
    #         response = view_func(instance, *args, **kwargs)
    #
    #         # TODO add 'described_by' header if response schema is a ToOne/ToMany/Set field.
    #
    #         if response_schema is None:
    #             return response
    #         else:
    #             response_schema.format_response(response)
    #
    #     return view
    def __repr__(self):
        return '{}("{}")'.format(self.__class__.__name__, self.rule)

def route(rule=None, method='GET', **view_kwargs):
    def wrapper(fn):
        return wraps(fn)(Route(fn, rule, method, **view_kwargs))

    return wrapper


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

    # @Route.GET(lambda r: '/<id:{}>/attribute/<key>'.format(r.meta.id_converter))
    # def attribute(self, item, key):
    #     pass


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