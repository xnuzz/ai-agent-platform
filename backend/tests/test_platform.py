import pytest

from apps.audit.models import AuditEvent
from apps.integrations.models import Integration

pytestmark = pytest.mark.django_db


def test_integration_secret_is_write_only_and_encrypted(api):
    r = api.post("/api/v1/integrations/", {"kind": "EMAIL", "provider": "SMTP", "name": "Mailgun SMTP",
                                           "config": {"host": "smtp.example.com", "port": 587},
                                           "secret": "s3cr3t"}, format="json")
    assert r.status_code == 201, r.content
    assert "secret" not in r.json() and r.json()["has_secret"] is True
    obj = Integration.objects.get()
    assert "s3cr3t" not in obj.secret_encrypted and obj.get_secret() == "s3cr3t"


def test_integration_rejects_secret_in_config(api):
    r = api.post("/api/v1/integrations/", {"kind": "LLM", "provider": "ANTHROPIC", "name": "x",
                                           "config": {"api_key": "oops"}}, format="json")
    assert r.status_code == 400


def test_integrations_require_admin(developer_api):
    assert developer_api.post("/api/v1/integrations/", {"kind": "LLM", "provider": "ANTHROPIC", "name": "x"},
                              format="json").status_code == 403


def test_audit_is_append_only(api):
    api.post("/api/v1/research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH", "input": {"industry": "x"}},
             format="json")
    ev = AuditEvent.objects.get(action="research_task.created")
    assert ev.actor_type == "USER"
    with pytest.raises(RuntimeError):
        ev.save()
    with pytest.raises(RuntimeError):
        ev.delete()
    assert api.get("/api/v1/audit-events/").json()["count"] >= 1


def test_dashboard_summary(api):
    api.post("/api/v1/research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH", "input": {"industry": "x"}},
             format="json")
    r = api.get("/api/v1/dashboard/summary/").json()
    assert r["research_tasks"] == {"QUEUED": 1} and r["active_tasks_by_agent"] == {"SAAS_RESEARCH": 1}


def test_openapi_schema_served(api):
    from rest_framework.test import APIClient

    assert APIClient().get("/api/schema/").status_code == 200
