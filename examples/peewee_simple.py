
from flask import Flask
from peewee import CharField, IntegerField
from playhouse.flask_utils import FlaskDB

from flask_potion import Api, ModelResource, fields
from flask.ext.potion.contrib.peewee.manager import PeeweeManager


class DB(FlaskDB):
    def connect_db(self):
        super(DB, self).connect_db()
        if not Book.table_exists():
            Book.create_table()

    def close_db(self, exc):
        # This is only necessary for a sqlite :memory: databases to prevent the
        # database from being destroyed after each request.
        pass

app = Flask(__name__)
app.debug = True
app.config['DATABASE'] = 'sqlite://'

db = DB(app)


class Book(db.Model):
    title = CharField(null=True, unique=True)
    year_published = IntegerField()


class BookResource(ModelResource):
    class Meta:
        name = 'book'
        model = Book

    class Schema:
        year_published = fields.Integer(minimum=1400)


api = Api(app, default_manager=PeeweeManager)
api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()
