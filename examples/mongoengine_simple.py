from flask import Flask
from flask_mongoengine import MongoEngine
from mongoengine import StringField, IntField

from flask_potion import Api, ModelResource, fields
from flask_potion.backends.mongoengine import MongoEngineManager

app = Flask(__name__)
app.debug = True
app.config['MONGODB_DB'] = 'potion-example'

me = MongoEngine(app)

class Book(me.Document):
    title = StringField(null=False, unique=True)
    year_published = IntField(null=True)


class BookResource(ModelResource):
    class Meta:
        name = 'book'
        model = Book

    class Schema:
        year_published = fields.Integer(minimum=1400)


api = Api(app, default_manager=MongoEngineManager)
api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()
