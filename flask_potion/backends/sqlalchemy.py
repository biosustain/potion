from operator import and_
from flask import current_app, abort
from flask_sqlalchemy import get_state
from sqlalchemy import types as sa_types
from sqlalchemy.dialects import postgres
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from .. import fields
from ..exceptions import DuplicateKey, ItemNotFound
from . import Relation, Manager
from ..signals import before_create, before_update, after_update, before_delete, after_delete

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

                if isinstance(column.type, postgres.ARRAY):
                    field_class = fields.Array
                    args = (fields.String,)
                elif isinstance(column.type, sa_types.String) and column.type.length:
                    field_class = fields.String
                    kwargs = {'max_length': column.type.length}
                elif isinstance(column.type, postgres.HSTORE):
                    field_class = fields.Object
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
                #     fs.required.append(name)
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

        return item

    def read(self, id):
        try:
            # NOTE SQLAlchemy's .get() does not work well with .filter(), therefore using .one()
            return self._query().filter(self.id_column == id).one()
        except NoResultFound:
            raise ItemNotFound(self.resource, id=id)

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