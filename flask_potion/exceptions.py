from werkzeug.exceptions import Conflict, BadRequest, NotFound


class ItemNotFound(NotFound):

    def __init__(self, resource, natural_key=None, id=None):
        NotFound.__init__()


class ValidationError(BadRequest):

    def __init__(self, ve, path=None):
        BadRequest.__init__(self)
        self.ve = ve
    # raise PotionValidationError(
    #     schema=ve.schema,
    #     validator=ve.validator,
    #     validator_value=ve.validator_value,
    #     instance=ve.instance,
    #     path='#/' + '/'.join(map(six.text_type, ve.absolute_path))
    # ) # expected <validator>: <validator_value> at <path>; instance: <instance>
    #

class DuplicateKey(Conflict):
    def __init__(self, **kwargs):
        Conflict.__init__(self)
        self.data = kwargs


class PageNotFound(NotFound):
    pass