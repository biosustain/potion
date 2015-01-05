from flask import json, Flask
from flask.testing import FlaskClient
from flask_testing import TestCase


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

    def create_app(self):
        app = Flask(__name__)
        app.secret_key = 'XXX'
        app.test_client_class = ApiClient
        app.debug = True
        return app

    def pp(self, obj):
        print(json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': ')))