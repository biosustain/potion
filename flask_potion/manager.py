from __future__ import division
from itertools import islice
from math import ceil
from operator import attrgetter, and_, itemgetter
import datetime
from flask import current_app
import six
from sqlalchemy import func
import sqlalchemy.types as sa_types
from sqlalchemy.dialects import postgres
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from .exceptions import DuplicateKey, ItemNotFound
from . import fields
from .utils import get_value
from .signals import before_create, before_update, after_update, before_delete, after_delete
from flask_sqlalchemy import get_state
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


class Pagination(object):

    def __init__(self, items, page, per_page, pages):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.pages = pages

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages


class Manager(object):
    relation_type = Relation
    supported_comparators = ()
    
    def __init__(self, resource, model):
        self.resource = resource
        self.model = model

    @staticmethod
    def _get_field_from_python_type(python_type):
        try:
            return {
                str: fields.String,
                six.text_type: fields.String,
                int: fields.Integer,
                float: fields.Number,
                bool: fields.Boolean,
                list: fields.Array,
                dict: fields.KeyValue,
                datetime.date: fields.DateString,
                datetime.datetime: fields.DateTimeString
            }[python_type]
        except KeyError:
            raise RuntimeError('No appropriate field class for "{}" type found'.format(python_type))

    def relation_factory(self, attribute, target_resource=None):
        return self.relation_type(self.resource, attribute, target_resource)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        pass

    def instances(self, where=None, sort=None):
        pass
    
    def create(self, properties, commit=True):
        pass
    
    def read(self, id):
        pass
    
    def update(self, item, changes, commit=True):
        pass
    
    def delete(self, item):
        pass

    def delete_by_id(self, id):
        return self.delete(self.read(id))

    def commit(self):
        pass

    def begin(self):
        pass


class MemoryRelation(Relation):
    pass


class MemoryManager(Manager):
    relation_type = MemoryRelation
    supported_comparators = ('$eq', '$ne', '$lt', '$gt', '$le', '$ge', '$in', '$startswith', '$endswith')

    def __init__(self, resource, model):
        super(MemoryManager, self).__init__(resource, model)
        self.id_attribute = resource.meta.get('id_attribute', 'id')
        self.id_sequence = 0
        self.items = {}
        self.session = []

    def _new_item_id(self):
        self.id_sequence += 1
        return self.id_sequence

    @staticmethod
    def _filter_items(items, where):
        for item in items:
            # TODO ensure condition uses the field attribute, not the post attribute
            if all(condition(item) for condition in where):
                yield item

    @staticmethod
    def _sort_items(items, sort):
        for key, reverse in reversed(sort):
            items = sorted(items, key=lambda item: get_value(key, item, None), reverse=reverse)
        return items

    def _paginate(self, items, page, per_page):
        items = list(items)
        start = per_page * (page - 1)
        pages = int(ceil(len(items) / per_page))
        return Pagination(items[start:start + per_page], page, per_page, pages)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        return self._paginate(self.instances(where=where, sort=sort), page, per_page)

    def instances(self, where=None, sort=None):
        items = self.items.values()

        if where is not None:
            items = self._filter_items(items, where)
        if sort is not None:
            items = self._sort_items(items, sort)

        return items

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


class SQLAlchemyRelation(Relation):
    def instances(self, item, where=None, sort=None, page=None, per_page=None):
        query = getattr(item, self.attribute)
        # TODO pagination, sort, etc.
        return query.all()

    def add(self, item, target_item):
        getattr(item, self.attribute).append(target_item)

    def remove(self, item, target_item):
        getattr(item, self.attribute).remove(target_item)


SA_COMPARATOR_EXPRESSIONS = {
    '$eq': lambda column, value: column == value,
    '$ne': lambda column, value: column != value,
    '$in': lambda column, value: column.in_(value) if len(value) else False,
    '$lt': lambda column, value: column < value,
    '$gt': lambda column, value: column > value,
    '$le': lambda column, value: column <= value,
    '$ge': lambda column, value: column >= value,
    '$text': lambda column, value: column.op('@@')(func.plainto_tsquery(value)),
    '$startswith': lambda column, value: column.startswith(value.replace('%', '\\%')),
    '$endswith': lambda column, value: column.endswith(value.replace('%', '\\%'))
}

class SQLAlchemyManager(Manager):
    relation_type = SQLAlchemyRelation
    supported_comparators = tuple(SA_COMPARATOR_EXPRESSIONS.keys())

    def __init__(self, resource, model):
        super(SQLAlchemyManager, self).__init__(resource, model)

        meta = resource.meta
        mapper = class_mapper(model)

        self.id_attribute = meta.get('id_attribute', mapper.primary_key[0].name)

        if resource.meta.id_field:
            self.id_column = getattr(model, resource.meta.id_field)
        else:
            self.id_column = mapper.primary_key[0]

        # resource name: use model table's name if not set explicitly
        if 'name' not in meta:
            meta['name'] = model.__tablename__.lower()

        fs = resource.schema
        include_fields = meta.get('include_fields', None)
        exclude_fields = meta.get('exclude_fields', None)
        read_only_fields = meta.get('read_only_fields', ())
        write_only_fields = meta.get('write_only_fields', ())
        pre_declared_fields = {f.attribute or k for k, f in fs.schema.items()}

        for name, column in mapper.columns.items():
            if (include_fields and name in include_fields) or \
                    (exclude_fields and name not in exclude_fields) or \
                    not (include_fields or exclude_fields):
                if column.primary_key or column.foreign_keys:
                    continue
                if name in pre_declared_fields:
                    continue

                args = ()
                kwargs = {}

                if isinstance(column.type, postgres.ARRAY):
                    field_class = fields.Array
                    args = (fields.String,)
                elif isinstance(column.type, sa_types.String) and column.type.length:
                    field_class = fields.String
                    kwargs = {'max_length': column.type.length}
                elif isinstance(column.type, postgres.HSTORE):
                    field_class = fields.KeyValue
                    args = (fields.String,)
                elif hasattr(postgres, 'JSON') and isinstance(column.type, postgres.JSON):
                    field_class = fields.Raw
                    kwargs = {"schema": {}}
                else:
                    field_class = self._get_field_from_python_type(column.type.python_type)

                kwargs['nullable'] = column.nullable

                if column.default is not None and column.default.is_scalar:
                    kwargs['default'] = column.default.arg

                io = "rw"
                if name in read_only_fields:
                    io = "r"
                elif name in write_only_fields:
                    io = "w"

                # if not (column.nullable or column.default):
                #     meta["required_fields"].append(name)
                fs.fields["name"] = field_class(*args, io=io, attribute=name, **kwargs)

    @staticmethod
    def _get_session():
        return get_state(current_app).db.session

    def _query(self):
        return self.model.query

    def _where_expression(self, where):
        expressions = []

        for condition in where:
            column = getattr(self.model, condition.attribute)
            expressions.append(SA_COMPARATOR_EXPRESSIONS[condition.comparator.name](column, condition.value))

        if len(expressions) == 1:
            return expressions[0]

        # TODO ranking by default with text-search.

        return and_(*expressions)

    def _order_by(self, sort):
        for attribute, reverse in sort.items():
            column = getattr(self.model, attribute)

            if reverse:
                yield column.desc()
            else:
                yield column.asc()

    def paginated_instances(self, page, per_page, where=None, sort=None):
        return self.instances(where=where, sort=sort).paginate(page=page, per_page=per_page)

    def instances(self, where=None, sort=None, page=None, per_page=None):
        query = self._query()

        if where:
            query = query.filter(self._where_expression(where))
        if sort:
            query = query.order_by(*self._order_by(sort))

        return query

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
            return self._query().filter(self.id_column == id).one()
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