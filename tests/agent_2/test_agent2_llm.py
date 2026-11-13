"""LLM layer: Anthropic provider (real SDK, mocked HTTP), fake provider, validation, template fallback."""
import json

import pytest

anthropic = pytest.importorskip("anthropic")  # Agent 2 dependency; CI installs it per INTEGRATION_STATUS request
httpx2 = pytest.importorskip("httpx2")         # the anthropic SDK's HTTP library

from local_leads.config import DEFAULT_LLM_MODEL, Settings  # noqa: E402
from local_leads.llm import LLMError, LLMRefusal, LLMUnavailable, build_llm, validate  # noqa: E402
from local_leads.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider  # noqa: E402
from local_leads.llm.fake import FakeLLMProvider  # noqa: E402
from local_leads.writing import BRIEF_SCHEMA, OUTREACH_SCHEMA, Writer, strip_signoff  # noqa: E402

FACTS = {
    "language": "en", "score": 77,
    "business": {"name": "Corner Bakery", "category": "Bakery", "city": "Plovdiv", "country_code": "BG",
                 "website": "http://cornerbakery.test", "domain": "cornerbakery.test"},
    "problems": [{"code": "NO_HTTPS", "title": "Website not served over HTTPS", "severity": "HIGH",
                  "description": "The site is served over plain HTTP (http://cornerbakery.test/). More text."}],
    "estimate": {"approach": "fixes", "scope_items": ["Enable HTTPS", "Project management, testing and handover"],
                 "tech_stack": ["Let's Encrypt / managed TLS"], "hours": {"min": 4, "max": 6},
                 "budget": {"min": 250.0, "max": 400.0, "currency": "EUR"}},
    "task_notes": "",
}
GOOD_BRIEF = {"title": "HTTPS for Corner Bakery", "summary": "Corner Bakery serves its site over HTTP only.",
              "proposed_solution": "Enable HTTPS and redirect all traffic.", "approval_summary": "Small, clear fix."}


def anthropic_client(handler):
    return anthropic.Anthropic(api_key="test-key", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))


def message(text, stop_reason="end_turn", **extra):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": DEFAULT_LLM_MODEL,
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10}, **extra}


def test_anthropic_provider_request_shape_and_parsing():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["headers"] = request.headers
        return httpx2.Response(200, json=message(json.dumps(GOOD_BRIEF)))

    llm = AnthropicProvider(client=anthropic_client(handler))
    out = llm.generate_json(task="project_brief", system="sys", prompt="facts", schema=BRIEF_SCHEMA)
    assert out == GOOD_BRIEF
    body = seen["body"]
    assert body["model"] == "claude-sonnet-5-5" == DEFAULT_LLM_MODEL
    assert body["output_config"]["format"]["type"] == "json_schema"
    schema = body["output_config"]["format"]["schema"]
    assert schema["required"] == BRIEF_SCHEMA["required"] and "maxLength" not in json.dumps(schema)
    assert body["output_config"]["effort"] == "medium"
    assert body["fallbacks"] == "default" and FALLBACK_BETA in seen["headers"]["anthropic-beta"]
    assert body["system"] == "sys" and body["messages"] == [{"role": "user", "content": "facts"}]
    assert seen["headers"]["authorization"] == "Bearer test-key"


def test_anthropic_provider_without_server_fallback_and_model_override():
    seen = {}

    def handler(request):
        seen["body"], seen["headers"] = json.loads(request.content), request.headers
        return httpx2.Response(200, json=message(json.dumps({"subject": "s", "body": "b"})))

    llm = AnthropicProvider(model="custom-model-id", effort="none", server_fallback=False,
                            client=anthropic_client(handler))
    llm.generate_json(task="outreach_email", system="s", prompt="p", schema=OUTREACH_SCHEMA)
    assert seen["body"]["model"] == "custom-model-id"
    assert "fallbacks" not in seen["body"] and "anthropic-beta" not in seen["headers"]
    assert "effort" not in seen["body"]["output_config"]


@pytest.mark.parametrize("response,error", [
    (lambda: httpx2.Response(200, json=message("", "refusal", stop_details={"type": "refusal", "category": "cyber",
                                                                            "explanation": "x"})), LLMRefusal),
    (lambda: httpx2.Response(200, json=message('{"title": "x', "max_tokens")), LLMError),
    (lambda: httpx2.Response(200, json=message("not json")), LLMError),
    (lambda: httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}),
     LLMUnavailable),
    (lambda: httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}),
     LLMUnavailable),
    (lambda: httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error",
                                                                    "message": "bad key"}}), LLMError),
])
def test_anthropic_provider_error_mapping(response, error):
    llm = AnthropicProvider(client=anthropic_client(lambda request: response()))
    with pytest.raises(error):
        llm.generate_json(task="t", system="s", prompt="p", schema=BRIEF_SCHEMA)


def test_build_llm_from_settings():
    assert build_llm(Settings.from_env({"LLM_PROVIDER": "template"})) is None
    assert isinstance(build_llm(Settings.from_env({"LLM_PROVIDER": "fake"})), FakeLLMProvider)
    llm = build_llm(Settings.from_env({"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "k", "LLM_MODEL": ""}))
    assert isinstance(llm, AnthropicProvider) and llm.model == DEFAULT_LLM_MODEL
    llm = build_llm(Settings.from_env({"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "k", "LLM_MODEL": "other-model"}))
    assert llm.model == "other-model"
    with pytest.raises(ValueError):
        build_llm(Settings.from_env({"LLM_PROVIDER": "nope"}))


def test_validate_schema_subset():
    assert validate(GOOD_BRIEF, BRIEF_SCHEMA) == []
    errs = validate({"title": "x" * 200, "summary": 3, "extra": 1}, BRIEF_SCHEMA)
    assert any("required" in e for e in errs) and any("unexpected" in e for e in errs)
    assert any("longer than 120" in e for e in errs) and any("expected string" in e for e in errs)


def test_writer_uses_llm_then_falls_back():
    fake = FakeLLMProvider()
    w = Writer(fake).brief(FACTS)
    assert w.author == "fake:mock" and w.note == "" and "Corner Bakery" in w.data["title"]
    assert "FACTS (JSON):" in fake.calls[0]["prompt"] and fake.calls[0]["task"] == "project_brief"

    failing = FakeLLMProvider(scripted={"project_brief": [LLMUnavailable("down")],
                                        "outreach_email": [{"subject": "Hi"}]})
    w = Writer(failing).brief(FACTS)
    assert w.author == "template" and "LLM unavailable" in w.note
    w = Writer(failing).outreach(FACTS)
    assert w.author == "template" and "validation" in w.note and w.data["subject"]
    w = Writer(None).outreach({**FACTS, "language": "fr"})
    assert w.author == "template" and "English (requested language: fr)" in w.note and w.language == "en"
    w = Writer(None).outreach({**FACTS, "language": "bg"})  # native template, no "English" note
    assert w.language == "bg" and "English" not in w.note and w.data["body"].startswith("Здравейте, екип на")


def test_outreach_rules_signoff_stripped_and_forbidden_content_rejected():
    body = "Hello Corner Bakery team,\n\n" + "We noticed your site is served over HTTP. " * 3 + \
           "\n\nWould a short call help?\n\nBest regards,\nAda"
    w = Writer(FakeLLMProvider(scripted={"outreach_email": [{"subject": "HTTPS", "body": body}]})).outreach(FACTS)
    assert w.author == "fake:mock" and w.data["body"].endswith("Would a short call help?")
    shaming = {"subject": "Your awful website", "body": body + "\nClick here to unsubscribe"}
    w = Writer(FakeLLMProvider(scripted={"outreach_email": [shaming]})).outreach(FACTS)
    assert w.author == "template" and "forbidden" in w.note
    assert strip_signoff("Text\n\nKind regards,\nAda\nAcme") == "Text"


def test_template_outreach_is_plain_and_factual():
    out = Writer(None).outreach(FACTS).data
    assert out["subject"] == "cornerbakery.test: a few quick wins"
    body = out["body"]
    assert body.startswith("Hello Corner Bakery team,") and "EUR 250-400" in body
    assert "unsubscribe" not in body.lower() and "regards" not in body.lower() and "[" not in body
    assert "- The site is served over plain HTTP (http://cornerbakery.test/)." in body


def test_bulgarian_template_never_mixes_a_latin_city_name():
    facts = {**FACTS, "language": "bg", "business": {**FACTS["business"], "city": "Plovdiv"}}
    assert "Plovdiv" not in Writer(None).outreach(facts).data["body"]
    facts["business"]["city"] = "Пловдив"
    assert "в Пловдив" in Writer(None).outreach(facts).data["body"]
