from flask_potion.fields import Object


class InlineModel(Object):
    """
    :param dict properties:
    :param model:
    """
    def __init__(self, properties, model, **kwargs):
        super(InlineModel, self).__init__(properties, **kwargs)
        self.model = model

    def converter(self, instance):
        instance = super(InlineModel, self).converter(instance)
        if instance is not None:
            instance = self.model(**instance)
        return instance
