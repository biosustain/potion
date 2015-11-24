from flask import Blueprint
from flask_potion import Api
from flask_potion.contrib.memory.manager import MemoryManager
from flask_potion.resource import ModelResource
from tests import BaseTestCase


class BlueprintApiTestCase(BaseTestCase):
    def test_api_blueprint(self):
        class SampleResource(ModelResource):
            class Meta:
                name = "samples"
                model = "samples"
                manager = MemoryManager

        api_bp = Blueprint("potion_blueprint", __name__.split(".")[0])
        api = Api(api_bp)
        api.add_resource(SampleResource)

        # Register Blueprint
        self.app.register_blueprint(api_bp)
        response = self.client.get("/samples")
        self.assert200(response)
