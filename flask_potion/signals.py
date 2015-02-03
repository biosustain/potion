from flask.signals import Namespace

_potion = Namespace()

before_create = _potion.signal('before-create')

after_create = _potion.signal('after-create')

before_update = _potion.signal('before-update')

after_update = _potion.signal('after-update')

before_delete = _potion.signal('before-delete')

after_delete = _potion.signal('after-delete')

before_add_to_relation = _potion.signal('before-add-to-relation')

after_add_to_relation = _potion.signal('after-add-to-relation')

before_remove_from_relation = _potion.signal('before-remove-from-relation')

after_remove_from_relation = _potion.signal('after-remove-from-relation')