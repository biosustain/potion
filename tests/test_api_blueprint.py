from flask import Blueprint, json
from flask_potion import Api, fields
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class SampleResource(ModelResource):
    class Schema:
        name = fields.String()

    class Meta:
        name = "samples"
        model = "samples"
        manager = MemoryManager


class SampleResource2(ModelResource):
    class Meta:
        name = "samples2"
        model = "samples2"
        manager = MemoryManager


class BlueprintApiTestCase(BaseTestCase):
    def test_api_blueprint(self):
        api_bp = Blueprint("potion_blueprint", __name__.split(".")[0])
        api = Api(api_bp)
        api.add_resource(SampleResource)

        # Register Blueprint
        self.app.register_blueprint(api_bp)
        response = self.client.get("/samples")
        self.assert200(response)

    def test_api_blueprint_w_prefix(self):
        api_bp = Blueprint("potion_blueprint", __name__.split(".")[0])
        api = Api(api_bp, prefix="/api/v1")
        api.add_resource(SampleResource)

        # Register Blueprint
        self.app.register_blueprint(api_bp)
        response = self.client.get("/api/v1/samples")
        self.assert200(response)

    def test_multiple_blueprints(self):
        # Create Blueprints
        api_bp1 = Blueprint("potion1", __name__.split(".")[0])
        api_bp2 = Blueprint("potion2", __name__.split(".")[0])

        # Create Api objects, add resources, and register blueprints with app
        api1 = Api(api_bp1, prefix="/api/v1")
        api2 = Api(api_bp2, prefix="/api/v2")
        api1.add_resource(SampleResource)
        api2.add_resource(SampleResource)
        api2.add_resource(SampleResource2)
        self.app.register_blueprint(api_bp1)
        self.app.register_blueprint(api_bp2)

        # Test both endpoints
        response = self.client.get("/api/v1/samples")
        self.assert200(response)
        response = self.client.get("/api/v2/samples2")
        self.assert200(response)
        response = self.client.get("/api/v2/samples2")
        self.assert200(response)

        # Test that we have two prefix'd schemas
        response = self.client.get("/api/v1/schema")
        self.assert200(response)
        v1_schema = json.loads(response.data)
        response = self.client.get("/api/v2/schema")
        self.assert200(response)
        v2_schema = json.loads(response.data)
        assert v1_schema != v2_schema
        assert v1_schema["properties"]["samples"] == v2_schema["properties"]["samples"]

        # Test that endpoints are linked to same resource
        response = self.client.post('/api/v1/samples', data={
            "name": "to_v1"
        })
        self.assert200(response)
        response = self.client.post('/api/v2/samples', data={
            "name": "to_v2"
        })
        self.assert200(response)
        response = self.client.get("/api/v1/samples/2")
        self.assert200(response)
        response = self.client.get("/api/v2/samples/1")
        self.assert200(response)
