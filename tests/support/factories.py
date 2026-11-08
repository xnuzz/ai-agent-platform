"""Django-side test builders (users, workspaces). Bundles live in support.bundles (no Django import)."""
from apps.accounts.models import Membership, User, Workspace
from apps.common.enums import Role


def make_user(email="dev@example.com", password="S3cure-pass-123", **kw):
    return User.objects.create_user(email=email, password=password, **kw)


def make_workspace(owner, name="Acme Dev Studio", *, sender=True, **kw):
    if sender:
        kw = {"sender_name": "Ada Dev", "sender_email": "ada@acme-dev.test", "sender_company": "Acme Dev Studio Ltd",
              "sender_postal_address": "1 Test Street, 1000 Sofia, BG", **kw}
    ws = Workspace.objects.create(name=name, created_by=owner, **kw)
    Membership.objects.create(user=owner, workspace=ws, role=Role.OWNER)
    return ws


def add_member(ws, email, role):
    u = make_user(email=email)
    Membership.objects.create(user=u, workspace=ws, role=role)
    return u


from .bundles import customer_bundle, local_leads_bundle, opportunity_bundle  # noqa: E402,F401
