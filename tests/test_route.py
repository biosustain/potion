from unittest import TestCase
from flask import request
from flask.ext.potion.schema import FieldSet, Schema

__author__ = 'lyschoening'


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

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self
        return lambda *args, **kwargs: self.link.view_func.__call__(obj, *args, **kwargs)

    def rule_for(self, resource):
        if callable(self.rule):
            return self.rule(resource)
        return self.rule

    def links(self):
        yield self.link

    def methods(self):
        yield self.link.method

    def view_factory(self, name, resource):
        request_schema = self.link.request_schema # TODO resolve deferred schema
        response_schema = self.link.response_schema # TODO resolve deferred schema
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


class MethodRoute(Route):

    def __init__(self, view_func, rule=None, rel=None, method='GET', attribute=None):
        super().__init__(view_func, rule=rule, rel=rel, method=method, attribute=attribute)
        self.methods = {method: self.link}

    def links(self):
        return self.methods.values()

    def methods(self):
        return self.methods.keys()

    def _set_method_view_func(self, method, view_func, rel=None, schema=None, response_schema=None):
        self.link = link = LinkView(view_func,
                                    rel=rel,
                                    route=self,
                                    method=method,
                                    schema=schema,
                                    response_schema=response_schema)
        self.methods = {method: link}

    def GET(self, view_func, **kwargs):
        self._set_method_view_func('GET', view_func, **kwargs)

    def PUT(self, view_func, **kwargs):
        self._set_method_view_func('PUT', view_func, **kwargs)

    def POST(self, view_func, **kwargs):
        self._set_method_view_func('POST', view_func, **kwargs)

    def POST(self, view_func, **kwargs):
        self._set_method_view_func('POST', view_func, **kwargs)

    def DELETE(self, view_func, **kwargs):
        self._set_method_view_func('DELETE', view_func, **kwargs)

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


class RouteTestCase(TestCase):
    def __init__(self):
        pass

    def test_route(self):
        pass

class Resource(TestCase):



class ResourceTestCase(TestCase):

