from flask_potion.exceptions import ItemNotFound
from flask_potion.instances import Pagination
from flask_potion.manager import Manager
from flask_potion.signals import before_add_to_relation, after_add_to_relation, before_remove_from_relation, \
    after_remove_from_relation
from flask_potion.utils import get_value


class MemoryManager(Manager):
    """
    An in-memory, pure-python :class:`Manager` implementation.

    .. warning::

        This manager is intended for debugging & testing only and should not be used in production.
    """

    def __init__(self, resource, model):
        super(MemoryManager, self).__init__(resource, model)
        self.id_sequence = 0
        self.items = {}
        self.session = []

    def _new_item_id(self):
        self.id_sequence += 1
        return self.id_sequence

    @staticmethod
    def _filter_items(items, conditions):
        for item in items:
            if all(condition(item) for condition in conditions):
                yield item

    @staticmethod
    def _sort_items(items, sort):
        for field, key, reverse in reversed(sort):
            items = sorted(items, key=lambda item: get_value(key, item, None), reverse=reverse)
        return items

    def _paginate(self, items, page, per_page):
        return Pagination.from_list(list(items), page, per_page)

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        collection = item.get(attribute, set())

        items = []
        for id in collection:
            try:
                items.append(target_resource.manager.read(id))
            except ItemNotFound:
                collection.remove(id)
                pass

        return Pagination.from_list(items, page, per_page)

    def relation_add(self, item, attribute, target_resource, target_item):
        before_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        item[attribute] = collection = item.get(attribute, set())
        item_id = target_item[target_resource.manager.id_attribute]
        collection.add(item_id)
        after_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)


    def relation_remove(self, item, attribute, target_resource, target_item):
        before_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        item[attribute] = collection = item.get(attribute, set())
        item_id = target_item[target_resource.manager.id_attribute]
        collection.remove(item_id)
        after_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        return self._paginate(self.instances(where=where, sort=sort), page, per_page)

    def instances(self, where=None, sort=None):
        items = self.items.values()

        if where is not None:
            items = self._filter_items(items, where)
        if sort is not None:
            items = self._sort_items(items, sort)

        return items

    def first(self, where=None, sort=None):
        try:
            return next(self.instances(where, sort))
        except StopIteration:
            raise ItemNotFound(self.resource, where=where)

    def create(self, properties, commit=True):
        item_id = self._new_item_id()
        item = dict({self.id_attribute: item_id})
        item.update(properties)

        if commit:
            self.items[item_id] = item
        else:
            self.session[item_id] = item

        return item

    def read(self, id):
        try:
            item = self.items[id]
        except KeyError:
            raise ItemNotFound(self.resource, id=id)

        return item

    def update(self, item, changes, commit=True):
        item_id = item[self.id_attribute]
        item = dict(item)
        item.update(changes)

        if commit:
            self.items[item_id] = item
        else:
            self.session.append((item_id, item))

        return item

    def delete(self, item):
        item_id = item[self.id_attribute]
        del self.items[item_id]

    def commit(self):
        for item_id, item in self.session:
            self.items[item_id] = item

    def begin(self):
        self.session = []