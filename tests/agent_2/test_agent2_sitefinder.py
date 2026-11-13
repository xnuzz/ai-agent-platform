"""Website lookup for businesses whose listing has no website (analyzer/sitefinder.py)."""
import httpx
from local_leads.analyzer import PoliteFetcher
from local_leads.analyzer.sitefinder import candidate_urls, find_website
from local_leads.config import CrawlerSettings
from local_leads.models import DiscoveredBusiness

PAGE = "<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{body}</p></body></html>"


def biz(**kw) -> DiscoveredBusiness:
    base = {"provider": "osm", "provider_id": "node/1", "name": "Зъболекар Иванов", "city": "Пловдив",
            "country_code": "BG", "phone": "+359 32 123 456"}
    return DiscoveredBusiness(**{**base, **kw})


def fetcher(sites: dict[str, str]) -> PoliteFetcher:
    def handle(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        html = sites.get(req.url.host)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"}) if html else httpx.Response(404)
    settings = CrawlerSettings(info_url="https://bot-info.test/x", min_host_interval=0.0, trust_env=False)
    return PoliteFetcher(settings, transport=httpx.MockTransport(handle))


def test_candidates_transliterate_and_skip_generic_names():
    assert candidate_urls(biz()) == ["https://zabolekarivanov.bg", "https://zabolekar-ivanov.bg",
                                     "https://zabolekarivanov.com", "https://zabolekar-ivanov.com"]
    assert candidate_urls(biz(name="Bar")) == []
    assert candidate_urls(biz(name="Café Müller GmbH", country_code="DE"))[0] == "https://cafemuller.de"


def test_finds_site_only_with_name_plus_phone_or_city():
    good = PAGE.format(title="Зъболекар Иванов", body="Обадете се: 032 123 456")
    url, proof = find_website(biz(), fetcher({"zabolekar-ivanov.bg": good}))
    assert url == "https://zabolekar-ivanov.bg" and proof == ["name", "phone"]

    # same name, but nothing ties it to this business (another town, other phone) -> not accepted
    other = PAGE.format(title="Зъболекар Иванов", body="Варна, тел. 052 999 888")
    assert find_website(biz(), fetcher({"zabolekarivanov.bg": other})) == ("", [])
    # page for a different business on the guessed domain
    assert find_website(biz(), fetcher({"zabolekarivanov.com": PAGE.format(title="Domain for sale", body="")})) \
        == ("", [])
