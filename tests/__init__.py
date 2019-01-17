from pprint import pformat

from flask import json, Flask
from flask.testing import FlaskClient
from flask_testing import TestCase
import sqlalchemy


class ApiClient(FlaskClient):
    def open(self, *args, **kw):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        headers = kw.pop('headers', [])

        if 'data' in kw and (kw.pop('force_json', False) or not isinstance(kw['data'], str)):
            kw['data'] = json.dumps(kw['data'])
            kw['content_type'] = 'application/json'

        return super(ApiClient, self).open(*args, headers=headers, **kw)


class BaseTestCase(TestCase):

    def assertJSONEqual(self, first, second, msg=None):
        self.assertEqual(json.loads(json.dumps(first)), json.loads(json.dumps(second)), msg)

    def _without(self, dct, without):
        return {k: v for k, v in dct.items() if k not in without}

    def assertEqualWithout(self, first, second, without, msg=None):
        if isinstance(first, list) and isinstance(second, list):
            self.assertEqual(
                [self._without(v, without) for v in first],
                [self._without(v, without) for v in second],
                msg=msg
            )
        elif isinstance(first, dict) and isinstance(second, dict):
            self.assertEqual(self._without(first, without),
                             self._without(second, without),
                             msg=msg)
        else:
            self.maxDiff = None
            self.assertEqual(first, second)

    def create_app(self):
        app = Flask(__name__)
        app.secret_key = 'XXX'
        app.test_client_class = ApiClient
        app.debug = True
        return app

    def pp(self, obj):
        print(json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': ')))


class DBQueryCounter:
    """
    Use as a context manager to count the number of execute()'s performed
    against the given sqlalchemy connection.
    Usage:
        with DBQueryCounter(db.session) as ctr:
            db.session.execute("SELECT 1")
            db.session.execute("SELECT 1")
        ctr.assert_count(2)
    """

    def __init__(self, session, reset=True):
        self.session = session
        self.reset = reset
        self.statements = []

    def __enter__(self):
        if self.reset:
            self.session.expire_all()
        sqlalchemy.event.listen(
            self.session.get_bind(), 'after_execute', self._callback
        )
        return self

    def __exit__(self, *_):
        sqlalchemy.event.remove(
            self.session.get_bind(), 'after_execute', self._callback
        )

    def get_count(self):
        return len(self.statements)

    def _callback(self, conn, clause_element, multiparams, params, result):
        self.statements.append((clause_element, multiparams, params))

    def display_all(self):
        for clause, multiparams, params in self.statements:
            print(pformat(str(clause)), multiparams, params)
            print('\n')
        count = self.get_count()
        return 'Counted: {count}'.format(count=count)

    def assert_count(self, expected):
        count = self.get_count()
        assert count == expected, self.display_all()
