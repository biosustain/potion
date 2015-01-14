from collections import OrderedDict
import operator
from flask import current_app, make_response, json, jsonify
from jsonschema import ValidationError
from six import wraps
from werkzeug.wrappers import BaseResponse
from .exceptions import PotionException
from .utils import unpack
from .resource import Resource, ModelResource
from . import signals, fields

__version_info__ = (1, 0, 0)
__version__ = '.'.join(map(str, __version_info__))
__all__ = (
    'Api',
    'Resource',
    'ModelResource',
    'signals',
    'fields',
)

class Api(object):
    def __init__(self, app=None, decorators=None, prefix=None, default_per_page=20, max_per_page=100):
        self.app = None
        self.prefix = prefix or ''
        self.decorators = decorators or []
        self.max_per_page = max_per_page
        self.default_per_page = default_per_page
        self.endpoints = set()
        self.resources = {}
        self.views = []

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.potion = self

        self._complete_view('/schema',
                            view_func=self.output(self._schema_view),
                            endpoint='schema',
                            methods=['GET'])

        for rule, view, endpoint, methods in self.views:
            self._complete_view(rule, view_func=view, endpoint=endpoint, methods=methods)

        @app.errorhandler(PotionException)
        def handle_invalid_usage(error):
            return error.make_response()

    def output(self, view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            resp = view(*args, **kwargs)
            if isinstance(resp, BaseResponse):
                return resp

            data, code, headers = unpack(resp)

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

        for name, resource in sorted(self.resources.items(), key=operator.itemgetter(0)):
            resource_schema_rule = resource.routes['schema'].rule_factory(resource)
            properties[name] = {"$ref": self._complete_rule('{}#'.format(resource_schema_rule))}

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
        resource.api = self
        resource.route_prefix = ''.join((self.prefix, '/', resource.meta.name))

        if resource in self.resources.values():
            return

        for route in resource.routes.values():
            self.add_route(route, resource)

        self.resources[resource.meta.name] = resource
