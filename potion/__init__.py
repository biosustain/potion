from flask import Flask
from flask_potion import Api


class Potion(Flask):
    def __init__(self, *args, api_decorators=None, **kwargs):
        super(Potion, self).__init__(*args, **kwargs, )
        self.api = Api(self, prefix=None, decorators=api_decorators)

    def add(self, resource):
        self.api.add_resource(resource)