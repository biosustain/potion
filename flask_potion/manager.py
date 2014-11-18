from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from .exceptions import DuplicateKey, ItemNotFound
from .signals import before_create, before_update, after_update, before_delete, after_delete
from flask_sqlalchemy import BaseQuery, Pagination, get_state
from werkzeug.exceptions import abort


class Relation(object):
    def __init__(self, resource, attribute, target_resource=None):
        self.resource = resource
        self.attribute = attribute
        self.target_resource = target_resource

    def instances(self, item, where=None, sort=None, page=None, per_page=None):
        raise NotImplementedError()

    def add(self, item, target_item):
        raise NotImplementedError()

    def remove(self, item, target_item):
        raise NotImplementedError()


class Manager(object):
    relation_type = Relation
    
    def __init__(self, resource, model):
        self.resource = resource
        self.model = model

    def relation_factory(self, attribute, target_resource=None):
        return self.relation_type(self.resource, attribute, target_resource)

    def instances(self, where=None, sort=None, page=None, per_page=None):
        pass
    
    def create(self, properties, commit=True):
        pass
    
    def read(self, id):
        pass
    
    def update(self, item, changes, commit=True):
        pass
    
    def delete(self, item):
        pass

    def commit(self):
        pass

    def begin(self):
        pass


class MemoryRelation(Relation):
    pass


class MemoryManager(Manager):
    relation_type = MemoryRelation

    def __init__(self, resource, model):
        super(MemoryManager, self).__init__(resource, model)
        self.id_attribute = resource.meta.get('id_attribute', 'id')
        self.id_sequence = 0
        self.items = {}
        self.session = {}

    def _new_item_id(self):
        self.id_sequence += 1
        return self.id_sequence

    def instances(self):
        # TODO filter, sort, pagination
        return list(self.items.values())

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
            self.session[item_id] = item

        return item

    def delete(self, item):
        item_id = item[self.id_attribute]
        del self.items[item_id]

    def commit(self):
        for id, item in self.session:
            self.items[id] = item

    def begin(self):
        self.session = {}



class SQLAlchemyRelation(Relation):
    def instances(self, item, where=None, sort=None, page=None, per_page=None):
        query = getattr(item, self.attribute)
        # TODO pagination, sort, etc.
        return query.all()

    def add(self, item, target_item):
        getattr(item, self.attribute).append(target_item)

    def remove(self, item, target_item):
        getattr(item, self.attribute).remove(target_item)


class SQLAlchemyManager(Manager):
    relation_type = SQLAlchemyRelation

    def __init__(self, resource, model):
        super(SQLAlchemyManager, self).__init__(resource, model)

        mapper = resource.meta.mapper

        if resource.meta.id_field:
            self._id_column = getattr(model, resource.meta.id_field)
        else:
            self._id_column = mapper.primary_key[0]

    @staticmethod
    def _get_session():
        return get_state(current_app).db.session

    def _query(self):
        return self.model.query

    def instances(self):
        query = self._query()
        # TODO filters
        # TODO sort
        # TODO pagination
        return query.all()

    def create(self, properties, commit=True):
        # noinspection properties
        item = self.model()

        for key, value in properties.items():
            setattr(item, key, value)

        before_create.send(self.resource, item=item)

        session = self._get_session()

        try:
            session.add(item)
            if commit:
                session.commit()
        except IntegrityError as e:
            session.rollback()

            if hasattr(e.orig, 'pgcode'):
                if e.orig.pgcode == "23505":  # duplicate key
                    raise DuplicateKey(detail=e.orig.diag.message_detail)
            raise

    def read(self, id):
        try:
            # NOTE SQLAlchemy's .get() does not work well with .filter(), therefore using .one()
            return self._query().filter(self._id_column == id).one()
        except NoResultFound:
            abort(404, resource=self.resource.meta.name, id=id)

    def update(self, item, changes, commit=True):
        session = self._get_session()

        try:
            before_update.send(self.resource, item=item, changes=changes)

            for key, value in changes.items():
                setattr(item, key, value)

            if commit:
                session.commit()
        except IntegrityError as e:
            session.rollback()

            # XXX need some better way to detect postgres engine.
            if hasattr(e.orig, 'pgcode'):
                if e.orig.pgcode == '23505':  # duplicate key
                    raise DuplicateKey(detail=e.orig.diag.message_detail)
            raise

        after_update.send(self.resource, item=item, changes=changes)
        return item

    def delete(self, item):
        before_delete.send(self.resource, item=item)

        session = self._get_session()
        session.delete(item)
        session.commit()

        after_delete.send(self, item=item)


class PrincipalsManager(SQLAlchemyManager):
    pass