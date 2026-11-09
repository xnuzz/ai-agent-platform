from dataclasses import dataclass

from .enums import ActorType


@dataclass(frozen=True)
class Actor:
    """Who performed an action. Used for audit + authorization decisions in services."""

    type: str
    user: object | None = None
    agent: str = ""  # AgentType value
    agent_token_id: str = ""

    @classmethod
    def system(cls) -> "Actor":
        return cls(ActorType.SYSTEM)

    @classmethod
    def for_user(cls, user) -> "Actor":
        return cls(ActorType.USER, user=user)

    @classmethod
    def for_agent_token(cls, token) -> "Actor":
        return cls(ActorType.AGENT, agent=token.agent, agent_token_id=str(token.id))

    @classmethod
    def from_request(cls, request) -> "Actor":
        from apps.orchestration.models import AgentToken

        if isinstance(getattr(request, "auth", None), AgentToken):
            return cls.for_agent_token(request.auth)
        return cls.for_user(request.user)

    @property
    def is_user(self) -> bool:
        return self.type == ActorType.USER
