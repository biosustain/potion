import unittest

from werkzeug.exceptions import Forbidden

from flask_potion.exceptions import DuplicateKey
from flask_potion.routes import Route
from flask_potion import Api, Resource
from tests import BaseTestCase


class ErrorMessagesTestCase(BaseTestCase):
    def setUp(self):
        super(ErrorMessagesTestCase, self).setUp()
        self.api = Api(self.app, prefix='/prefix')

        class ErrorResource(Resource):
            @Route.GET
            def forbidden(self):
                raise Forbidden()

            @Route.GET
            def python_exception(self):
                raise ValueError()

            @Route.GET
            def duplicate_key(self):
                raise DuplicateKey()

            class Meta:
                name = 'error'

        self.api.add_resource(ErrorResource)

    def test_werkzeug_exception(self):
        response = self.client.get('/prefix/error/forbidden')
        self.assert403(response)
        self.assertEqual({
            "message": "You don't have the permission to access the requested resource. "
                       "It is either read-protected or not readable by the server.",
            "status": 403
        }, response.json)

    def test_potion_exception(self):
        response = self.client.get('/prefix/error/duplicate-key')
        self.assertStatus(response, 409)
        self.assertEqual({
            "message": "Conflict",
            "status": 409
        }, response.json)

    def test_not_found_exception(self):
        response = self.client.get('/prefix/error/missing')
        self.assert404(response)
        self.assertEqual({
            "message": "The requested URL was not found on the server.  If you entered "
                        "the URL manually please check your spelling and try again.",
            "status": 404
        }, response.json)

    def test_exception_outside_api(self):
        response = self.client.get('/missing')
        self.assert404(response)

    @unittest.SkipTest
    def test_python_exception(self):
        response = self.client.get('/prefix/error/python-exception')
        self.assert500(response)
        self.assertEqual({}, response.json)
