from werkzeug.utils import cached_property


class Schema(object):
    pass

    @property
    def schema(self):
        raise NotImplementedError()

    @cached_property
    def response(self):
        schema = self.schema()
        if isinstance(schema, tuple):
            return schema[0]
        return schema

    @cached_property
    def request(self):
        schema = self.schema()
        if isinstance(schema, tuple):
            return schema[1]
        return schema
