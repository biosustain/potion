from unittest import TestCase
import unittest
from flask_potion.backends.memory import MemoryManager
from flask_potion.resource import ModelResource, Resource
from flask_potion import Api, fields
from flask_potion.routes import ItemAttributeRoute, RelationRoute, ItemRoute
from tests import BaseTestCase


class RelationTestCase(BaseTestCase):

    def setUp(self):
        super(RelationTestCase, self).setUp()
        self.api = Api(self.app)

    def test_item_route(self):

        class Box(ModelResource):

            class Schema:
                description = fields.String()
                is_open = fields.Boolean(default=False)

            class Meta:
                model = 'box'
                manager = MemoryManager

            @ItemRoute.GET()
            def verbose_description(self, box):
                return box["description"] + " box"

            verbose_description.response_schema = fields.String()

            @ItemRoute.POST()
            def open(self, box):
                return self.manager.update(box, {"is_open": True})

            open.response_schema = fields.Inline('self', attribute='Test')

        self.api.add_resource(Box)

        print(Box.routes)
        print(Box.routes['open'].rule_factory(Box))
        print(Box.routes['open'].rule_factory(Box, True))

        response = self.client.post('/box', data={"description": "mysterious"})

        self.assert200(response)

        response = self.client.get('/box/1/verbose-description')
        self.assertEqual("mysterious box", response.json)

        response = self.client.post('/box/1/open')

        self.assert200(response)
        self.assertEqual({
            "$id": 1,
            "$type": "box",
            "description": "mysterious",
            "is_open": True
        }, response.json)

    @unittest.SkipTest
    def test_item_attribute_route(self):
        class Recipe(ModelResource):
            class Schema:
                name = fields.String()

            class Meta:
                model = 'recipe'
                manager = MemoryManager

            ingredients = ItemAttributeRoute(
                fields.Array(
                    fields.Object({
                        "ingredient": fields.String(),
                        "amount": fields.String()
                    }))
            )

        self.api.add_resource(Recipe)

        response = self.client.post('/recipe', {
            "name": "spam soup"
        })

        self.assertEqual({
            "$id": 1,
            "$type": "recipe",
            "name": "spam soup"
        }, response.json)

        response = self.client.get('/recipe/1/ingredients')
        self.assertEqual([], response.json)

        response = self.client.post('/recipe/1/ingredients', data={
            "name": "pepper",
            "amount": "50% by volume"
        })

        self.assert200(response)

        response = self.client.get('/recipe/1/ingredients')
        self.assertEqual([{
            "name": "pepper",
            "amount": "50% by volume"
        }], response.json)



    # def test_simple_relation(self):
    #
    #     class Group(Resource):
    #         class Schema:
    #             name = fields.String()
    #
    #         class Meta:
    #             name = 'group'
    #             model = name
    #             manager = MemoryManager
    #
    #         members = RelationRoute('person')
    #
    #
    #     class Person(Resource):
    #
    #         class Schema:
    #             first_name = fields.String()
    #             last_name = fields.String()
    #
    #         class Meta:
    #             name = 'person'
    #             manager = MemoryManager
    #
    #
    #
    #
    #


#
#     def __init__(self):
#         pass
#
#
#     def test_one_to_many(self):
#         request = [
#             {"$ref": "/drink/1"},
#             {"$ref": "/drink/2"},
#             {"$ref": "/drink/3"},
#             {"$ref": "/drink/4"},
#         ]
#
#     def test_many_to_many(self):
#         pass
#
#     def test_inline_references(self):
#         request = {
#             "$id": 1,
#             "$uri": "/drink/1",
#             "name": "Lemonade",
#             "collection": None,
#             "author": {"$ref": "/user/1"},
#             "recipe": [
#                 {
#                     "ingredient": {"$ref": "/ingredient/1"},
#                     "volume": 10.0
#                 },
#                 {
#                     "ingredient": "water",
#                     "volume": 85.0
#                 },
#                 {
#                     "ingredient": 3,
#                     "volume": 5.0
#                 }
#             ]
#         }
#
#     def test_item_route(self):
#
#
#         class DrinkResource(ModelResource):
#
#             recipe = ItemAttributeRoute(
#                 fields.Array(
#                     fields.Object(properties={
#                         "ingredient": fields.ToOne("ingredient"),
#                         "volume": fields.Number()
#                     })
#                 )
#             )
#
#             class Meta:
#                 name = "drink"
#
#             class Schema:
#                 name = fields.String()
#                 collection = fields.ToOne("collection")
#                 author = fields.ToOne("user")
#
#
#         pass
#
#
#     def test_relationship(self):
#
#         # class ProjectResource(ModelResource):
#         #     tasks = Instances('tasks')
#
#             # class Meta:
#             #     model = Project
#
#         class TaskResource(ModelResource):
#             # class Meta:
#             #     model = Task
#
#             class Schema:
#                 project = fields.RefOne('project')
#                 status = fields.String(enum=('open', 'closed'))
#
