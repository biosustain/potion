import re
import sys
from collections import OrderedDict
from types import MethodType

from flask import request
from werkzeug.utils import cached_property

from flask_potion.reference import _bind_schema
from flask_potion.fields import ToOne, Integer
from flask_potion.fields import _field_from_object
from flask_potion.instances import Instances, RelationInstances
from flask_potion.reference import ResourceBound, ResourceReference
from flask_potion.schema import Schema, FieldSet
from flask_potion.utils import get_value

HTTP_METHODS = ('GET', 'PUT', 'POST', 'PATCH', 'DELETE')

HTTP_METHOD_VERB_DEFAULTS = {
    'GET': 'read',
    'PUT': 'create',
    'POST': 'create',
    'PATCH': 'update',
    'DELETE': 'destroy'
}

def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)


def attribute_to_route_uri(s):
    return s.replace('_', '-')


def to_camel_case(s):
    return s[0].lower() + s.title().replace('_', '')[1:] if s else s


def _method_decorator(method):
    def wrapper(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return self.for_method(method, args[0], **kwargs)
        else:
            return lambda f: self.for_method(method, f, *args, **kwargs)

    wrapper.__name__ = method
    return wrapper


class Route(object):
    """

    Routes are not bound to a specific resource and their schema, generated using :meth:`schema_factory` can vary depending on the resource.

    If ``view_func`` has an ``__annotations__`` attribute (a Python 3.x function annotation), the annotations
    will be used to generate the ``request_schema`` and ``response_schema``. The *return* annotation in this case
    is expected to be a :class:`schema.Schema` used for responses, and all other annotations are expected to be of type :class:`fields.Raw`
    and are combined into a :class:`schema.Fieldset`.

    .. attribute:: relation

        A relation for the string, equal to ``rel`` if one was given.

    .. attribute:: request_schema

        request schema (not resource-bound)

    .. attribute:: response_schema

        response schema (not resource-bound)


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
        :param schema.Schema response_schema: response schema
        :param bool format_response: whether the response should be converted using the response schema

    .. attribute:: schema

        Used to get and set the request schema for the most recently decorated request method view function

    .. attribute:: response_schema

        Used to get and set the response schema for the most recently decorated request method view function

    .. attribute:: method_links

        A dictionary mapping of method names (in upper case) to :class:`routes.Link` objects containing the method view functions.

    :param str method: a HTTP request method name (upper case)
    :param callable view_func: view function
    :param rule: url rule string or callable returning a string
    :param str rel: relation
    :param str title: title of schema
    :param str description: description of schema
    :param routes.Route route: route this link belongs to
    :param schema.Schema schema: request schema
    :param schema.Schema response_schema: response schema
    :param bool format_response: whether the response should be converted using the response schema

    """

    def __init__(self,
                 method=None,
                 view_func=None,
                 rule=None,
                 attribute=None,
                 rel=None,
                 title=None,
                 description=None,
                 schema=None,
                 response_schema=None,
                 format_response=True):
        self.rel = rel
        self.rule = rule
        self.method = method
        self.attribute = attribute

        self.title = title
        self.description = description

        self.view_func = view_func
        self.format_response = format_response

        annotations = getattr(view_func, '__annotations__', None)

        if isinstance(annotations, dict) and len(annotations):
            self.request_schema = FieldSet({name: field for name, field in annotations.items() if name != 'return'})
            self.response_schema = annotations.get('return', response_schema)
        else:
            self.request_schema = schema
            self.response_schema = response_schema

        self._related_routes = ()

        for method in HTTP_METHODS:
            setattr(self, method, MethodType(_method_decorator(method), self))

    @property
    def relation(self):
        if self.rel:
            return self.rel
        # elif len(self.route.methods()) == 1:
        #     return self.route.attribute
        else:
            verb = HTTP_METHOD_VERB_DEFAULTS.get(self.method, self.method.lower())
            return to_camel_case("{}_{}".format(verb, self.attribute))

    def schema_factory(self, resource):
        """
        Returns a link schema for a specific resource.
        """
        request_schema = _bind_schema(self.request_schema, resource)
        response_schema = _bind_schema(self.response_schema, resource)

        # NOTE "href" for rel="instances" MUST NOT be relative; others MAY BE relative
        schema = OrderedDict([
            ("rel", self.relation),
            ("href", url_rule_to_uri_pattern(self.rule_factory(resource, relative=False))),
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

    def for_method(self,
                   method,
                   view_func,
                   rel=None,
                   title=None,
                   description=None,
                   schema=None,
                   response_schema=None,
                   **kwargs):

        attribute = kwargs.pop('attribute', self.attribute)
        format_response = kwargs.pop('format_response', self.format_response)

        instance = self.__class__(method,
                                  view_func,
                                  rule=self.rule,
                                  rel=rel,
                                  title=title,
                                  description=description,
                                  schema=schema,
                                  response_schema=response_schema,
                                  attribute=attribute,
                                  format_response=format_response,
                                  **kwargs)

        instance._related_routes = self._related_routes + (self,)
        return instance

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return lambda *args, **kwargs: self.view_func.__call__(obj, *args, **kwargs)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, repr(self.rule))

    @property
    def request_schema(self):
        return self.schema

    @request_schema.setter
    def request_schema(self, schema):
        self.schema = schema

    def rule_factory(self, resource, relative=False):
        """
        Returns a URL rule string for this route and resource.

        :param flask_potion.Resource resource:
        :param bool relative: whether the rule should be relative to ``resource.route_prefix``
        """
        rule = self.rule

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(self.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative or resource.route_prefix is None:
            return rule[1:]

        return ''.join((resource.route_prefix, rule))

    def view_factory(self, name, resource):
        """
        Returns a view function for all links within this route and resource.

        :param name: Flask view name
        :param flask_potion.Resource resource:
        """
        request_schema = _bind_schema(self.request_schema, resource)
        response_schema = _bind_schema(self.response_schema, resource)
        view_func = self.view_func

        def view(*args, **kwargs):
            instance = resource()
            if isinstance(request_schema, (FieldSet, Instances)):
                kwargs.update(request_schema.parse_request(request))
            elif isinstance(request_schema, Schema):
                args += (request_schema.parse_request(request),)

            response = view_func(instance, *args, **kwargs)
            # TODO add 'describedBy' link header if response schema is a ToOne/ToMany/Instances field.
            if response_schema is None or not self.format_response:
                return response
            else:
                return response_schema.format_response(response)

        return view


def _route_decorator(method):
    @classmethod
    def decorator(cls, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return cls(method, args[0])
        else:
            return lambda f: cls(method, f, *args, **kwargs)

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

    def rule_factory(self, resource, relative=False):
        rule = self.rule
        id_matcher = '<{}:id>'.format(resource.meta.id_converter)

        if rule is None:
            rule = '/{}'.format(attribute_to_route_uri(self.attribute))
        elif callable(rule):
            rule = rule(resource)

        if relative or resource.route_prefix is None:
            return rule[1:]

        return ''.join((resource.route_prefix, '/', id_matcher, rule))

    def view_factory(self, name, resource):
        original_view = super(ItemRoute, self).view_factory(name, resource)

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
    :param str io: ``r``, ``u``, or ``ru`` - defaults to the field's ``io`` attribute
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
            def read_attribute(resource, item):
                return get_value(attribute, item, field.default)

            yield route.for_method('GET',
                                   read_attribute,
                                   response_schema=field,
                                   rel=to_camel_case('read_{}'.format(route.attribute)))

        if "u" in io:
            def update_attribute(resource, item, value):
                attribute = field.attribute or route.attribute
                item = resource.manager.update(item, {attribute: value})
                return get_value(attribute, item, field.default)

            yield route.for_method('POST',
                                   update_attribute,
                                   schema=field,
                                   response_schema=field,
                                   rel=to_camel_case('update_{}'.format(route.attribute)))


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
            def relation_instances(resource, item, page, per_page):
                return resource.manager.relation_instances(item,
                                                           self.attribute,
                                                           self.target,
                                                           page,
                                                           per_page)

            yield relations_route.for_method('GET',
                                             relation_instances,
                                             rel=self.attribute,
                                             response_schema=RelationInstances(self.target),
                                             schema=FieldSet({
                                                 "page": Integer(minimum=1, default=1),
                                                 "per_page": Integer(minimum=1,
                                                                     default=20,  # FIXME use API reference
                                                                     maximum=50)
                                             }))

        if "w" in io or "u" in io:
            def relation_add(resource, item, target_item):
                resource.manager.relation_add(item, self.attribute, self.target, target_item)
                resource.manager.commit()
                return target_item

            yield relations_route.for_method('POST',
                                             relation_add,
                                             rel=to_camel_case('add_{}'.format(self.attribute)),
                                             response_schema=ToOne(self.target),
                                             schema=ToOne(self.target))

            def relation_remove(resource, item, target_id):
                target_item = self.target.manager.read(target_id)
                resource.manager.relation_remove(item, self.attribute, self.target, target_item)
                resource.manager.commit()
                return None, 204

            yield relation_route.for_method('DELETE',
                                            relation_remove,
                                            rel=to_camel_case('remove_{}'.format(self.attribute)))

