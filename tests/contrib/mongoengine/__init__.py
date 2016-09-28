from flask_mongoengine import MongoEngine
from pymongo.database import Database

from flask_potion import Api
from flask_potion.contrib.mongoengine import MongoEngineManager
from tests import BaseTestCase


class MongoEngineTestCase(BaseTestCase):
    def setUp(self):
        super(MongoEngineTestCase, self).setUp()
        self.app.config['MONGODB_DB'] = 'potion-test-db'
        self.api = Api(self.app, default_manager=MongoEngineManager)
        self.me = me = MongoEngine(self.app)

    def tearDown(self):
        connection_or_db = self.me.connection

        # MongoEngine.connection value changed in flask-mongoengine 0.8
        if isinstance(connection_or_db, Database):
            connection_or_db.client.drop_database(connection_or_db)
        else:
            connection_or_db.drop_database('potion-test-db')
