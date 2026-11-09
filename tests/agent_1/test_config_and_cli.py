import pytest

from saas_research.__main__ import main
from saas_research.config import DEFAULT_LLM_MODEL, Settings
from saas_research.errors import ConfigurationError
from saas_research.llm import build_llm
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.sources import build_fetcher, build_search
from saas_research.sources.fake import FakePageFetcher, FakeSearchProvider
from saas_research.sources.search_http import BraveSearch, SerpApiSearch

MOCK_ENV = {"LLM_PROVIDER": "fake", "SEARCH_PROVIDER": "fake", "FETCHER": "fake"}


def test_defaults():
    s = Settings.from_env({})
    assert s.llm_provider == "anthropic" and s.llm_model == DEFAULT_LLM_MODEL == "claude-sonnet-5-5"
    assert s.search_provider == "brave" and s.fetcher == "http" and s.llm_fallbacks is True
    assert s.llm_api_key is None and not s.uses_mocks


def test_overrides_and_secret_not_in_repr():
    s = Settings.from_env({"LLM_MODEL": "my-model", "LLM_API_KEY": "sk-secret", "LLM_EFFORT": "LOW",
                           "LLM_FALLBACKS": "false", "SEARCH_PROVIDER": "serpapi", "SEARCH_API_KEY": "k2",
                           "AGENT1_BATCH_SIZE": "25"})
    assert (s.llm_model, s.llm_effort, s.llm_fallbacks, s.search_provider, s.batch_size) == \
        ("my-model", "low", False, "serpapi", 25)
    assert "sk-secret" not in repr(s) and "k2" not in repr(s)


@pytest.mark.parametrize("env", [{"LLM_PROVIDER": "openai"}, {"LLM_EFFORT": "huge"}, {"AGENT1_BATCH_SIZE": "0"},
                                 {"LLM_FALLBACKS": "maybe"}, {"SEARCH_PROVIDER": "google"}])
def test_invalid_env_rejected(env):
    with pytest.raises(ConfigurationError):
        Settings.from_env(env)


def test_worker_validation_requires_keys_and_mock_opt_in():
    with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
        Settings.from_env({"SEARCH_API_KEY": "x"}).validate_for_worker()
    with pytest.raises(ConfigurationError, match="SEARCH_API_KEY"):
        Settings.from_env({"LLM_API_KEY": "x"}).validate_for_worker()
    with pytest.raises(ConfigurationError, match="AGENT1_ALLOW_MOCK_PROVIDERS"):
        Settings.from_env(MOCK_ENV).validate_for_worker()
    Settings.from_env({**MOCK_ENV, "AGENT1_ALLOW_MOCK_PROVIDERS": "true"}).validate_for_worker()
    Settings.from_env({"LLM_API_KEY": "x", "SEARCH_API_KEY": "y"}).validate_for_worker()


def test_provider_factories():
    s = Settings.from_env(MOCK_ENV)
    assert isinstance(build_llm(s), FakeLLMProvider)
    assert isinstance(build_search(s), FakeSearchProvider) and isinstance(build_fetcher(s), FakePageFetcher)
    assert isinstance(build_search(Settings.from_env({"SEARCH_API_KEY": "k"})), BraveSearch)
    assert isinstance(build_search(Settings.from_env({"SEARCH_PROVIDER": "serpapi", "SEARCH_API_KEY": "k"})),
                      SerpApiSearch)
    with pytest.raises(ConfigurationError):
        build_llm(Settings.from_env({}))  # anthropic without key


def test_build_anthropic_provider_from_settings():
    pytest.importorskip("anthropic")
    llm = build_llm(Settings.from_env({"LLM_API_KEY": "test-key", "LLM_MODEL": "override-model"}))
    assert (llm.name, llm.model, llm.fallbacks) == ("anthropic", "override-model", True)


def test_cli_exit_codes(monkeypatch):
    for k in ("LLM_PROVIDER", "SEARCH_PROVIDER", "FETCHER", "LLM_API_KEY", "SEARCH_API_KEY", "PLATFORM_API_URL",
              "PLATFORM_AGENT_TOKEN", "AGENT1_ALLOW_MOCK_PROVIDERS"):
        monkeypatch.delenv(k, raising=False)
    assert main(["--check-config"]) == 2  # no keys
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    assert main(["--check-config"]) == 2  # mocks without opt-in
    monkeypatch.setenv("AGENT1_ALLOW_MOCK_PROVIDERS", "true")
    assert main(["--check-config"]) == 2  # no platform url/token
    monkeypatch.setenv("PLATFORM_API_URL", "http://localhost:9")
    monkeypatch.setenv("PLATFORM_AGENT_TOKEN", "agt_test_x")
    assert main(["--check-config"]) == 0
