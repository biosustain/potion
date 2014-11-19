from unittest import TestCase
from flask.ext.potion.filter import Instances
from flask_potion import Potion, fields
from flask_potion.routes import ItemAttributeRoute
from potion.client import Resource


class RelationshipTestCase(TestCase):

    def __init__(self):
        pass


    def test_one_to_many(self):
        request = [
            {"$ref": "/drink/1"},
            {"$ref": "/drink/2"},
            {"$ref": "/drink/3"},
            {"$ref": "/drink/4"},
        ]

    def test_many_to_many(self):
        pass

    def test_inline_references(self):
        request = {
            "$id": 1,
            "$uri": "/drink/1",
            "name": "Lemonade",
            "collection": None,
            "author": {"$ref": "/user/1"},
            "recipe": [
                {
                    "ingredient": {"$ref": "/ingredient/1"},
                    "volume": 10.0
                },
                {
                    "ingredient": "water",
                    "volume": 85.0
                },
                {
                    "ingredient": 3,
                    "volume": 5.0
                }
            ]
        }

    def test_item_route(self):

        potion = Potion()

        class DrinkResource(potion.Resource):

            recipe = ItemAttributeRoute(
                fields.Array(
                    fields.Object(properties={
                        "ingredient": fields.ToOne("ingredient"),
                        "volume": fields.Number()
                    })
                )
            )

            class Meta:
                name = "drink"

            class Schema:
                name = fields.String()
                collection = fields.ToOne("collection")
                author = fields.ToOne("user")


        pass


    def test_relationship(self):

        potion = Potion()

        class ProjectResource(potion.Resource):
            tasks = Instances('tasks')

            # class Meta:
            #     model = Project


        class TaskResource(potion.Resource):
            # class Meta:
            #     model = Task

            class Schema:
                project = fields.RefOne('project')
                status = fields.String(enum=('open', 'closed'))

