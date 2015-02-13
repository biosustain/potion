from operator import and_
from flask import current_app
from flask_sqlalchemy import get_state
from sqlalchemy import String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.potion.utils import get_value
from flask_potion import fields
from flask_potion.exceptions import DuplicateKey, ItemNotFound, BackendConflict
from flask_potion.backends import Manager, Pagination
from flask_potion.signals import before_create, before_update, after_update, before_delete, after_delete, after_create, \
    before_add_to_relation, after_remove_from_relation, before_remove_from_relation, after_add_to_relation

SA_COMPARATOR_EXPRESSIONS = {
    '$eq': lambda column, value: column == value,
    '$ne': lambda column, value: column != value,
    '$in': lambda column, value: column.in_(value) if len(value) else False,
    '$lt': lambda column, value: column < value,
    '$gt': lambda column, value: column > value,
    '$lte': lambda column, value: column <= value,
    '$gte': lambda column, value: column >= value,
    '$text': lambda column, value: column.op('@@')(func.plainto_tsquery(value)),
    '$startswith': lambda column, value: column.startswith(value.replace('%', '\\%')),
    '$endswith': lambda column, value: column.endswith(value.replace('%', '\\%'))
}


class SQLAlchemyManager(Manager):
    """
    A manager for SQLAlchemy models.

    Expects that :class:`Meta.model` contains an SQLALchemy declarative model.

    """
    supported_comparators = tuple(SA_COMPARATOR_EXPRESSIONS.keys())

    def __init__(self, resource, model):
        super(SQLAlchemyManager, self).__init__(resource, model)

        meta = resource.meta
        mapper = class_mapper(model)

        self.id_attribute = meta.get('id_attribute', mapper.primary_key[0].name)

        if 'id_field' in resource.meta:
            self.id_column = getattr(model, resource.meta.id_field)
        else:
            self.id_column = mapper.primary_key[0]

        # resource name: use model table's name if not set explicitly
        if not hasattr(resource.Meta, 'name'):
            meta['name'] = model.__tablename__.lower()

        fs = resource.schema
        include_fields = meta.get('include_fields', None)
        exclude_fields = meta.get('exclude_fields', None)
        read_only_fields = meta.get('read_only_fields', ())
        write_only_fields = meta.get('write_only_fields', ())
        pre_declared_fields = {f.attribute or k for k, f in fs.fields.items()}

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

                if isinstance(column.type, postgresql.ARRAY):
                    field_class = fields.Array
                    args = (fields.String,)
                elif isinstance(column.type, String) and column.type.length:
                    field_class = fields.String
                    kwargs = {'max_length': column.type.length}
                elif isinstance(column.type, postgresql.HSTORE):
                    field_class = fields.Object
                    args = (fields.String,)
                elif hasattr(postgresql, 'JSON') and isinstance(column.type, (postgresql.JSON, postgresql.JSONB)):
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

                if not (column.nullable or column.default):
                    fs.required.append(name)
                fs.set(name, field_class(*args, io=io, attribute=name, **kwargs))

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
        for attribute, reverse in sort:
            column = getattr(self.model, attribute)

            if reverse:
                yield column.desc()
            else:
                yield column.asc()

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        query = getattr(item, attribute)

        if isinstance(query, InstrumentedList):
            if page and per_page:
                return Pagination.from_list(query, page, per_page)
            return query

        if page and per_page:
            return query.paginate(page=page, per_page=per_page)
        return query.all()

    def relation_add(self, item, attribute, target_resource, target_item):
        before_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        getattr(item, attribute).append(target_item)
        after_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def relation_remove(self, item, attribute, target_resource, target_item):
        before_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        getattr(item, attribute).remove(target_item)
        after_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def paginated_instances(self, page, per_page, where=None, sort=None):
        return self.instances(where=where, sort=sort).paginate(page=page, per_page=per_page)

    def instances(self, where=None, sort=None):
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

            if current_app.debug:
                raise BackendConflict(debug_info=dict(statement=e.statement, params=e.params))
            raise BackendConflict()

        after_create.send(self.resource, item=item)
        return item

    def read(self, id):
        try:
            # NOTE SQLAlchemy's .get() does not work well with .filter(), therefore using .one()
            return self._query().filter(self.id_column == id).one()
        except NoResultFound:
            raise ItemNotFound(self.resource, id=id)

    def update(self, item, changes, commit=True):
        session = self._get_session()
        actual_changes = {
            key: value for key, value in changes.items()
            if get_value(key, item, None) != value
        }

        try:
            before_update.send(self.resource, item=item, changes=actual_changes)

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

        after_update.send(self.resource, item=item, changes=actual_changes)
        return item

    def delete(self, item):
        before_delete.send(self.resource, item=item)

        session = self._get_session()
        session.delete(item)
        session.commit()

        after_delete.send(self.resource, item=item)
