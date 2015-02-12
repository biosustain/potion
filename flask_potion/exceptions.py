from flask import jsonify, current_app
from werkzeug.exceptions import Conflict, BadRequest, NotFound, InternalServerError, UnsupportedMediaType
from werkzeug.http import HTTP_STATUS_CODES


class PotionException(Exception):
    http_exception = InternalServerError

    @property
    def status_code(self):
        return self.http_exception.code

    def as_dict(self):
        return {
            'status': self.status_code,
            'message': HTTP_STATUS_CODES.get(self.status_code, '')
        }

    def make_response(self):
        code = self.http_exception.code
        response = jsonify(self.as_dict())
        response.status_code = self.status_code
        return response


class ItemNotFound(PotionException):
    http_exception = NotFound

    def __init__(self, resource, natural_key=None, id=None):
        super(ItemNotFound, self).__init__()
        self.resource = resource
        self.id = id
        self.natural_key = natural_key

    def as_dict(self):
        dct = super(ItemNotFound, self).as_dict()

        if self.id is not None:
            dct['item'] = {
                "$type": self.resource.meta.name,
                "$id": self.id
            }
        return dct

    def make_response(self):
        code = self.http_exception.code
        response = jsonify(self.as_dict())
        response.status_code = self.status_code
        return response


class RequestMustBeJSON(PotionException):
    http_exception = UnsupportedMediaType


class ValidationError(PotionException):
    http_exception = BadRequest

    def __init__(self, errors, root=None, schema_uri='#'):
        self.root = root
        self.errors = errors
        self.schema_uri = schema_uri

    def _complete_path(self, error):
        path = tuple(error.absolute_path)
        if self.root is not None:
            return (self.root, ) + path
        return path

    def _format_errors(self):
        for error in self.errors:
            error_data = {
                'validationOf': {error.validator: error.validator_value},
                "path": self._complete_path(error)
            }

            if current_app.debug:
                error_data['message'] = error.message
            yield error_data

    def as_dict(self):
        dct = super(ValidationError, self).as_dict()
        dct['errors'] = list(self._format_errors())
        return dct


class DuplicateKey(PotionException):
    http_exception = Conflict

    def __init__(self, **kwargs):
        self.data = kwargs


class BackendConflict(PotionException):
    http_exception = Conflict

    def __init__(self, **kwargs):
        self.data = kwargs

    def as_dict(self):
        dct = super(BackendConflict, self).as_dict()
        dct.update(self.data)
        return dct

class PageNotFound(PotionException):
    http_exception = NotFound


class InvalidJSON(PotionException):
    http_exception = BadRequest
