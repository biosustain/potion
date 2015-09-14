from flask import Flask
from os.path import isfile
from peewee import Model, CharField, IntegerField, SqliteDatabase
from flask_potion.backends.peewee import PeeweeManager
from flask_potion import Api, ModelResource, fields

app = Flask(__name__)
app.debug = True

pw = SqliteDatabase('peewee-simple.db')


class Book(Model):
    title = CharField(null=True, unique=True)
    year_published = IntegerField()

    class Meta:
        database = pw


class BookResource(ModelResource):
    class Meta:
        name = 'book'
        model = Book

    class Schema:
        year_published = fields.Integer(minimum=1400)


api = Api(app, default_manager=PeeweeManager)
api.add_resource(BookResource)

if not isfile('peewee-simple.db'):
    pw.connect()
    pw.create_tables([Book])

if __name__ == '__main__':
    app.run()
