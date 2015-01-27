from importlib import import_module
import inspect
import six
from flask import current_app


class ResourceReference(object):
    def __init__(self, value):
        self.value = value

    def resolve(self, binding=None):
        """
        Attempt to resolve the reference value and return the matching :class:`Resource`.
        """
        name = self.value

        if name == 'self':
            return binding

        from .resource import ModelResource
        if inspect.isclass(name) and issubclass(name, ModelResource):
            return name

        potion = None
        if binding and binding.api:
            potion = binding.api
        elif hasattr(current_app, 'potion'):  # FIXME soft failure if no app context
            potion = current_app.potion
        if potion:
            if name in potion.resources:
                return potion.resources[name]

        try:
            if isinstance(name, six.string_types):
                module_name, class_name = name.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)
        except ValueError:
            pass

        raise RuntimeError('Resource named "{}" is not registered with Potion'.format(name))

    def __repr__(self):
        return "<ResourceReference '{}'>".format(self.value)


class ResourceBound(object):
    resource = None

    def bind(self, resource):
        self.resource = resource