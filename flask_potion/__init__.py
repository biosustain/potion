from collections import OrderedDict
import operator
from flask import current_app, make_response
from six import wraps
from sqlalchemy.dialects.postgresql import json
from werkzeug.wrappers import BaseResponse
from .util import unpack


class Api(object):
    def __init__(self, app=None, decorators=None, prefix=None, default_per_page=20, max_per_page=100):
        self.app = None
        self.prefix = prefix
        self.decorators = decorators or []
        self.max_per_page = max_per_page
        self.default_per_page = default_per_page

        self.decorators = []
        self.endpoints = set()
        self.resources = {}
        self.views = []

        if app is not None:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        self.app._complete_view('/schema',
                                view_func=self._schema_view,
                                endpoint='schema',
                                methods=['GET'])
        # TODO add URL rule for base schema.

    def output(self, view):
        # FIXME from Flask-RESTful
        """Wraps a resource (as a flask view function), for cases where the
        resource does not directly return a response object

        :param view: The resource as a flask view function
        """
        @wraps(view)
        def wrapper(*args, **kwargs):
            resp = view(*args, **kwargs)
            if isinstance(resp, BaseResponse):
                return resp

            data, code, headers = unpack(resp)

            # TODO since these settings are the same every time, move them outside the function
            settings = {}
            if current_app.debug:
                settings.setdefault('indent', 4)
                settings.setdefault('sort_keys', True)

            data = json.dumps(data, **settings)
            resp = make_response(data, code)
            resp.headers['Content-Type'] = 'application/json'
            resp.headers.extend(headers or {})
            return resp

        return wrapper

    def _complete_rule(self, rule):
        return ''.join((self.prefix, rule))

    def _complete_view(self, rule, **kwargs):
        self.app.add_url_rule(self._complete_rule(rule), **kwargs)

    def _schema_view(self):
        definitions = OrderedDict([])
        properties = OrderedDict([])
        schema = OrderedDict([
            ("$schema", "http://json-schema.org/draft-04/hyper-schema#"),
            ("definitions", definitions),
            ("properties", properties)
        ])

        # TODO add title, description

        for name, resource in sorted(self.resources, key=operator.itemgetter(0)):
            properties[name] = {"$ref": self._complete_rule('/{}'.format(name))}

        return schema, 200, {'Content-Type': 'application/schema+json'}

    def add_route(self, route, resource, endpoint=None):
        endpoint = endpoint or '.'.join((resource.meta.name, route.attribute))
        methods = route.methods()
        rule = route.rule_factory(resource)
        view = self.output(route.view_factory(endpoint, resource))

        for decorator in self.decorators:
            view = decorator(view)

        if self.app:
            self._complete_view(rule, view_func=view, endpoint=endpoint, methods=methods)
        else:
            self.views.append((rule, view, endpoint, methods))

    def add_resource(self, resource):
        if resource in self.resources.values():
            return

        for route in resource.routes:
            self.add_route(route, resource)

        self.resources[resource.meta.name] = resource
