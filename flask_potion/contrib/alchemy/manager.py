from flask import current_app
from flask_sqlalchemy import Pagination as SAPagination, get_state
from sqlalchemy import String, or_, and_
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import class_mapper, aliased
from sqlalchemy.orm.attributes import ScalarObjectAttributeImpl
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.exc import NoResultFound

from flask_potion import fields
from flask_potion.contrib.alchemy.filters import FILTER_NAMES, FILTERS_BY_TYPE, SQLAlchemyBaseFilter
from flask_potion.exceptions import ItemNotFound, DuplicateKey, BackendConflict
from flask_potion.instances import Pagination
from flask_potion.manager import RelationalManager
from flask_potion.signals import before_add_to_relation, after_add_to_relation, before_remove_from_relation, \
    after_remove_from_relation, before_create, after_create, before_update, after_update, before_delete, after_delete
from flask_potion.utils import get_value


class SQLAlchemyManager(RelationalManager):
    """
    A manager for SQLAlchemy models.

    Expects that ``Meta.model`` contains a SQLALchemy declarative model.

    """
    FILTER_NAMES = FILTER_NAMES
    FILTERS_BY_TYPE = FILTERS_BY_TYPE
    PAGINATION_TYPES = (Pagination, SAPagination)

    def _init_model(self, resource, model, meta):
        mapper = class_mapper(model)

        self.model = model

        if meta.id_attribute:
            self.id_column = getattr(model, resource.meta.id_attribute)
            self.id_attribute = meta.id_attribute
        else:
            self.id_column = mapper.primary_key[0]
            self.id_attribute = mapper.primary_key[0].name

        self.id_field = self._get_field_from_column_type(self.id_column, self.id_attribute, io="r")
        self.default_sort_expression = self._get_sort_expression(
            model, meta, self.id_column)

        fs = resource.schema
        if meta.include_id:
            fs.set('$id', self.id_field)
        else:
            fs.set('$uri', fields.ItemUri(resource, attribute=self.id_attribute))

        if meta.include_type:
            fs.set('$type', fields.ItemType(resource))

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

                io = "rw"
                if name in read_only_fields:
                    io = "r"
                elif name in write_only_fields:
                    io = "w"

                if "w" in io and not (column.nullable or column.default):
                    fs.required.add(name)
                fs.set(name, self._get_field_from_column_type(column, name, io=io))

    def _get_sort_expression(self, model, meta, id_column):
        if meta.sort_attribute is None:
            return id_column.asc()

        attr_name, reverse = meta.sort_attribute
        attr = getattr(model, attr_name)
        return attr.desc() if reverse else attr.asc()

    def _get_field_from_column_type(self, column, attribute, io="rw"):
        args = ()
        kwargs = {}

        if isinstance(column.type, postgresql.ARRAY):
            field_class = fields.Array
            args = (fields.String,)
        elif isinstance(column.type, postgresql.UUID):
            field_class = fields.UUID
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
            try:
                python_type = column.type.python_type
            except NotImplementedError:
                raise RuntimeError('Unable to auto-detect the correct field type for {}! '
                                   'You need to specify it manually in ModelResource.Schema'.format(column))
            field_class = self._get_field_from_python_type(python_type)

        kwargs['nullable'] = column.nullable

        if column.default is not None:
            if column.default.is_sequence:
                pass
            elif column.default.is_scalar:
                kwargs['default'] = column.default.arg

        return field_class(*args, io=io, attribute=attribute, **kwargs)

    def _init_filter(self, filter_class, name, field, attribute):
        return filter_class(name,
                            field=field,
                            attribute=field.attribute or attribute,
                            column=getattr(self.model, field.attribute or attribute))

    def _is_sortable_field(self, field):
        if super(SQLAlchemyManager, self)._is_sortable_field(field):
            return True
        elif isinstance(field, fields.ToOne):
            return isinstance(field.target.manager, SQLAlchemyManager)
        else:
            return False

    @staticmethod
    def _get_session():
        return get_state(current_app).db.session

    @staticmethod
    def _is_change(a, b):
        return (a is None) != (b is None) or a != b

    def _query(self):
        query = self.model.query
        try:
            query_options = self.resource.meta.query_options
        except KeyError:
            return query
        return query.options(*query_options)

    def _query_filter(self, query, expression):
        return query.filter(expression)

    def _expression_for_join(self, attribute, expression):
        relationship = getattr(self.model, attribute)
        if isinstance(relationship.impl, ScalarObjectAttributeImpl):
            return relationship.has(expression)
        else:
            return relationship.any(expression)

    def _expression_for_condition(self, condition):
        return condition.filter.expression(condition.value)

    def _expression_for_ids(self, ids):
        return self.id_column.in_(ids)

    def _or_expression(self, expressions):
        if not expressions:
            return True
        if len(expressions) == 1:
            return expressions[0]
        return or_(*expressions)

    def _and_expression(self, expressions):
        if not expressions:
            return False
        if len(expressions) == 1:
            return expressions[0]
        return and_(*expressions)

    def _query_filter_by_id(self, query, id):
        try:
            return query.filter(self.id_column == id).one()
        except NoResultFound:
            raise ItemNotFound(self.resource, id=id)

    def _query_order_by(self, query, sort=None):
        order_clauses = []

        if not sort:
            return query.order_by(self.default_sort_expression)

        for field, attribute, reverse in sort:
            column = getattr(self.model, attribute)

            if isinstance(field, fields.ToOne):
                target_alias = aliased(field.target.meta.model)
                query = query.outerjoin(target_alias, column).reset_joinpoint()
                sort_attribute = None
                if field.target.meta.sort_attribute:
                    sort_attribute, _ = field.target.meta.sort_attribute
                column = getattr(
                    target_alias,
                    sort_attribute or field.target.manager.id_attribute)

            order_clauses.append(column.desc() if reverse else column.asc())

        return query.order_by(*order_clauses)

    def _query_get_paginated_items(self, query, page, per_page):
        return query.paginate(page=page, per_page=per_page)

    def _query_get_all(self, query):
        return query.all()

    def _query_get_one(self, query):
        return query.one()

    def _query_get_first(self, query):
        try:
            return query.one()
        except NoResultFound:
            raise IndexError()

    def create(self, properties, commit=True):
        # noinspection properties
        item = self.model()

        for key, value in properties.items():
            setattr(item, key, value)

        before_create.send(self.resource, item=item)

        session = self._get_session()

        try:
            session.add(item)
            self.commit_or_flush(commit)
        except IntegrityError as e:
            session.rollback()

            if hasattr(e.orig, 'pgcode'):
                if e.orig.pgcode == "23505":  # duplicate key
                    raise DuplicateKey(detail=e.orig.diag.message_detail)

            if current_app.debug:
                raise BackendConflict(debug_info=dict(exception_message=str(e), statement=e.statement, params=e.params))
            raise BackendConflict()

        after_create.send(self.resource, item=item)
        return item

    def update(self, item, changes, commit=True):
        session = self._get_session()

        actual_changes = {
            key: value for key, value in changes.items()
            if self._is_change(get_value(key, item, None), value)
        }

        try:
            before_update.send(self.resource, item=item, changes=actual_changes)

            for key, value in changes.items():
                setattr(item, key, value)

            self.commit_or_flush(commit)
        except IntegrityError as e:
            session.rollback()

            # XXX need some better way to detect postgres engine.
            if hasattr(e.orig, 'pgcode'):
                if e.orig.pgcode == '23505':  # duplicate key
                    raise DuplicateKey(detail=e.orig.diag.message_detail)

            if current_app.debug:
                raise BackendConflict(debug_info=dict(exception_message=str(e), statement=e.statement, params=e.params))
            raise BackendConflict()

        after_update.send(self.resource, item=item, changes=actual_changes)
        return item

    def delete(self, item, commit=True):
        session = self._get_session()

        before_delete.send(self.resource, item=item)

        try:
            session.delete(item)
            self.commit_or_flush(commit)
        except IntegrityError as e:
            session.rollback()

            if current_app.debug:
                raise BackendConflict(debug_info=dict(exception_message=str(e), statement=e.statement, params=e.params))
            raise BackendConflict()

        after_delete.send(self.resource, item=item)

    def relation_instances(self, item, attribute, target_resource, page=None, per_page=None):
        query = getattr(item, attribute)

        if isinstance(query, InstrumentedList):
            if page and per_page:
                return Pagination.from_list(query, page, per_page)
            return query

        if page and per_page:
            return self._query_get_paginated_items(query, page, per_page)

        return self._query_get_all(query)

    def relation_add(self, item, attribute, target_resource, target_item):
        before_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        getattr(item, attribute).append(target_item)
        after_add_to_relation.send(self.resource, item=item, attribute=attribute, child=target_item)

    def relation_remove(self, item, attribute, target_resource, target_item):
        before_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        try:
            getattr(item, attribute).remove(target_item)
            after_remove_from_relation.send(self.resource, item=item, attribute=attribute, child=target_item)
        except ValueError:
            pass  # if the relation does not exist, do nothing

    def commit(self):
        session = self._get_session()
        session.commit()

    def commit_or_flush(self, commit):
        session = self._get_session()
        if commit:
            session.commit()
        else:
            session.flush()
