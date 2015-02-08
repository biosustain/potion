from flask import Flask
from flask_potion.routes import Route
from flask_potion import Api, Resource, fields

app = Flask(__name__)


api = Api(app)
api.add_resource(Resource)

class SimpleResource(Resource):
    class Meta:
        name = 'simple'

    class Schema:
        name = fields.String()
        value = fields.Number()

    @Route.POST
    def create(self, value: fields.Number()) -> fields.Inline('self'):
        return {"name": "foo", "value": value}

api.add_resource(SimpleResource)

if __name__ == '__main__':
    app.run()