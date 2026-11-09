import pytest
from rest_framework.test import APIClient

from apps.common.enums import AgentType, Role
from apps.orchestration.models import AgentToken
from support.factories import add_member, make_user, make_workspace


@pytest.fixture
def owner(db):
    return make_user()


@pytest.fixture
def workspace(owner):
    return make_workspace(owner)


def _client(user, ws):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_WORKSPACE_ID=str(ws.id))
    return c


@pytest.fixture
def api(owner, workspace):
    return _client(owner, workspace)


@pytest.fixture
def viewer_api(workspace):
    return _client(add_member(workspace, "viewer@example.com", Role.VIEWER), workspace)


@pytest.fixture
def developer_api(workspace):
    return _client(add_member(workspace, "developer@example.com", Role.DEVELOPER), workspace)


def _agent_client(agent):
    _, key = AgentToken.issue(name=f"test-{agent}", agent=agent)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Agent {key}")
    return c


@pytest.fixture
def agent1(db):
    return _agent_client(AgentType.SAAS_RESEARCH)


@pytest.fixture
def agent2(db):
    return _agent_client(AgentType.LOCAL_LEADS)


class AgentSession:
    """Helper that claims a task and talks to the agent API with the lease header."""

    def __init__(self, client, task):
        self.client, self.task = client, task
        self.h = {"HTTP_X_LEASE_ID": task["lease_id"]}

    def post(self, suffix, data=None):
        return self.client.post(f"/api/v1/agent/tasks/{self.task['id']}/{suffix}/", data or {}, format="json",
                                **self.h)

    def results(self, bundle):
        return self.post("results", bundle)


@pytest.fixture
def claim():
    def _claim(agent_client, **body):
        r = agent_client.post("/api/v1/agent/tasks/claim/", {"worker_id": "w1", **body}, format="json")
        assert r.status_code == 200, r.content
        return AgentSession(agent_client, r.json()["task"]) if r.json()["task"] else None
    return _claim


@pytest.fixture
def create_task(api):
    def _create(task_type, input_data, client=None):
        r = (client or api).post("/api/v1/research-tasks/", {"task_type": task_type, "input": input_data},
                                 format="json")
        assert r.status_code == 201, r.content
        return r.json()
    return _create


OPP_INPUT = {"industry": "Dental clinics", "regions": ["bg"]}
LOCAL_INPUT = {"location": {"city": "Plovdiv", "country_code": "BG"}, "categories": ["Bakery"]}
