from importlib import import_module
import inspect

import six
from flask import current_app, _app_ctx_stack


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

        if binding and binding.api:
            raise RuntimeError('Resource named "{}" is not registered with the Api it is bound to.'.format(name))
        raise RuntimeError('Resource named "{}" cannot be found; the reference is not bound to an Api.'.format(name))

    def __repr__(self):
        return "<ResourceReference '{}'>".format(self.value)


class ResourceBound(object):
    resource = None

    def _on_bind(self, resource):
        pass

    def bind(self, resource):
        if self.resource is None:
            self.resource = resource
            self._on_bind(resource)
        elif self.resource != resource:
            return self.rebind(resource)
        return self

    def rebind(self, resource):
        raise NotImplementedError('{} is already bound to {}'
                                  ' and does not support rebinding to {}'.format(repr(self), self.resource, resource))


def _bind_schema(schema, resource):
    if isinstance(schema, ResourceBound):
        return schema.bind(resource)
    return schema