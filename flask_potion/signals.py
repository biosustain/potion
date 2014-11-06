from blinker import Namespace

_potion = Namespace()

before_create = _potion.signal('before-create')

after_create = _potion.signal('after-create')

before_update = _potion.signal('before-update')

after_update = _potion.signal('after-update')

before_delete = _potion.signal('before-delete')

after_delete = _potion.signal('after-delete')

before_add_to_relationship = _potion.signal('before-add-to-relationship')

after_add_to_relationship = _potion.signal('after-add-to-relationship')

before_remove_from_relationship = _potion.signal('before-remove-from-relationship')

after_remove_from_relationship = _potion.signal('after-remove-from-relationship')