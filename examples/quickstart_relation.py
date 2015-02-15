from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import backref
from flask_potion.routes import Relation
from flask_potion import ModelResource, fields, Api

app = Flask(__name__)
db = SQLAlchemy(app)


class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(), nullable=False)
    last_name = db.Column(db.String(), nullable=False)

    __table_args__ = (
        UniqueConstraint('first_name', 'last_name'),
    )


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey(Author.id), nullable=False)

    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)

    author = db.relationship(Author, backref=backref('books', lazy='dynamic'))


db.create_all()


class BookResource(ModelResource):
    class Meta:
        model = Book

    class Schema:
        author = fields.ToOne('author')


class AuthorResource(ModelResource):
    books = Relation('book')

    class Meta:
        model = Author
        natural_key = ('first_name', 'last_name')


api = Api(app)
api.add_resource(BookResource)
api.add_resource(AuthorResource)

if __name__ == '__main__':
    app.run()