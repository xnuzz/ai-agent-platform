from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions

from .models import AgentToken


class AgentPrincipal:
    """request.user for agent-authenticated requests. Never a Django User -> cannot hit user endpoints."""

    is_authenticated = True
    is_anonymous = False
    is_staff = False
    is_superuser = False

    def __init__(self, token: AgentToken):
        self.token = token
        self.agent = token.agent
        self.pk = self.id = None

    def __str__(self):
        return f"agent:{self.agent}"


class AgentTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Agent"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header:
            return None
        parts = header.split()
        if parts[0] != self.keyword:
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid Agent authorization header.")
        token = AgentToken.lookup(parts[1])
        if token is None:
            raise exceptions.AuthenticationFailed("Invalid or revoked agent token.")
        now = timezone.now()
        if not token.last_used_at or (now - token.last_used_at).total_seconds() > 60:
            AgentToken.objects.filter(pk=token.pk).update(last_used_at=now)
        return AgentPrincipal(token), token

    def authenticate_header(self, request):
        return self.keyword


class AgentTokenScheme(OpenApiAuthenticationExtension):
    target_class = "apps.orchestration.authentication.AgentTokenAuthentication"
    name = "AgentToken"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "header", "name": "Authorization",
                "description": "Format: `Agent agt_<prefix>_<secret>`"}
