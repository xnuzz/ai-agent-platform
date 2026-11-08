from apps.common.actor import Actor

from .models import AuditEvent


def _target_type(target) -> str:
    return getattr(target, "AUDIT_TYPE", None) or type(target).__name__


def record(action: str, *, workspace, actor: Actor, target=None, metadata: dict | None = None,
           request=None) -> AuditEvent:
    ip = None
    if request is not None:
        ip = request.META.get("REMOTE_ADDR")
    return AuditEvent.objects.create(
        workspace=workspace,
        actor_type=actor.type,
        actor_user=actor.user if actor.user is not None and getattr(actor.user, "pk", None) else None,
        actor_agent=actor.agent,
        action=action,
        target_type=_target_type(target) if target is not None else "",
        target_id=getattr(target, "pk", None) if target is not None else None,
        metadata=metadata or {},
        ip_address=ip,
    )
