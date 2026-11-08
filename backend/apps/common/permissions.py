from rest_framework.permissions import SAFE_METHODS, BasePermission

from .enums import ROLE_RANK, Role


def has_role(membership, minimum: str) -> bool:
    return membership is not None and ROLE_RANK[membership.role] >= ROLE_RANK[minimum]


class WorkspaceRolePermission(BasePermission):
    """Read: VIEWER+. Write: view.write_role (default DEVELOPER).

    Requires the view to be a WorkspaceScopedMixin (sets request.membership).
    Per-action overrides: view.action_roles = {"decide": Role.DEVELOPER}.
    """

    message = "Your workspace role does not allow this action."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        action_roles = getattr(view, "action_roles", {})
        action = getattr(view, "action", None)
        if action in action_roles:
            return has_role(membership, action_roles[action])
        if request.method in SAFE_METHODS:
            return has_role(membership, Role.VIEWER)
        return has_role(membership, getattr(view, "write_role", Role.DEVELOPER))
