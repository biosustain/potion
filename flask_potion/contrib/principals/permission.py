from flask import g
from flask_principal import Permission
from sqlalchemy import or_

from .needs import HybridNeed


class HybridPermission(Permission):
    """
    Hybrid :class:`flask_principal.Permission` that evaluates both regular and hybrid needs.
    """
    def __init__(self, *needs):
        super(HybridPermission, self).__init__(*needs)
        self.hybrid_needs = set()
        self.standard_needs = set()

        for need in needs:
            if isinstance(need, HybridNeed):
                self.hybrid_needs.add(need)
            else:
                self.standard_needs.add(need)

    def allows(self, identity):
        """
        Determines whether a given identity meets this permission.

        :param flask_principal.Identity identity: An identity with a set of provided *needs*
        """
        if self.standard_needs and not self.standard_needs.intersection(identity.provides):
            return False

        # TODO support standard needs for excludes
        if self.excludes and self.excludes.intersection(identity.provides):
            return False

        if self.needs and not self.standard_needs:
            return False

        return True

    def can(self, item=None):
        """
        Depending on whether or not ``item`` is given, this function either:

        - evaluates all regular needs needs
        - also evaluates the hybrid needs against the item

        If any of the needs are met, the function returns ``True``.

        :param item: SQLAlchemy model instance
        """
        if not item:
            return self.require().can()
        else:
            if self.require().can():
                return True

            for need in self.hybrid_needs:
                resolved_need = need(item)
                if resolved_need in g.identity.provides:
                    return True
        return False
