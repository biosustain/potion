from unittest import TestCase
import unittest
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.resource import ModelResource, Resource
from flask_potion import Api, fields
from flask_potion.routes import ItemAttributeRoute, Relation, ItemRoute
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
                include_id = True
                include_type = True

            @ItemRoute.GET()
            def verbose_description(self, box):
                return box["description"] + " box"

            verbose_description.response_schema = fields.String()

            @ItemRoute.POST()
            def open(self, box):
                return self.manager.update(box, {"is_open": True})

            open.response_schema = fields.Inline('self', attribute='Test')

        self.api.add_resource(Box)

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
                id_field_class = fields.Integer
                include_type = True

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

    def test_simple_relation(self):

        class Person(ModelResource):
            class Schema:
                first_name = fields.String()
                last_name = fields.String()

            class Meta:
                name = 'person'
                model = name
                manager = MemoryManager
                include_id = True
                include_type = True

        self.api.add_resource(Person)

        class Group(ModelResource):
            class Schema:
                name = fields.String()

            class Meta:
                name = 'group'
                model = name
                manager = MemoryManager
                include_id = True
                include_type = True

            members = Relation('person')

        self.api.add_resource(Group)

        # self.pp(self.client.get('/group/schema').json)

        response = self.client.post('/group', data={
            "name": "Amnesiacs"
        })

        self.assert200(response)

        response = self.client.post('/person', data={
            "first_name": "Jane",
            "last_name": "Doe"
        })
        self.assert200(response)

        response = self.client.post('/person', data={
            "first_name": "John",
            "last_name": "Doe"
        })
        self.assert200(response)

        response = self.client.get('/group/1')
        self.assert200(response)

        response = self.client.get('/person/1')
        self.assert200(response)
        self.assertJSONEqual({
                                 '$id': 1,
                                 '$type': 'person',
                                 'first_name': 'Jane',
                                 'last_name': 'Doe'
                             }, response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([], response.json)

        response = self.client.post('/group/1/members', data={
            "$ref": "/person/1"
        })

        self.assertJSONEqual({
            "$ref": "/person/1"
        }, response.json)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([
                                 {
                                     "$ref": "/person/1"
                                 }
                             ], response.json)

        response = self.client.post('/group/1/members', data={
            "$ref": "/person/2"
        })
        self.assert200(response)

        response = self.client.delete('/group/1/members/1')
        self.assertStatus(response, 204)

        response = self.client.get('/group/1/members')
        self.assert200(response)
        self.assertJSONEqual([
                                 {
                                     "$ref": "/person/2"
                                 }
                             ], response.json)

    def test_attribute_route(self):

        class IngredientResource(ModelResource):
            class Meta:
                name = "ingredient"
                model = name
                manager = MemoryManager
                id_field_class = fields.Integer
                include_type = True

            class Schema:
                name = fields.String()

        self.api.add_resource(IngredientResource)

        class DrinkResource(ModelResource):
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
                model = name
                manager = MemoryManager
                id_field_class = fields.Integer
                include_type = True

            class Schema:
                name = fields.String()
                # collection = fields.ToOne("collection")
                # author = fields.ToOne("user")

        self.api.add_resource(DrinkResource)

        response = self.client.post("/drink", data={
            "name": "Gin & tonic"
        })

        self.assert200(response)

        response = self.client.post("/ingredient", data={
            "name": "gin"
        })

        response = self.client.post("/ingredient", data={
            "name": "tonic water"
        })

        response = self.client.post("/drink/1/recipe", data=[
            {
                "ingredient": {"$ref": "/ingredient/1"},
                "volume": 0.6
            },
            {
                "ingredient": {"$ref": "/ingredient/2"},
                "volume": 0.4
            }
        ])

        self.assert200(response)
        self.assertJSONEqual([{'ingredient': {'$ref': '/ingredient/1'}, 'volume': 0.6},
                              {'ingredient': {'$ref': '/ingredient/2'}, 'volume': 0.4}], response.json)


        response = self.client.get("/drink/1/recipe")
        self.assert200(response)
        self.assertJSONEqual([{'ingredient': {'$ref': '/ingredient/1'}, 'volume': 0.6},
                              {'ingredient': {'$ref': '/ingredient/2'}, 'volume': 0.4}], response.json)


    # def test_attribute_set_route
    # def test_attribute_map_route