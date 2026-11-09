"""Agent 1 tests. Puts the agent package on sys.path without touching the shared pytest.ini.

If the agent's own dependencies (pydantic, see agents/agent_1_saas_research/pyproject.toml) are not installed,
the Agent 1 tests are not collected and a warning says why (see INTEGRATION_STATUS "Requests to Team 3": CI must
install the agent package).
"""
import importlib.util
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "agents" / "agent_1_saas_research"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

_missing = [m for m in ("pydantic",) if importlib.util.find_spec(m) is None]
collect_ignore_glob = ["test_*.py"] if _missing else []
if _missing:
    warnings.warn(f"Agent 1 tests skipped: missing {_missing}. pip install -e agents/agent_1_saas_research")
