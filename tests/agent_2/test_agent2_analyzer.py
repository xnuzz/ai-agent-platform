"""Website analyzer: real HTTP(S) checks against local test servers (no internet)."""
import socket

import pytest
from a2_helpers import GOOD_HOME, Route, good_site_routes, poor_site_routes
from local_leads.analyzer import PoliteFetcher, WebsiteAnalyzer
from local_leads.analyzer.htmlparse import parse_html
from local_leads.config import CrawlerSettings


def crawler(**kw) -> CrawlerSettings:
    base = {"info_url": "https://bot-info.test/local-leads", "min_host_interval": 0.0, "connect_timeout": 2.0,
            "read_timeout": 3.0, "trust_env": False}
    return CrawlerSettings(**{**base, **kw})


def codes(result) -> set[str]:
    return {f.code for f in result.findings}


def free_port(host="127.0.0.9") -> int:
    with socket.socket() as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def test_poor_site_findings_robots_and_user_agent(sites):
    site = sites(poor_site_routes())
    analyzer = WebsiteAnalyzer(crawler())
    res = analyzer.analyze(site.url, category="Dentist")

    assert res.scanned
    assert {"NO_HTTPS", "NOT_MOBILE_FRIENDLY", "MISSING_META", "OUTDATED_CMS", "OUTDATED_DESIGN", "BROKEN_LINKS",
            "NO_CONTACT_FORM", "NO_ONLINE_BOOKING", "NO_ANALYTICS", "SECURITY_HEADERS_MISSING",
            "ACCESSIBILITY_ISSUES", "POOR_SEO"} <= codes(res)
    cms = next(f for f in res.findings if f.code == "OUTDATED_CMS")
    assert cms.facts["version"] == "4.9" and res.facts["cms"] == "WordPress"
    broken = next(f for f in res.findings if f.code == "BROKEN_LINKS").facts["broken"]
    assert [b["url"].rsplit("/", 1)[1] for b in broken] == ["old-menu"]
    # robots.txt fetched once and obeyed; external links never requested
    assert site.paths().count("/robots.txt") == 1
    assert not any(p.startswith("/private") for p in site.paths())
    assert res.facts["links"]["skipped_by_robots"] == 1
    # crawler identifies itself with a contact URL (no e-mail address)
    ua = site.requests[0]["ua"]
    assert ua.startswith("LocalLeadsBot/") and "https://bot-info.test/local-leads" in ua and "@" not in ua
    assert res.emails == ["info@cornerbakery.test"]
    analyzer.close()


def test_good_site_only_reports_missing_https(sites):
    site = sites(good_site_routes(), host="127.0.0.3")
    res = WebsiteAnalyzer(crawler()).analyze(site.url, category="Dentist")
    assert res.scanned and codes(res) == {"NO_HTTPS"}
    assert res.facts["contact_form"] is True and res.facts["online_booking"] is True
    assert res.facts["analytics_detected"] is True and res.facts["security_headers_missing"] == []
    assert "office@moderndental.test" in res.emails
    https_probe = res.facts["https_probe"]
    assert https_probe["url"].startswith("https://127.0.0.3") and https_probe["status"] is None


def test_checks_subset_limits_requests(sites):
    site = sites(poor_site_routes())
    res = WebsiteAnalyzer(crawler()).analyze(site.url, category="Bakery", wanted={"NOT_MOBILE_FRIENDLY"})
    assert codes(res) == {"NOT_MOBILE_FRIENDLY"}
    assert "/old-menu" not in site.paths() and "/about" not in site.paths()   # no link checks


def test_robots_disallow_all_means_no_scan(sites):
    site = sites({"/robots.txt": Route("User-agent: *\nDisallow: /\n", headers={"Content-Type": "text/plain"}),
                  "/": Route(GOOD_HOME)})
    res = WebsiteAnalyzer(crawler()).analyze(site.url)
    assert not res.scanned and res.findings == [] and "robots.txt" in res.skipped_reason
    assert site.paths() == ["/robots.txt"]


def test_robots_specific_agent_rules(sites):
    site = sites({"/robots.txt": Route("User-agent: LocalLeadsBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
                                       headers={"Content-Type": "text/plain"}), "/": Route(GOOD_HOME)})
    res = WebsiteAnalyzer(crawler()).analyze(site.url)
    assert not res.scanned and site.paths() == ["/robots.txt"]


def test_robots_server_error_is_treated_as_disallow(sites):
    site = sites({"/robots.txt": Route("oops", 503), "/": Route(GOOD_HOME)})
    res = WebsiteAnalyzer(crawler()).analyze(site.url)
    assert not res.scanned and res.findings == [] and "/" not in site.paths()


def test_crawl_delay_limits_scan_to_homepage(sites):
    routes = poor_site_routes()
    routes["/robots.txt"] = Route("User-agent: *\nCrawl-delay: 60\n", headers={"Content-Type": "text/plain"})
    site = sites(routes)
    res = WebsiteAnalyzer(crawler(max_crawl_delay=0.2, min_host_interval=0.0)).analyze(site.url)
    assert res.facts["crawl_limited"] is True
    assert "BROKEN_LINKS" not in codes(res) and "/about" not in site.paths()


def test_unreachable_and_404_sites(sites):
    res = WebsiteAnalyzer(crawler()).analyze(f"http://127.0.0.9:{free_port()}/")
    assert codes(res) == {"WEBSITE_UNREACHABLE"} and not res.scanned
    site = sites({"/": Route("gone", 404)})
    res = WebsiteAnalyzer(crawler()).analyze(site.url)
    assert codes(res) == {"WEBSITE_UNREACHABLE"} and res.findings[0].facts["status"] == 404


def test_slow_page_and_size_limit(sites):
    site = sites({"/": Route(GOOD_HOME + ("<p>x</p>" * 5000), delay=0.5)})
    res = WebsiteAnalyzer(crawler(slow_page_seconds=0.2, max_page_bytes=10_000)).analyze(site.url)
    slow = next(f for f in res.findings if f.code == "SLOW_PAGE_LOAD")
    assert slow.facts["seconds"] >= 0.5 and slow.severity == "HIGH"
    assert res.facts["truncated"] is True and res.facts["html_bytes"] == 10_000


def test_per_host_rate_limit(sites):
    site = sites({"/": Route("a"), "/b": Route("b"), "/robots.txt": Route("", 404)})
    fetcher = PoliteFetcher(crawler(min_host_interval=0.25))
    for path in ("", "b", ""):
        assert fetcher.get(site.url + path).status == 200
    times = [r["t"] for r in site.requests]
    assert len(times) == 4  # robots.txt + 3 pages
    assert all(b - a >= 0.22 for a, b in zip(times, times[1:], strict=False))


def test_redirect_to_https_is_followed(sites, pki):
    secure = sites(good_site_routes(), host="127.0.0.4", tls=pki.server_context("127.0.0.4"))
    plain = sites({"/": Route("", 301, {"Location": secure.url}), "/robots.txt": Route("", 404)}, host="127.0.0.5")
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(plain.url, category="Dentist")
    assert res.final_url == secure.url and res.facts["https"] is True
    assert res.facts["redirects"] == [plain.url]
    assert not codes(res) & {"NO_HTTPS", "NO_HTTPS_REDIRECT", "SSL_EXPIRED", "SSL_INVALID_CERTIFICATE"}


def test_valid_certificate(sites, pki):
    site = sites(good_site_routes(), host="127.0.0.4", tls=pki.server_context("127.0.0.4", days_valid=90))
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(site.url, category="Dentist")
    tls = res.facts["tls"]
    assert tls["valid"] is True and 88 <= tls["days_left"] <= 90
    # good site served over valid HTTPS: only the missing HSTS header could remain (1 header -> no finding)
    assert codes(res) == set(), [f.description for f in res.findings]


def test_expired_certificate_still_analyses_content(sites, pki):
    site = sites(poor_site_routes(), host="127.0.0.6", tls=pki.server_context("127.0.0.6", expired=True))
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(site.url)
    assert "SSL_EXPIRED" in codes(res) and "expired" in res.facts["tls"]["error"]
    assert res.scanned and "NOT_MOBILE_FRIENDLY" in codes(res)


def test_untrusted_and_expiring_certificates(sites, pki):
    untrusted = sites(good_site_routes(), host="127.0.0.7", tls=pki.server_context("127.0.0.7", self_signed=True))
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(untrusted.url)
    assert "SSL_INVALID_CERTIFICATE" in codes(res) and res.scanned
    soon = sites(good_site_routes(), host="127.0.0.8", tls=pki.server_context("127.0.0.8", days_valid=5))
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(soon.url)
    assert "SSL_EXPIRING_SOON" in codes(res)
    assert next(f for f in res.findings if f.code == "SSL_EXPIRING_SOON").facts["days_left"] <= 5


def test_mixed_content(sites, pki):
    page = GOOD_HOME.replace("</head>", '<script src="http://cdn.insecure.test/lib.js"></script></head>')
    routes = {**good_site_routes(), "/": Route(page)}
    site = sites(routes, host="127.0.0.10", tls=pki.server_context("127.0.0.10"))
    res = WebsiteAnalyzer(crawler(ca_bundle=str(pki.ca_file))).analyze(site.url)
    mixed = next(f for f in res.findings if f.code == "MIXED_CONTENT")
    assert mixed.facts["resources"] == ["http://cdn.insecure.test/lib.js"]


@pytest.mark.parametrize("html,expected", [
    ('<form action="/search"><input name="q"></form>', False),
    ('<form><input type="email" name="newsletter"></form>', False),
    ('<form><input type="email" name="email"><input name="name"></form>', True),
    ('<form><textarea></textarea></form>', True),
])
def test_contact_form_detection(html, expected):
    page = parse_html(f"<html><body>{html}</body></html>")
    assert any(f.looks_like_contact_form for f in page.forms) is expected


def test_label_and_alt_extraction():
    page = parse_html('<html lang="de"><body><label>Name <input name="n"></label><input id="x">'
                      '<label for="y">Y</label><input id="y"><input type="hidden" name="t">'
                      '<img src="a.png" alt=""><img src="b.png"></body></html>')
    assert page.html_lang == "de" and page.form_controls == 3 and page.unlabelled_controls == 1
    assert page.images_total == 2 and page.images_missing_alt == 1
