from werkzeug.exceptions import Conflict, BadRequest, NotFound


class InlineNotFoundError(NotFound):

    def __init__(self, resource, natural_key=None, id=None):
        NotFound.__init__()


class ValidationError(BadRequest):

    def __init__(self, kind, property, schema_trace=None):
        BadRequest.__init__(self)


class DuplicateKey(Conflict):
    def __init__(self, **kwargs):
        Conflict.__init__(self)
        self.data = kwargs

