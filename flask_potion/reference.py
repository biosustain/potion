from importlib import import_module
import inspect
import six
from flask import current_app


class ResourceReference(object):
    def __init__(self, name):
        self.name = name

    def resolve(self, binding=None):
        """
        Resolve attempts three different methods for resolving a reference:

        - if the reference is a Resource, return it
        - if the reference is a Resource name in the current_app.unrest API context, return it
        - if the reference is a complete module.class string, import and return it
        """
        name = self.name

        if name == 'self':
            return binding

        from .resource import Resource
        if inspect.isclass(name) and issubclass(name, Resource):
            return name

        # FIXME XXX need a better back-reference to the Potion instance
        if hasattr(current_app, 'potion'):
            return current_app.potion.get_resource_class(name)

        try:
            if isinstance(name, six.string_types):
                module_name, class_name = name.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)
        except ValueError:
            pass

        raise RuntimeError('Resource named "{}" is not registered with Potion'.format(name))

    def __repr__(self):
        return "<ResourceReference '{}'>".format(self.resolve().meta.name)


class ResourceBound(object):
    resource = None

    def bind(self, resource):
        self.resource = resource