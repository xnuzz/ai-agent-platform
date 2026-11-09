from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import ROLE_RANK, Role
from apps.common.exceptions import Conflict
from apps.common.permissions import has_role
from apps.common.workspace import WorkspaceScopedMixin

from .models import Membership, User, Workspace
from .serializers import MembershipSerializer, RegisterSerializer, UserSerializer, WorkspaceSerializer


class RegisterView(generics.CreateAPIView):
    """Create a user plus their first workspace (user becomes OWNER)."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(responses={201: UserSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class WorkspaceViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Workspaces the current user belongs to. Not scoped by X-Workspace-ID."""

    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]
    queryset = Workspace.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Workspace.objects.none()
        return (
            Workspace.objects.filter(memberships__user=self.request.user, is_active=True)
            .prefetch_related("memberships")
            .distinct()
            .order_by("name")
        )

    @transaction.atomic
    def perform_create(self, serializer):
        ws = serializer.save(created_by=self.request.user)
        Membership.objects.create(user=self.request.user, workspace=ws, role=Role.OWNER)
        record("workspace.created", workspace=ws, actor=Actor.for_user(self.request.user), target=ws)

    def perform_update(self, serializer):
        ws = serializer.instance
        m = ws.memberships.filter(user=self.request.user).first()
        if not has_role(m, Role.ADMIN):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Only workspace admins can change workspace settings.")
        serializer.save()
        record("workspace.updated", workspace=ws, actor=Actor.for_user(self.request.user), target=ws,
               metadata={"fields": sorted(serializer.validated_data.keys())})


class MembershipViewSet(
    WorkspaceScopedMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """Members of the current workspace. Writes require ADMIN."""

    serializer_class = MembershipSerializer
    queryset = Membership.objects.select_related("user")
    write_role = Role.ADMIN
    http_method_names = ["get", "post", "patch", "delete"]

    def perform_create(self, serializer):
        email = serializer.validated_data.pop("email").lower()
        user = User.objects.filter(email=email).first()
        if user is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"email": ["No user with this email. Invitations are not implemented yet."]})
        if Membership.objects.filter(user=user, workspace=self.request.workspace).exists():
            raise Conflict("User is already a member.")
        self._guard_role(serializer.validated_data.get("role", Role.DEVELOPER))
        m = serializer.save(user=user, workspace=self.request.workspace)
        record("membership.created", workspace=self.request.workspace, actor=Actor.for_user(self.request.user),
               target=m, metadata={"role": m.role, "user_id": str(user.id)})

    def perform_update(self, serializer):
        self._guard_role(serializer.validated_data.get("role", serializer.instance.role))
        self._guard_last_owner(serializer.instance, serializer.validated_data.get("role"))
        m = serializer.save()
        record("membership.updated", workspace=self.request.workspace, actor=Actor.for_user(self.request.user),
               target=m, metadata={"role": m.role})

    def perform_destroy(self, instance):
        self._guard_last_owner(instance, None)
        record("membership.deleted", workspace=self.request.workspace, actor=Actor.for_user(self.request.user),
               target=instance, metadata={"user_id": str(instance.user_id)})
        instance.delete()

    def _guard_role(self, role):
        # Admins cannot grant a role above their own.
        if ROLE_RANK[role] > ROLE_RANK[self.request.membership.role]:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Cannot grant a role higher than your own.")

    def _guard_last_owner(self, membership, new_role):
        if membership.role == Role.OWNER and new_role != Role.OWNER:
            owners = Membership.objects.filter(workspace=membership.workspace, role=Role.OWNER).count()
            if owners <= 1:
                raise Conflict("A workspace must keep at least one OWNER.")
