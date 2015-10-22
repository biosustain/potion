from flask import Flask
from flask_potion import Api, Resource, fields
from flask_potion.routes import Route

app = Flask(__name__)
app.debug = True


class LogResource(Resource):
    class Schema:
        level = fields.String(enum=['info', 'warning', 'error'])
        message = fields.String()

    class Meta:
        name = 'log'

    @Route.POST('',
                rel="create",
                schema=fields.Inline('self'),
                response_schema=fields.Inline('self'))
    def create(self, properties):
        print('{level}: {message}'.format(**properties))
        return properties

api = Api(app)
api.add_resource(LogResource)

if __name__ == '__main__':
    app.run()