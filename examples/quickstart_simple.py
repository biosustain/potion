from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_potion import Api, ModelResource, fields

app = Flask(__name__)
db = SQLAlchemy(app)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)

db.create_all()

class BookResource(ModelResource):
    class Meta:
        model = Book

    class Schema:
        year_published = fields.Integer(minimum=1400)
    
BookResource.schema.set('$id', fields.Integer(attribute='id', nullable=True))


api = Api(app)
api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()