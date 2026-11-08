import uuid

from rest_framework.permissions import IsAuthenticated

from .exceptions import WorkspaceRequired
from .permissions import WorkspaceRolePermission

WORKSPACE_HEADER = "HTTP_X_WORKSPACE_ID"


def resolve_membership(request):
    from apps.accounts.models import Membership

    raw = request.META.get(WORKSPACE_HEADER, "")
    try:
        ws_id = uuid.UUID(raw)
    except (ValueError, TypeError):
        raise WorkspaceRequired()
    membership = (
        Membership.objects.select_related("workspace")
        .filter(user=request.user, workspace_id=ws_id, workspace__is_active=True)
        .first()
    )
    if membership is None:
        raise WorkspaceRequired()
    return membership


class WorkspaceScopedMixin:
    """Scopes a DRF view to the workspace in the X-Workspace-ID header.

    Sets request.workspace / request.membership and filters querysets by workspace.
    """

    permission_classes = [IsAuthenticated, WorkspaceRolePermission]

    def initial(self, request, *args, **kwargs):
        self.perform_authentication(request)
        if request.user and request.user.is_authenticated:
            request.membership = resolve_membership(request)
            request.workspace = request.membership.workspace
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return super().get_queryset().none()
        return super().get_queryset().filter(workspace=self.request.workspace)
