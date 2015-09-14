from playhouse.flask_utils import FlaskDB

__author__ = 'lays'


class PeeweeTestDB(FlaskDB):
    def connect_db(self):
        pass

    def close_db(self, exc):
        pass