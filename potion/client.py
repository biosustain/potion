

class Client(object):

    def __init__(self, schema_uri, auth=None):
        self._schema_uri = schema_uri

    def _get_schema(self):
        res = requests.get(self._schema_uri)


class Route(object):

    def __init__(self, uri, method=None):
        pass

    def __call__(self, **kwargs):
        pass

        # TODO check Link describedBy header for possible conversion of results.


class Resource(object):

    # NOTE the `instances`, `create` and `self` routes are abstracted into:
    # instances -> access like a list/iterator
    # self -> Resource.read(id, etc.)
    # create -> Resource(**data).save()
    #
    # If an `update` relation is available, .save() will call this relation with any changes made.

    @classmethod
    def read(self, *args):
        pass

    def save(self):
        pass

    def __getitem__(self, item):
        # TODO support slices
        # TODO should this be for pagination, id lookup, or both?
        pass