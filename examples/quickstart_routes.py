import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_potion.routes import ItemRoute, Route
from flask_potion import Api, ModelResource, fields

app = Flask(__name__)
db = SQLAlchemy(app)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)
    rating = db.Column(db.Integer, default=5)

db.create_all()


class BookResource(ModelResource):
    class Meta:
        model = Book
        exclude_fields = ['rating']

    @ItemRoute.GET('/rating')
    def rating(self, book) -> fields.Integer():
        return book.rating

    @rating.POST
    def rate(self, book, value: fields.Integer(minimum=1, maximum=10)) -> fields.Integer():
        self.manager.update(book, {"rating": value})
        return value

    @ItemRoute.GET()
    def is_recent(self, book) -> fields.Boolean():
        return datetime.date.today().year <= book.year_published + 10

    @Route.GET
    def genres(self) -> fields.List(fields.String, description="A list of genres"):
        return ['biography', 'history', 'essay', 'law', 'philosophy']


api = Api(app)
api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()

# Example use:
# $ http :5000/book title=Foo year_published:=1990
# HTTP/1.0 200 OK
# Content-Length: 72
# Content-Type: application/json
# Date: Sat, 07 Feb 2015 13:43:02 GMT
# Server: Werkzeug/0.9.6 Python/3.3.2
#
# {
#     "$uri": "/book/1",
#     "rating": 2,
#     "title": "Foo",
#     "year_published": 1990
# }
#
# $ http GET :5000/book/1/rating
# HTTP/1.0 200 OK
# Content-Length: 3
# Content-Type: application/json
# Date: Sat, 07 Feb 2015 13:43:06 GMT
# Server: Werkzeug/0.9.6 Python/3.3.2
#
# 2.5
#
# $ http POST :5000/book/1/rating value:=4
# HTTP/1.0 200 OK
# Content-Length: 3
# Content-Type: application/json
# Date: Sat, 07 Feb 2015 13:43:09 GMT
# Server: Werkzeug/0.9.6 Python/3.3.2
#
# 4.0
#
# $ http GET :5000/book/1/is-recent
# HTTP/1.0 200 OK
# Content-Length: 5
# Content-Type: application/json
# Date: Sat, 07 Feb 2015 13:43:18 GMT
# Server: Werkzeug/0.9.6 Python/3.3.2
#
# false
#
# $ http GET :5000/book/genres
# HTTP/1.0 200 OK
# Content-Length: 54
# Content-Type: application/json
# Date: Sat, 07 Feb 2015 13:43:31 GMT
# Server: Werkzeug/0.9.6 Python/3.3.2
#
# [
#     "biography",
#     "history",
#     "essay",
#     "law",
#     "philosophy"
# ]



