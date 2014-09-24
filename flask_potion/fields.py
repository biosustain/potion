class Raw(object):
    """
    :param io: one of "r", "w" and "rw"
    :param schema: JSON-schema for field, or :class:`callable` resolving to a JSON-schema when called
    :param default: optional default value, must be JSON-convertible
    :param attribute: key on parent object, optional.
    :param nullable: whether the field is nullable.
    """

    def __init__(self, schema, io="rw", default=None, attribute=None, nullable=False):
        pass


class Array(Raw):
    pass


class Object(Raw):
    def __init__(self, properties=None, pattern_properties=None, advanced_properties=None, nullable=False):
        pass


class String(Raw):
    def __init__(self, min_length=None, max_length=None, pattern=None, enum=None, **kwargs):
        pass


class Boolean(Raw):
    def __init__(self, **kwargs):
        super(Boolean, self).__init__({"type": "boolean"}, **kwargs)

    def format(self, value):
        return bool(value)


class Integer(Raw):
    def __init__(self, minimum=None, maximum=None, **kwargs):
        schema = {"type": "integer"}

        if minimum is not None:
            schema['minimum'] = minimum
        if maximum is not None:
            schema['maximum'] = maximum

        super(Integer, self).__init__(schema, **kwargs)

    def format(self, value):
        return int(value)


class PositiveInteger(Integer):
    """
    Only accepts integers >=0.
    """

    def __init__(self, default=0, maximum=None, **kwargs):
        super(PositiveInteger, self).__init__(minimum=0, maximum=maximum, **kwargs)


class Number(Raw):
    def __init__(self,
                 default=0,
                 minimum=None,
                 maximum=None,
                 exclusive_minimum=False,
                 exclusive_maximum=False,
                 **kwargs):

        schema = {"type": "number"}

        if minimum is not None:
            schema['minimum'] = minimum
            if exclusive_minimum:
                schema['exclusiveMinimum'] = True

        if maximum is not None:
            schema['maximum'] = maximum
            if exclusive_maximum:
                schema['exclusiveMaximum'] = True

        super(Number, self).__init__(schema, **kwargs)

    def format(self, value):
        return float(value)


class Null(Raw):
    def __init__(self, io="rw", attribute=None):
        super(Null, self).__init__({"type": "null"}, io=io, attribute=attribute)


class ToOne(Raw):
    """

    Different schemas for read & write:

    {
        "type": "object",
        "properties": {
            "$ref": {
                "type": "string",
                "format": "uri",
                "pattern": "^{}".format(re.escape(resource_url))
            }
        },
        "required": ["$ref"]
    }

    {
        "type": ["null", "object"],
        "anyOf": {
            "$ref": "{}/schema#definitions/_resolvers".format(resource_url)
        }
    }


    """
    pass

