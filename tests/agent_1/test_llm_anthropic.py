"""Anthropic provider tested against a mocked HTTP transport (no network, no API key in this environment)."""
import json

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from platform_sdk import RetryableError  # noqa: E402
from saas_research.errors import LLMOutputError, LLMRefusalError, ProviderError  # noqa: E402
from saas_research.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider  # noqa: E402
from saas_research.schemas import OfferDraft  # noqa: E402

OFFER = {"headline": "Fill cancelled slots", "value_proposition": "Saves hours", "pricing": "",
         "call_to_action": "15-min call?"}


def message(content_text, stop_reason="end_turn"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": content_text}] if content_text is not None else [],
            "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 5}}


def provider(responses, **kw):
    """responses: list of (status, json) returned in order; captured requests in .requests."""
    requests = []

    def handler(req):
        requests.append(req)
        status, body = responses[min(len(requests) - 1, len(responses) - 1)]
        return httpx2.Response(status, json=body, headers={"request-id": "req_test"})

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    p = AnthropicProvider(api_key="test-key", http_client=http, max_retries=0, **kw)
    p.requests = requests
    return p


def test_structured_request_shape_and_parse():
    p = provider([(200, message(json.dumps(OFFER)))], effort="medium")
    out = p.generate(system="sys", prompt="<input>{}</input>", output_model=OfferDraft)
    assert isinstance(out, OfferDraft) and out.headline == "Fill cancelled slots"
    req = p.requests[0]
    body = json.loads(req.content)
    assert req.url.path == "/v1/messages" and "test-key" in (req.headers.get("x-api-key", "") + req.headers.get("authorization", ""))
    assert body["model"] == "claude-sonnet-5-5" and body["max_tokens"] == 16000 and body["system"] == "sys"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "medium"
    assert set(body["output_config"]["format"]["schema"]["properties"]) == set(OFFER)
    assert body["fallbacks"] == "default" and FALLBACK_BETA in req.headers["anthropic-beta"]


def test_model_override_and_fallbacks_off():
    p = provider([(200, message(json.dumps(OFFER)))], model="custom-model", fallbacks=False, max_tokens=2048)
    p.generate(system="s", prompt="p", output_model=OfferDraft)
    body = json.loads(p.requests[0].content)
    assert body["model"] == "custom-model" and body["max_tokens"] == 2048 and "fallbacks" not in body
    assert "output_config" in body and "effort" not in body["output_config"]


@pytest.mark.parametrize("status,etype", [(429, "rate_limit_error"), (529, "overloaded_error"),
                                          (500, "api_error"), (503, "api_error")])
def test_transient_errors_map_to_retryable(status, etype):
    p = provider([(status, {"type": "error", "error": {"type": etype, "message": "slow down"}})])
    with pytest.raises(RetryableError):
        p.generate(system="s", prompt="p", output_model=OfferDraft)


@pytest.mark.parametrize("status,etype", [(400, "invalid_request_error"), (401, "authentication_error"),
                                          (404, "not_found_error")])
def test_client_errors_are_not_retryable(status, etype):
    p = provider([(status, {"type": "error", "error": {"type": etype, "message": "nope"}})])
    with pytest.raises(ProviderError) as ei:
        p.generate(system="s", prompt="p", output_model=OfferDraft)
    assert not isinstance(ei.value, RetryableError)


def test_connection_error_is_retryable():
    def boom(req):
        raise httpx2.ConnectError("down", request=req)

    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(boom))
    p = AnthropicProvider(api_key="k", http_client=http, max_retries=0)
    with pytest.raises(RetryableError):
        p.generate(system="s", prompt="p", output_model=OfferDraft)


def test_refusal_raises():
    p = provider([(200, {**message(None, "refusal"), "stop_details": {"type": "refusal", "category": "cyber",
                                                                       "explanation": None}})])
    with pytest.raises(LLMRefusalError, match="cyber"):
        p.generate(system="s", prompt="p", output_model=OfferDraft)


def test_invalid_output_retried_once_then_succeeds():
    bad = json.dumps({**OFFER, "headline": "x" * 400})  # violates max_length=300
    p = provider([(200, message(bad)), (200, message(json.dumps(OFFER)))])
    assert p.generate(system="s", prompt="p", output_model=OfferDraft).headline == OFFER["headline"]
    assert len(p.requests) == 2


def test_persistently_invalid_or_truncated_output_raises():
    p = provider([(200, message("not json at all"))])
    with pytest.raises(LLMOutputError):
        p.generate(system="s", prompt="p", output_model=OfferDraft)
    assert len(p.requests) == 2  # one retry
    p = provider([(200, message('{"headline": "cut', "max_tokens"))], output_retries=0)
    with pytest.raises(LLMOutputError):
        p.generate(system="s", prompt="p", output_model=OfferDraft)


def test_requires_api_key():
    with pytest.raises(ProviderError):
        AnthropicProvider(api_key=None)
