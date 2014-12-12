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
from flask import request
from .fields import _field_from_object
from .utils import get_value
from .instances import Instances
from .reference import ResourceBound
from .schema import Schema, FieldSet


def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)

def attribute_to_route_uri(s):
    return s.replace('_', '-')

def to_camel_case(s):
    return s[0].lower() + s.title().replace('_', '')[1:] if s else s

class DeferredSchema(object):
    def __init__(self, class_, *args, **kwargs):
        self.schema_class = class_
        self.schema_args = args
        self.schema_kwargs = kwargs
        self._cached_schemas = {}

    def __call__(self, resource):
        if resource in self._cached_schemas:
            return self._cached_schemas[resource]

        schema = self.schema_class(*self.schema_args, **self.schema_kwargs)
        if isinstance(schema, ResourceBound):
            schema.bind(resource)

        self._cached_schemas[resource] = schema
        return schema

    @classmethod
    def resolve(cls, schema, resource):
        if isinstance(schema, cls):
            return schema(resource)
        if isinstance(schema, ResourceBound):
            schema.bind(resource)
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

        if isinstance(annotations, dict) and len(annotations):
            self.request_schema = FieldSet({name: field for name, field in annotations.items() if name != 'return'})
            self.response_schema = annotations.get('return', response_schema)
        else:
            self.request_schema = schema
            self.response_schema = response_schema

    @property
    def relation(self):
        if self.rel:
            return self.rel
        elif len(self.route.methods()) == 1:
            return self.route.attribute
        else:
            return "{}_{}".format(self.method, self.route.attribute)

    def schema_factory(self, resource):
        request_schema = DeferredSchema.resolve(self.request_schema, resource)
        response_schema = DeferredSchema.resolve(self.response_schema, resource)

        schema = OrderedDict([
            ("rel", self.relation),
            ("href", url_rule_to_uri_pattern(self.route.rule_factory(resource, relative=True))),
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

    @property
    def request_schema(self):
        return self.link.request_schema

    @request_schema.setter
    def request_schema(self, schema):
        self.link.request_schema = schema

    @property
    def response_schema(self):
        return self.link.response_schema

    @response_schema.setter
    def response_schema(self, schema):
        self.link.response_schema = schema

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return lambda *args, **kwargs: self.link.view_func.__call__(obj, *args, **kwargs)

    def links(self):
        yield self.link

    def methods(self):
        yield self.link.method

    @staticmethod
    def _rule_factory(route, resource, relative=False):
        rule = route.rule

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(route.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative:
            return rule[1:]
        return ''.join((resource.route_prefix, rule))

    def rule_factory(self, resource, relative=False):
        return self._rule_factory(self, resource, relative)

    @staticmethod
    def _view_factory(route, link, name, resource):
        request_schema = DeferredSchema.resolve(link.request_schema, resource)
        response_schema = DeferredSchema.resolve(link.response_schema, resource)
        view_func = link.view_func

        def view(*args, **kwargs):
            instance = resource()
            print(request_schema)
            print('NEW REQUEST',args, kwargs, request)
            print('NEW REQUEST', view_func, request_schema, response_schema)

            if isinstance(request_schema, (FieldSet, Instances)):
                kwargs.update(request_schema.parse_request(request))
            elif isinstance(request_schema, Schema):
                args += (request_schema.parse_request(request),)

            response = view_func(instance, *args, **kwargs)

            # TODO add 'described_by' header if response schema is a ToOne/ToMany/Instances field.

            if response_schema is None or not route.format_response:
                return response
            else:
                return response_schema.format_response(response)

        return view

    def view_factory(self, name, resource):
        return self._view_factory(self, self.link, name, resource)

    # TODO auto-generate these from all available methods
    @classmethod
    def GET(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='GET', view_class=cls, **kwargs))
        return wrapper

    @classmethod
    def POST(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='POST', view_class=cls, **kwargs))
        return wrapper

    @classmethod
    def PATCH(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='PATCH', view_class=cls, **kwargs))
        return wrapper

    @classmethod
    def PUT(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='PUT', view_class=cls, **kwargs))
        return wrapper

    @classmethod
    def DELETE(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='DELETE', view_class=cls, **kwargs))
        return wrapper


class MethodRoute(Route):

    def __init__(self, view_func, rule=None, rel=None, method='GET', attribute=None, view_class=Route):
        super().__init__(view_func, rule=rule, rel=rel, method=method, attribute=attribute)
        self.method_views = {method: self.link}
        self.view_class = view_class

        # for method in ('GET', 'POST', 'PATCH', 'PUT'):
        #     decorator = lambda **kwargs: \
        #         lambda func: wraps(func)(self._set_method_view_func(method, func, **kwargs))
        #     #decorator = MethodType(decorator, self, self.__class__)
        #
        #     setattr(self, method, decorator) #MethodType(decorator, self, self.__class__))

    def links(self):
        return self.method_views.values()

    def methods(self):
        return self.method_views.keys()

    def _set_method_view_func(self, method, view_func, rel=None, schema=None, response_schema=None):
        link = LinkView(view_func,
                        rel=rel,
                        route=self,
                        method=method,
                        schema=schema,
                        response_schema=response_schema)

        self.link = link
        self.method_views[method] = link
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

    def rule_factory(self, resource, relative=False):
        return self.view_class._rule_factory(self, resource, relative)

    def view_factory(self, name, resource):
        method_views = {}

        for name, link in self.method_views.items():
            method_views[name] = self.view_class._view_factory(self, link, name, resource)

        def view(*args, **kwargs):
            method = method_views.get(request.method)
            if method is None and request.method == 'HEAD':
                method = method_views['GET']
            return method(*args, **kwargs)
        return view

    def __repr__(self):
        return '{}("{}")'.format(self.__class__.__name__, self.rule)


def route(rule=None, method='GET', **view_kwargs):
    def wrapper(fn):
        return wraps(fn)(Route(fn, rule, method, **view_kwargs))
    return wrapper


class ItemRoute(Route):

    # TODO FIXME implement ItemMethodRoute

    @staticmethod
    def _rule_factory(route, resource, relative=False):
        rule = route.rule
        id_matcher = '<{}:id>'.format(resource.meta.id_converter)

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(route.attribute))
        elif callable(rule):
            rule = rule(resource)


        if relative:
            return ''.join((id_matcher, '/', rule[1:]))
        return ''.join(('/', resource.meta.name, '/', id_matcher, rule))

    @staticmethod
    def _view_factory(route, link, name, resource):
        original_view = Route._view_factory(route, link, name, resource)
        def view(*args, id, **kwargs):
            item = resource.manager.read(id)
            return original_view(item, *args, **kwargs)
        return view

    @classmethod
    def GET(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='GET', view_class=cls, **kwargs))
        return wrapper

    @classmethod
    def POST(cls, rule=None, **kwargs):
        def wrapper(func):
            return wraps(func)(MethodRoute(func, rule=rule, method='POST', view_class=cls, **kwargs))
        return wrapper



class Route_(object):
    def __init__(self, rule=None, attribute=None, format_response=True, view_decorator=None):
        self.rule = rule
        self.attribute = attribute
        self.view_decorator = view_decorator
        self.format_response = format_response

    def links(self):
        return ()

    def methods(self):
        return (link.method for link in self.links())

    @staticmethod
    def _rule_factory(route, resource, relative=False):
        rule = route.rule

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(route.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative:
            return rule[1:]
        return ''.join(('/', resource.meta.name, rule))

    def rule_factory(self, resource, relative=False):
        return self._rule_factory(self, resource, relative)

    @staticmethod
    def _view_factory(route, link, name, resource):
        request_schema = DeferredSchema.resolve(link.request_schema, resource)
        response_schema = DeferredSchema.resolve(link.response_schema, resource)
        view_func = link.view_func

        if route.view_decorator:
            view_func = route.view_decorator(view_func)

        def view(*args, **kwargs):
            instance = resource()
            print(request_schema)
            print('NEW REQUEST',args, kwargs, request)
            print('NEW REQUEST', view_func, request_schema, response_schema)

            if isinstance(request_schema, (FieldSet, Instances)):
                kwargs.update(request_schema.parse_request(request))
            elif isinstance(request_schema, Schema):
                args += (request_schema.parse_request(request),)

            response = view_func(instance, *args, **kwargs)

            # TODO add 'described_by' header if response schema is a ToOne/ToMany/Instances field.

            if response_schema is None or not route.format_response:
                return response
            else:
                return response_schema.format_response(response)

        return view

    def view_factory(self, name, resource):
        method_views = {}
        for link in self.links():
            method_views[link.method] = self._view_factory(self, link, name, resource)
        def view(*args, **kwargs):
            method = method_views.get(request.method)
            if method is None and request.method == 'HEAD':
                method = method_views['GET']
            return method(*args, **kwargs)
        return view


class NewMethodRoute(Route_):
    def __init__(self, method_views, rule=None, attribute=None, view_class=None, current_method=None):
        self.method_views = method_views
        self.current_view = self.method_views[current_method]
        # self.attribute = attribute
        # self.rule = rule

    def links(self):
        return self.method_views.values()


class ItemRoute_(Route_):

    @staticmethod
    def _rule_factory(route, resource, relative=False):
        rule = route.rule
        id_matcher = '<{}:id>'.format(resource.meta.id_converter)

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(route.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative:
            return ''.join((id_matcher, '/', rule[1:]))
        return ''.join(('/', resource.meta.name, '/', id_matcher, rule))

    @staticmethod
    def _view_factory(route, link, name, resource):
        original_view = Route_._view_factory(route, link, name, resource)
        def view(*args, id, **kwargs):
            item = resource.manager.read(id)
            return original_view(item, *args, **kwargs)
        return view


class ItemAttributeRoute(ItemRoute_):
    def __init__(self, cls_or_instance, io=None, **kwargs):
        super(ItemAttributeRoute, self).__init__(**kwargs)
        self.field = _field_from_object(ItemAttributeRoute, cls_or_instance)
        self.io = io

    def links(self):
        field = self.field
        io = self.io or field.io
        attribute = field.attribute or self.attribute

        def read_attribute(resource, item):
            return get_value(attribute, item, field.default)

        def update_attribute(resource, item, value):
            item = resource.manager.update(item, {attribute: value})
            return get_value(attribute, item, field.default)

        if "r" in io:
            yield LinkView(read_attribute,
                           method='GET',
                           rel=to_camel_case(attribute),
                           response_schema=field)
        if "w" in io:
            yield LinkView(update_attribute,
                           method='POST',
                           rel=to_camel_case('update_{}'.format(attribute)),
                           response_schema=field,
                           schema=field)


class RelationRoute(ItemRoute_):
    """
    A relationship route returns `{"$ref"}` objects for purposes of cache-ability, a core principle of REST.
    """
    def __init__(self, resource, backref=None, io="rw", attribute=None, **kwargs):
        super(RelationRoute, self).__init__(kwargs.pop('binding', None), attribute)
        self.resource = resource
        self.backref = backref
        self.io = io

    @staticmethod
    def read_relation(resource, item, where, sort):
        pass

    @staticmethod
    def add_to_relation(resource, item, child):
        pass

    @staticmethod
    def remove_to_relation(resource, item, child):
        pass


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



class RouteSet(object):
    pass