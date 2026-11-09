"""Agent 2 test setup: make `local_leads` (agents/agent_2_local_leads) and the helpers importable.

pytest.ini (Team 3) puts backend, agents/platform_sdk and tests on sys.path; Agent 2's package is added here
so the shared pytest.ini does not need to change.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "agents" / "agent_2_local_leads", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from a2_helpers import SiteServer, TestPKI  # noqa: E402


@pytest.fixture
def sites():
    """Factory for local test websites; all servers are stopped after the test."""
    started: list[SiteServer] = []

    def make(routes, host="127.0.0.2", tls=None):
        s = SiteServer(routes, host=host, tls=tls).start()
        started.append(s)
        return s

    yield make
    for s in started:
        s.stop()


@pytest.fixture(scope="session")
def pki(tmp_path_factory):
    return TestPKI(tmp_path_factory.mktemp("pki"))
