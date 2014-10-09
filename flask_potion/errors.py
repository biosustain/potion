

class PotionError(Exception):

    def __init__(self, code):
        self.code = code


class InlineNotFoundError(PotionError):

    def __init__(self, resource, natural_key=None, id=None):
        super(InlineNotFoundError, self).__init__(404)


class ValidationError(PotionError):

    def __init__(self, kind, property, schema_trace=None):
        super(ValidationError, self).__init__(400)