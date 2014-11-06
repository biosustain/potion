from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from .exceptions import DuplicateKey
from .signals import before_create, before_update, after_update, before_delete, after_delete
from flask_sqlalchemy import BaseQuery, Pagination, get_state
from werkzeug.exceptions import abort


class Manager(object):

    def __init__(self, resource, model):
        self.resource = resource
        self.model = model

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

    def index(self):
        query = self._query()
        # TODO filters
        # TODO sort
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

    def read(self, id_):
        try:
            # NOTE SQLAlchemy's .get() does not work well with .filter(), therefore using .one()
            return self._query().filter(self._id_column == id_).one()
        except NoResultFound:
            abort(404, resource=self.resource.meta.name, id=id_)

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
