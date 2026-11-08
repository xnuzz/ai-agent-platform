import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership
from support.factories import make_user, make_workspace

pytestmark = pytest.mark.django_db


def test_register_login_me():
    c = APIClient()
    r = c.post("/api/v1/auth/register/", {"email": "New@Example.com", "password": "Very-strong-pass-42",
                                          "workspace_name": "My Studio"}, format="json")
    assert r.status_code == 201, r.content
    assert Membership.objects.get(user__email="new@example.com").role == "OWNER"
    tok = c.post("/api/v1/auth/token/", {"email": "new@example.com", "password": "Very-strong-pass-42"},
                 format="json").json()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok['access']}")
    assert c.get("/api/v1/auth/me/").json()["email"] == "new@example.com"
    ws = c.get("/api/v1/workspaces/").json()["results"]
    assert ws[0]["role"] == "OWNER" and ws[0]["sender_identity_complete"] is False


def test_register_rejects_weak_password():
    r = APIClient().post("/api/v1/auth/register/", {"email": "a@b.test", "password": "123",
                                                    "workspace_name": "x"}, format="json")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_workspace_header_required_and_isolated(owner, workspace):
    c = APIClient()
    c.force_authenticate(user=owner)
    assert c.get("/api/v1/research-tasks/").json()["error"]["code"] == "workspace_required"

    other = make_workspace(make_user(email="other@example.com"), name="Other")
    c.credentials(HTTP_X_WORKSPACE_ID=str(other.id))
    r = c.get("/api/v1/research-tasks/")
    assert r.status_code == 400 and r.json()["error"]["code"] == "workspace_required"


def test_viewer_is_read_only(viewer_api):
    assert viewer_api.get("/api/v1/research-tasks/").status_code == 200
    r = viewer_api.post("/api/v1/research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH",
                                                    "input": {"industry": "x"}}, format="json")
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"


def test_only_admin_changes_workspace_settings(developer_api, api, workspace):
    url = f"/api/v1/workspaces/{workspace.id}/"
    assert developer_api.patch(url, {"daily_send_limit": 5}, format="json").status_code == 403
    r = api.patch(url, {"consent_required_countries": ["de", "at"]}, format="json")
    assert r.status_code == 200 and r.json()["consent_required_countries"] == ["DE", "AT"]


def test_cannot_remove_last_owner(api, workspace, owner):
    m = Membership.objects.get(user=owner, workspace=workspace)
    r = api.patch(f"/api/v1/members/{m.id}/", {"role": "ADMIN"}, format="json")
    assert r.status_code == 409
