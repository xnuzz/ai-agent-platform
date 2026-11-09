"""Real search providers + HTTP fetcher, exercised with httpx.MockTransport (no network, no keys)."""
import httpx
import pytest

from platform_sdk import RetryableError
from saas_research.errors import ProviderError, ProviderTransientError
from saas_research.sources.base import classify_source_type, clean_text, domain_of, is_http_url
from saas_research.sources.fetcher import HttpPageFetcher, extract_emails, html_to_page_parts
from saas_research.sources.search_http import BraveSearch, SerpApiSearch


def test_brave_request_and_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["req"] = req
        return httpx.Response(200, json={"web": {"results": [
            {"url": "https://www.reddit.com/r/dentistry/1", "title": "<strong>Scheduling</strong> hell",
             "description": "We lose &amp; waste hours", "extra_snippets": ["more"], "page_age": "2026-01-01"},
            {"url": "javascript:alert(1)", "title": "bad"},
        ]}})

    s = BraveSearch("brave-key", transport=httpx.MockTransport(handler))
    out = s.search("dental scheduling", max_results=5, country="bg", language="EN")
    r = seen["req"]
    assert r.headers["X-Subscription-Token"] == "brave-key" and r.url.host == "api.search.brave.com"
    assert r.url.params["q"] == "dental scheduling" and r.url.params["country"] == "BG"
    assert r.url.params["search_lang"] == "en" and r.url.params["count"] == "5"
    assert len(out) == 1  # non-http URL dropped
    assert out[0].title == "Scheduling hell" and out[0].snippet == "We lose & waste hours more"
    assert out[0].provider == "brave" and out[0].country_code == "BG" and out[0].retrieved_at.endswith("Z")


def test_serpapi_request_and_parsing():
    seen = {}

    def handler(req):
        seen["req"] = req
        return httpx.Response(200, json={"organic_results": [
            {"link": "https://www.g2.com/products/x/reviews", "title": "X reviews", "snippet": "Too pricey"}]})

    out = SerpApiSearch("serp-key", transport=httpx.MockTransport(handler)).search("x", max_results=3, country="DE",
                                                                                  language="de")
    p = seen["req"].url.params
    assert (p["engine"], p["gl"], p["hl"], p["api_key"], p["num"]) == ("google", "de", "de", "serp-key", "3")
    assert out[0].url == "https://www.g2.com/products/x/reviews" and out[0].snippet == "Too pricey"


def test_serpapi_no_results_error_is_empty():
    t = httpx.MockTransport(lambda r: httpx.Response(200, json={"error": "Google hasn't returned any results"}))
    assert SerpApiSearch("k", transport=t).search("zzz", max_results=3) == []


@pytest.mark.parametrize("status,exc", [(429, ProviderTransientError), (503, ProviderTransientError),
                                        (500, ProviderTransientError), (401, ProviderError), (400, ProviderError)])
def test_search_error_mapping(status, exc):
    t = httpx.MockTransport(lambda r: httpx.Response(status, json={}))
    with pytest.raises(exc) as ei:
        BraveSearch("k", transport=t).search("q", max_results=1)
    assert isinstance(ei.value, RetryableError) == (exc is ProviderTransientError)


def test_search_network_error_is_retryable():
    def boom(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    with pytest.raises(RetryableError):
        SerpApiSearch("k", transport=httpx.MockTransport(boom)).search("q", max_results=1)


def test_search_requires_key():
    with pytest.raises(ProviderError):
        BraveSearch("")


def test_helpers():
    assert classify_source_type("https://www.reddit.com/r/x") == "FORUM"
    assert classify_source_type("https://www.capterra.com/p/1") == "REVIEW"
    assert classify_source_type("https://www.linkedin.com/in/x") == "SOCIAL"
    assert classify_source_type("https://acme.com/blog") == "WEB_PAGE"
    assert domain_of("https://WWW.Acme.com:443/x") == "acme.com"
    assert is_http_url("https://a.b/c") and not is_http_url("ftp://a.b") and not is_http_url("https://a b")
    assert clean_text("<b>a</b>\n\n b &amp; c", 100) == "a b & c"


def test_email_extraction():
    text = "Write to Info@Acme.com or sales [at] acme [dot] com. logo@2x.png noreply@acme.com."
    assert extract_emails(text) == ("info@acme.com", "sales@acme.com", "noreply@acme.com")


def test_html_parsing():
    title, text, emails = html_to_page_parts(
        "<html><head><title>Smile Dental</title><style>.x{}</style><script>var e='x@evil.com'</script></head>"
        "<body><h1>Welcome</h1><p>Call us</p><a href='mailto:office@smile.test?subject=hi'>mail</a></body></html>")
    assert title == "Smile Dental" and "Welcome" in text and "x@evil.com" not in text
    assert emails == ("office@smile.test",)


def _fetcher(routes: dict, **kw):
    def handler(req):
        key = str(req.url)
        if key in routes:
            status, body, headers = routes[key]
            return httpx.Response(status, text=body, headers=headers)
        return httpx.Response(404, text="")
    return HttpPageFetcher(transport=httpx.MockTransport(handler), host_check=lambda h: True, **kw)


def test_fetcher_follows_redirect_and_respects_robots():
    html = {"content-type": "text/html; charset=utf-8"}
    f = _fetcher({
        "https://acme.test/robots.txt": (200, "User-agent: *\nDisallow: /private", {}),
        "https://acme.test/": (301, "", {"location": "https://acme.test/home"}),
        "https://acme.test/home": (200, "<title>Acme</title><p>info@acme.test</p>", html),
        "https://acme.test/private": (200, "<p>secret@acme.test</p>", html),
    })
    page = f.fetch("https://acme.test/")
    assert page.url == "https://acme.test/home" and page.emails == ("info@acme.test",) and page.title == "Acme"
    assert f.fetch("https://acme.test/private") is None  # robots.txt disallow


def test_fetcher_refuses_non_html_and_private_hosts_and_caps_size():
    f = _fetcher({"https://a.test/robots.txt": (404, "", {}),
                  "https://a.test/file": (200, "%PDF", {"content-type": "application/pdf"}),
                  "https://a.test/big": (200, "<p>" + "x" * 5000 + " end@a.test</p>", {"content-type": "text/html"})},
                 max_bytes=1000)
    assert f.fetch("https://a.test/file") is None
    assert f.fetch("https://a.test/big").emails == ()  # truncated before the address
    guarded = HttpPageFetcher(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="x")),
                              host_check=lambda h: h != "internal.test")
    assert guarded.fetch("http://internal.test/") is None
    assert guarded.fetch("file:///etc/passwd") is None


def test_default_host_check_blocks_loopback():
    from saas_research.sources.fetcher import _is_public_host
    assert _is_public_host("127.0.0.1") is False and _is_public_host("localhost") is False
