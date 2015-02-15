from collections import OrderedDict
import re
from types import MethodType
import sys

from flask import request
from werkzeug.utils import cached_property

from flask_potion.fields import _field_from_object
from flask_potion.fields import ToOne, Integer, Object
from flask_potion.utils import get_value
from flask_potion.instances import Instances, RelationInstances
from flask_potion.reference import ResourceBound, ResourceReference
from flask_potion.schema import Schema, FieldSet


HTTP_METHODS = ('GET', 'PUT', 'POST', 'PATCH', 'DELETE')

def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)

def attribute_to_route_uri(s):
    return s.replace('_', '-')

def to_camel_case(s):
    return s[0].lower() + s.title().replace('_', '')[1:] if s else s

def _bind_schema(schema, resource):
    if isinstance(schema, ResourceBound):
        return schema.bind(resource)
    return schema


class Link(object):
    """
    This class is an container used by :class:`Route` to store method view functions and their schemas.

    Links are not bound to a specific resource and their schema, generated using :meth:`schema_factory` can vary depending on the resource.

    If ``view_func`` has an ``__annotations__`` attribute (a Python 3.x function annotation), the annotations
    will be used to generate the ``request_schema`` and ``response_schema``. The *return* annotation in this case
    is expected to be a :class:`schema.Schema` used for responses, and all other annotations are expected to be of type :class:`fields.Raw`
    and are combined into a :class:`schema.Fieldset`.

    :param callable view_func: view function
    :param str rel: relation
    :param str title: title of schema
    :param str description: description of schema
    :param routes.Route route: route this link belongs to
    :param str method: a HTTP request method name (upper case)
    :param schema.Schema schema: request schema
    :param schema.Schema response_schema: response schema
    :param bool format_response: whether the response should be converted using the response schema

    .. property:: relation

        A relation for the string, equal to ``rel`` if one was given.

    .. attribute:: request_schema

        request schema (not resource-bound)

    .. attribute:: response_schema

        response schema (not resource-bound)
    """
    def __init__(self,
                 view_func,
                 rel=None,
                 title=None,
                 description=None,
                 route=None,
                 method=None,
                 schema=None,
                 response_schema=None,
                 format_response=True):
        self.rel = rel
        self.title = title
        self.description = description
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
        """
        Returns a link schema for a specific resource.
        """
        request_schema = _bind_schema(self.request_schema, resource)
        response_schema = _bind_schema(self.response_schema, resource)

        # NOTE "href" for rel="instances" MUST NOT be relative; others MAY BE relative
        schema = OrderedDict([
            ("rel", self.relation),
            ("href", url_rule_to_uri_pattern(self.route.rule_factory(resource, relative=False))),
            ("method", self.method)
        ])

        if self.title:
            schema["title"] = self.title
        if self.description:
            schema["description"] = self.description

        if request_schema:
            schema["schema"] = request_schema.request
        if response_schema:
            schema["targetSchema"] = response_schema.response
        return schema


def _method_decorator(method):
    def wrapper(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return self._set_method_link(method, args[0], **kwargs)
        else:
            return lambda f: self._set_method_link(method, f, *args, **kwargs)

    wrapper.__name__ = method
    return wrapper


class Route(object):
    """

    .. decoratormethod:: METHOD(rule=None, attribute=None, rel=None, title=None, description=None, schema=None, response_schema=None, format_response=True)

        A decorator for registering the *METHOD* method handler of a route. Can be used with or without arguments and on both class and route instances. The ``rule`` and ``attribute``
        arguments are only available on the class.

        When used with an instance will add or replace the view function for the *METHOD* method of this :class:`Route` with the decorated function; otherwise instantiates a new :class:`Route` with the view function.

        This decorator is defined for the *GET*, *PUT*, *POST*, *PATCH* and *DELETE* methods.

        :param str rule: (class-only) route URI relative to the resource, defaults to ``/{attribute}``, replacing any ``'_'`` (underscore) in ``attribute`` with ``'-'`` (dash).
        :param str attribute: (class-only) attribute on the parent resource, used to identify the route internally; defaults to the attribute name of the decorated view function within the parent resource.
        :param str rel: relation of the method link to the resource
        :param str title: title of link schema
        :param str description: description of link schema
        :param schema.Schema schema: request schema
        :param schema.Schema schema: response schema
        :param bool format_response: whether the response should be converted using the response schema

    .. attribute:: request_schema

        Used to get and set the response schema for the most recently decorated request method view function

    .. attribute:: response_schema

        Used to get and set the response schema for the most recently decorated request method view function

    .. attribute:: method_links

        A dictionary mapping of method names (in upper case) to :class:`routes.Link` objects containing the method view functions.

    """
    def __init__(self, rule=None, attribute=None, format_response=True):
        self.rule = rule
        self.attribute = attribute
        self.format_response = format_response
        self.current_link = None
        self._method_links = {}

        for method in HTTP_METHODS:
            setattr(self, method, MethodType(_method_decorator(method), self))

    @classmethod
    def for_method(cls, method, func, rule=None, **kwargs):
        instance = cls(rule=rule,
                       attribute=kwargs.pop('attribute', None),
                       format_response=kwargs.pop('format_response', True))
        instance._set_method_link(method, func, **kwargs)
        return instance

    def _set_method_link(self, method, view_func, rel=None, title=None, description=None, schema=None, response_schema=None):
        link = Link(view_func,
                        rel=rel,
                        title=title,
                        description=description,
                        route=self,
                        method=method,
                        schema=schema,
                        response_schema=response_schema)
        self.current_link = link
        self._method_links[method] = link
        return self

    def __getattr__(self, name):
        return getattr(self.current_link, name)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return lambda *args, **kwargs: self.current_link.view_func.__call__(obj, *args, **kwargs)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.rule))

    @property
    def request_schema(self):
        return self.current_link.request_schema

    @request_schema.setter
    def request_schema(self, schema):
        self.current_link.request_schema = schema

    @property
    def response_schema(self):
        return self.current_link.response_schema

    @response_schema.setter
    def response_schema(self, schema):
        self.current_link.response_schema = schema

    def links(self):
        """
        Helper function that returns a list of all links within this route.
        """
        return self._method_links.values()

    def methods(self):
        """
        Helper function that returns a list of all methods supported by this route.
        """
        return [link.method for link in self.links()]

    def _rule_factory(self, resource, relative=False):
        rule = self.rule

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(self.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative or resource.route_prefix is None:
            return rule[1:]

        return ''.join((resource.route_prefix, rule))

    def _view_factory(self, link, name, resource):
        request_schema = _bind_schema(link.request_schema, resource)
        response_schema = _bind_schema(link.response_schema, resource)
        view_func = link.view_func

        def view(*args, **kwargs):
            instance = resource()
            if isinstance(request_schema, (FieldSet, Instances)):
                kwargs.update(request_schema.parse_request(request))
            elif isinstance(request_schema, Schema):
                args += (request_schema.parse_request(request),)

            response = view_func(instance, *args, **kwargs)
            # TODO add 'described_by' header if response schema is a ToOne/ToMany/Instances field.
            if response_schema is None or not self.format_response:
                return response
            else:
                return response_schema.format_response(response)

        return view

    def rule_factory(self, resource, relative=False):
        """
        Returns a URL rule string for this route and resource.

        :param flask_potion.Resource resource:
        :param bool relative: whether the rule should be relative to ``resource.route_prefix``
        """
        return self._rule_factory(resource, relative)

    def view_factory(self, name, resource):
        """
        Returns a view function for all links within this route and resource.

        :param name: Flask view name
        :param flask_potion.Resource resource:
        """
        method_views = {}

        for name, link in self._method_links.items():
            method_views[name] = self._view_factory(link, name, resource)

        def view(*args, **kwargs):
            method = method_views.get(request.method)
            if method is None and request.method == 'HEAD':
                method = method_views['GET']
            return method(*args, **kwargs)
        return view


def _route_decorator(method):
    @classmethod
    def decorator(cls, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return cls.for_method(method, args[0])
        else:
            return lambda f: cls.for_method(method, f, *args, **kwargs)
    if sys.version_info.major > 2:
        decorator.__name__ = method
    return decorator

for method in HTTP_METHODS:
    setattr(Route, method, _route_decorator(method))


class ItemRoute(Route):
    """
    This route can be used with :class:`flask_potion.ModelResource`. It is a simple extension over :class:`Route` with
    the following adjustments:

    - :meth:`rule_factory` is changed to prefix ``<{id_converter}:id>`` with any rule.
    - It changes the implementation of :meth:`view_factory` so that it passes the resolved resource item matching *id*
      as the first positional argument to the view function.
    """
    def _rule_factory(self, resource, relative=False):
        rule = self.rule
        id_matcher = '<{}:id>'.format(resource.meta.id_converter)

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(self.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative or resource.route_prefix is None:
            return rule[1:]

        return ''.join((resource.route_prefix, '/', id_matcher, rule))

    def _view_factory(self, link, name, resource):
        original_view = super(ItemRoute, self)._view_factory(link, name, resource)
        def view(*args, **kwargs):
            id = kwargs.pop('id')  # Py2.7 -- could use (*args, id, **kwargs) otherwise
            item = resource.manager.read(id)
            return original_view(item, *args, **kwargs)
        return view


class RouteSet(object):
    """
    An abstract class for combining related routes into one, which can also be used as a route factory.
    """

    def routes(self):
        """
        :returns: an iterator over :class:`Route` objects
        """
        return ()


class ItemAttributeRoute(RouteSet):
    """

    :param fields.Raw cls_or_instance: a field class or instance
    :param str attribute: defaults to the field's ``attribute`` attribute
    :param str io: ``r``, ``w``, or ``rw`` - defaults to the field's ``io`` attribute
    """
    def __init__(self, cls_or_instance, io=None, attribute=None):
        self.field = _field_from_object(ItemAttributeRoute, cls_or_instance)
        self.attribute = attribute
        self.io = io

    def routes(self):
        io = self.io or self.field.io
        field = self.field
        route = ItemRoute(attribute=self.attribute)
        attribute = field.attribute or route.attribute

        if "r" in io:
            @route.GET(response_schema=field,
                       rel=to_camel_case('read_{}'.format(route.attribute)))
            def read_attribute(resource, item):
                return get_value(attribute, item, field.default)

        if "w" in io:
            @route.POST(schema=field,
                        response_schema=field,
                        rel=to_camel_case('update_{}'.format(route.attribute)))
            def update_attribute(resource, item, value):
                attribute = field.attribute or route.attribute
                item = resource.manager.update(item, {attribute: value})
                return get_value(attribute, item, field.default)

        yield route


class Relation(RouteSet, ResourceBound):
    """
    Used to define a relation to another :class:`ModelResource`.
    """
    def __init__(self, resource, backref=None, io="rw", attribute=None, **kwargs):
        self.reference = ResourceReference(resource)
        self.attribute = attribute
        self.backref = backref
        self.io = io

    @cached_property
    def target(self):
        return self.reference.resolve(self.resource)

    # FIXME can only be loaded after target is added to API
    def routes(self):
        io = self.io
        rule = '/{}'.format(attribute_to_route_uri(self.attribute))

        relation_route = ItemRoute(rule='{}/<{}:target_id>'.format(rule, self.target.meta.id_converter))
        relations_route = ItemRoute(rule=rule)

        if "r" in io:
            @relations_route.GET
            def relation_instances(resource, item, page, per_page):
                return resource.manager.relation_instances(item,
                                                           self.attribute,
                                                           self.target,
                                                           page,
                                                           per_page)

            relations_route.request_schema = FieldSet({
                "page": Integer(minimum=1, default=1),
                "per_page": Integer(minimum=1,
                                    default=20,  # FIXME use API reference
                                    maximum=50)
            })

            relations_route.response_schema = RelationInstances(self.target)

        if "w" in io:
            @relations_route.POST
            def relation_add(resource, item, target_item):
                resource.manager.relation_add(item, self.attribute, self.target, target_item)
                resource.manager.commit()
                return target_item

            relation_add.request_schema = ToOne(self.target)
            relation_add.response_schema = ToOne(self.target)

            @relation_route.DELETE
            def relation_remove(resource, item, target_id):
                target_item = self.target.manager.read(target_id)
                resource.manager.relation_remove(item, self.attribute, self.target, target_item)
                resource.manager.commit()
                return None, 204
            yield relation_route

        if io:
            yield relations_route


# class ItemMapAttribute(RouteSet):
#     """
#     Adds a route that includes the keys to a dictionary attribute and allows these to be read, set, and deleted
#     either individually or in bulk.
#
#     class Schema:
#         scores = fields.Object(field.Integer)
#
#     GET /item/:id/scores/:key/
#     PUT /item/:id/scores/:key/
#     DELETE /item/:id/scores/:key/
#
#     :param str mapping_attribute: Must map to an attribute that is of type :class:`str`
#     """
#
#     def __init__(self, cls_or_instance, io=None, **kwargs):
#         self.field = field = _field_from_object(self, cls_or_instance)
#         self.object_field = Object(field, **kwargs)
#         self.io = io
#
#     # @Route.GET(lambda r: '/<id:{}>/attribute/<key>'.format(r.meta.id_converter))
#     # def attribute(self, item, key):
#     #     pass
#
#     def routes(self):
#         field = self.field
#         object_field = self.object_field
#         attribute = field.attribute
#         rule = '/{}'.format(attribute_to_route_uri(attribute))
#         io = self.io or field.io
#
#         object = ItemRoute(rule=rule)
#         # object_property = ItemRoute(rule=rule)
#
#         @object.GET(response_schema=object_field)
#         def read(resource, item):
#             return get_value(attribute, item, {})
#
#         read.response_schema = object_field
#
#         @object.POST(schema=object_field)
#         def write(resource, item, value):
#             resource.manager.update(item, {attribute: value})
#             return value
#
#         # TODO PATCH object
#
#         # @object_property.GET(response_schema=field)
#         # def read_property(resource, item, key, value):
#         #     # TODO ensure key matches pattern.
#         #     pass
#         #
#         # @object_property.POST(schema=field)
#         # def write_property(resource, item, key, value):
#         #     # TODO ensure key matches pattern.
#         #     pass
#         #
#         # @object_property.DELETE
#         # def remove_property(resource, item, key):
#         #     # TODO ensure key matches pattern.
#         #     pass
#
#         yield object

#
# class ItemSetAttributeRoute(RouteSet):
#     """
#     GET /item/:id/values
#     POST /item/:id/value/:value_id
#     DELETE /item/:id/value/:value_id
#
#     The URL of each item must stay consistent when the order of the list changes.
#
#     Direct addressing is only supported when an `id_attribute` is given. This must be an attribute
#     that is unique and cannot be changed. Without it, only read-only mode can be supported.
#
#     Depending on the type of collection, sorting and filtering may or may not be supported.
#
#     """
#
#     def __init__(self, cls_or_instance, id_attribute=None, id_field=None, io="r"):
#         if "w" in io:
#             raise NotImplementedError("ItemListAttributeRoute only supports read-only mode for now.")
#
#         pass
#
#     # @ItemRoute.GET()
#     # def read_items(self):
#     #     pass
#     #
#     # @ItemRoute.GET()
#     # def read_item(self, item, position):
#     #     pass
#     #
#     # @read_item.POST()
#     # def add_item(self, item):
#     #     pass
