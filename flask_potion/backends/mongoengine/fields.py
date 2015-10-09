from bson import ObjectId
from flask_potion import fields

# TODO: more elaborate field that validates and returns ObjectId
class ObjectIdField(fields.String):
    def formatter(self, value):
        if isinstance(value, ObjectId):
            return str(value)
        else:
            return value