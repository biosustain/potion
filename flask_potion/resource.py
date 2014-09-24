from collections import namedtuple


class Link(namedtuple('Link', ('uri', 'rel'))):
    pass

class Set(HasSchema):
    """
    This is what implements all of the pagination, filter, and sorting logic.
    """

    def __init__(self, type, default_sort=None):
        pass

    def get(self, items, where=None, sort=None, page=None, per_page=None):

        items = self._filter_where(items, where)
        items = self._sort_by(items, sort)
        items = self._paginate(items, page, per_page)


        return items, 200, {
            "Link": ','.join(str(link) for link in (
                Link(self.resource.schema.uri, rel="describedBy"),
            ))
        }

    def put(self, item, child):
        raise NotImplementedError()

    def delete(self, item, child):
        raise NotImplementedError()



class Resource(object):
    pass
