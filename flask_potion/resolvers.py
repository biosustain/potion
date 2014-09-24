from flask.ext.potion.schema import HasSchema


class KeyResolver(HasSchema):
    pass

    def schema(self):
        raise NotImplementedError()


class KeyFormatter(HasSchema):
    pass


class GetOrCreateResolver(KeyResolver):
    """
    One of:
        ``$upsert``, ``$getOrCreate``

    ::

        {
            "$upsert": true,
            # .. properties ..
        }

    """

    def __init__(self, *using_properties, first_if_multiple=True):
        pass


class RefObjectResolver(KeyResolver):
    """

    JSON-Reference

    http://tools.ietf.org/html/draft-pbryan-zyp-json-ref-03

    Although this Internet-Draft seems to have expired, the idea works pretty well standardized or not.
    It is similar to the EJSON reference model.
    ::

        {"$ref": "/resource/1" }

    """
    pass


class PropertyResolver(KeyResolver):
    def __init__(self, property):
        pass


class PropertiesResolver(KeyResolver):
    def __init__(self, *properties):
        pass

class IdentifierResolver(KeyResolver):
    def __init__(self):
        pass