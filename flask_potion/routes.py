"""



sub-resources:

strict sub-resources are no problem.


one-to-one:

use filters.




one-to-many:

/project/1/tasks
/task.project


/task/1/project?

/project/tasks






many-to-many:


/group/1/members
/user/1.groups


/user/1/memberships
/membership/1,1



Relationships should be references rather than full items so that the cache only has to be invalidated if an item is
added or removed, but not if any other values change.


/user/{userID}/groups/{groupID}
should do a HTTP redirect to:
/memberships/{uuid}





"""

class Route(object):

    def __init__(self, binding=None, attribute=None):
        self.binding = binding
        self.attribute = attribute

        self.schema = None
        self.target_schema = None
        self.described_by = None


class ItemRoute(Route):
    pass


class ItemAttributeRoute(ItemRoute):

    def __init__(self, attribute_field, **kwargs):
        super(ItemAttributeRoute, self).__init__(**kwargs)
        self.attribute_field = attribute_field


class ItemSetRoute(ItemRoute):

    def __init__(self, target_resource=None, **kwargs):
        pass

    def get(self):
        raise NotImplementedError()

    def put(self, item, child):
        raise NotImplementedError()

    def delete(self, item, child):
        raise NotImplementedError()


class RelationshipRoute(ItemSetRoute):
    """

    A relationship route returns `{"$ref"}` objects for purposes of cache-ability, a core principle of REST.
    """

    def __init__(self, resource, backref=None, io="rw", attribute=None, **kwargs):
        super(RelationshipRoute, self).__init__(kwargs.pop('binding', None), attribute)
        self.resource = resource
        self.backref = backref
        self.io = io

