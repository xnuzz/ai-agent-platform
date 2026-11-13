"""Bulgaria market pack (local_leads/bulgaria.py) and its wiring."""
from local_leads import bulgaria as bg
from local_leads.contacts import choose_contact
from local_leads.discovery.base import categories_for
from local_leads.discovery.osm import OSMProvider, _tag_filters
from local_leads.handler import _subject, prospect_rank
from local_leads.models import DiscoveredBusiness, TaskInput


def biz(**kw):
    return DiscoveredBusiness(**{"provider": "osm", "provider_id": kw.get("name", "x"), "name": "x", **kw})


def test_small_business_filter_drops_chains_and_brands():
    assert bg.is_chain("Lilly") and bg.is_chain("Аптеки Марешки") and bg.is_chain("BILLA Plovdiv")
    assert bg.is_chain("Some pharmacy", {"brand:wikidata": "Q123"})
    assert not bg.is_chain("Дентален център Усмивка") and not bg.is_chain("Dm Dental")  # "dm" alone, not a prefix
    inp = TaskInput.parse({"location": {"city": "Plovdiv", "country_code": "BG"}})
    chain = {"type": "node", "id": 1, "tags": {"name": "Shell", "amenity": "fuel"}}
    assert OSMProvider._to_business(chain, inp, {}) is None


def test_bulgarian_categories_and_defaults():
    assert _tag_filters("автосервиз") == ['["shop"="car_repair"]'] and _tag_filters("Къща за гости")
    bg_inp = TaskInput.parse({"location": {"city": "Варна", "country_code": "BG"}})
    assert categories_for(bg_inp) == bg.DEFAULT_CATEGORIES
    assert "Tyres" in categories_for(bg_inp) and _tag_filters("Tyres") == ['["shop"="tyres"]']


def test_phone_mobile_social_and_free_hosts():
    assert bg.normalize_phone("032 123 456") == "+35932123456"
    assert bg.normalize_phone("+359 88 123 4567; 032 1") == "+359881234567"
    assert bg.is_mobile("0888 123 456") and bg.is_mobile("+359 98 765 4321") and not bg.is_mobile("032 123 456")
    assert bg.is_social_only("https://www.facebook.com/hotelgabi") and bg.is_social_only("http://m.facebook.com/x")
    assert not bg.is_social_only("https://hotelgabi.bg")
    assert bg.is_free_host("http://hoteldali.hit.bg/") and bg.is_free_host("https://x.wixsite.com/y")
    assert not bg.is_free_host("https://hit.bg") and not bg.is_free_host("https://superdent.eu")


def test_owner_run_and_facebook_only_businesses_rank_first():
    found = [biz(name="site", website="https://a.bg", phone="032 123 456", country_code="BG"),
             biz(name="landline", phone="032 123 456", country_code="BG"),
             biz(name="fb-mobile", website="https://facebook.com/x", phone="0888 123 456", country_code="BG"),
             biz(name="nothing", country_code="BG")]
    assert [b.name for b in sorted(found, key=prospect_rank)] == ["fb-mobile", "landline", "site", "nothing"]


def test_page_checks_euro_company_info_privacy_encoding():
    found = bg.page_findings("Подстригване 25 лв. Боядисване 60 лева", [("/", "Начало")], "windows-1251")
    assert set(found) == {"PRICES_IN_BGN", "MISSING_COMPANY_INFO", "NO_PRIVACY_POLICY", "OUTDATED_DESIGN"}
    assert found["PRICES_IN_BGN"]["examples"][0].startswith("25")
    ok = bg.page_findings("Цена 12,78 € (25 лв.) · Салон ЕООД, ЕИК 123456789", [("/privacy", "Политика за поверителност")],
                          "utf-8")
    assert ok == {}


def test_bulgarian_compliance_subject_and_legal_basis():
    assert _subject("Идея за сайта", "BG") == "Търговско предложение: Идея за сайта"
    assert _subject("Търговско предложение: X", "BG") == "Търговско предложение: X"
    assert _subject("Idea", "DE") == "Idea"
    company = choose_contact([("office@superdent.eu", "website")], business_name="Супердент",
                             website="https://superdent.eu", country_code="BG")
    assert company.legal_basis == "LEGITIMATE_INTEREST" and "КЗП" in company.legal_basis_note
    person = choose_contact([("m_kostova62@abv.bg", "website")], business_name="Д-р Мария Костова", country_code="BG")
    assert person.legal_basis == "UNKNOWN" and "consent" in person.legal_basis_note


def test_review_regressions_no_false_claims_and_no_lost_leads():
    from local_leads.analyzer.fetcher import FetchResult
    from local_leads.bundle import BatchBundle, Refs
    from local_leads.handler import LocalLeadsAgent

    # facebook pages are different businesses: not deduped by domain, not sent as a website
    a = biz(name="Salon A", provider_id="1", website="https://www.facebook.com/salonA")
    b = biz(name="Salon B", provider_id="2", website="https://facebook.com/salonB")
    assert len(LocalLeadsAgent._dedupe([a, b])) == 2
    bb = BatchBundle()
    bb.business(a, Refs(a), email="", evidence_refs=[])
    assert bb.data["businesses"][0]["website"] == ""
    # windows-1251 declared only in <meta> is decoded, so the page is read correctly
    html = '<meta charset="windows-1251"><p>Салон ЕООД, ЕИК 123456789 · Защита на личните данни</p>'.encode("cp1251")
    text = FetchResult(url="x", status=200, headers={"content-type": "text/html"}, body=html).text()
    assert "ЕИК" in text and set(bg.page_findings(text, [], "windows-1251")) == {"OUTDATED_DESIGN"}
    # standard Bulgarian privacy wording, Latin company forms, Булстат
    assert bg.PRIVACY_RE.search("Защита на личните данни") and bg.PRIVACY_RE.search("/zashtita-na-lichnite-danni")
    assert all(bg.COMPANY_INFO_RE.search(t) for t in ("Булстат: 123456789", "ЕИК123456789", "Ivan EOOD", "Ex Ltd"))
    # prices: no phone number in the example, registered capital and "Евро 5" don't count
    assert bg.page_findings("Тел.: 0888 123 456, 50 лв", [], "")["PRICES_IN_BGN"]["examples"] == ["50 лв"]
    assert "PRICES_IN_BGN" not in bg.page_findings("Фирма ООД с капитал 5000 лв.", [], "")
    assert "PRICES_IN_BGN" in bg.page_findings("Ремонт Евро 5 двигатели - 80 лв", [], "")
    assert "PRICES_IN_BGN" not in bg.page_findings("25 euro (48.90 лв)", [], "")
    # chains: generic words are real small businesses
    assert not any(bg.is_chain(n) for n in ("Happy Dental", "Metro Dental Clinic", "Zora Beauty", "Lilly Nails"))
    assert bg.is_chain("McDonald’s") and bg.is_chain("Kaufland Пловдив")
    # portals are not the business's own site; their addresses are never the contact
    assert all(bg.is_social_only(u) for u in ("https://pochivka.bg/x", "https://superdoc.bg/lekar/1", "https://g.page/x"))
    # phones
    assert bg.normalize_phone("+359 (0) 88 123 4567") == "+359881234567" and bg.is_mobile("00359 (0)88 123 4567")
    assert bg.normalize_phone("0888123456 или 032123456") == "+359888123456"
    # free-mail is never treated as a legal entity, even with a generic local part
    c = choose_contact([("office@abv.bg", "listing")], business_name="Салон Мила", country_code="BG")
    assert c.legal_basis == "UNKNOWN"
    # mobile bonus only in BG; subject prefix case-insensitive
    assert prospect_rank(biz(name="m", phone="089 1234567", country_code="DE"))[1] == 1
    assert _subject("ТЪРГОВСКО ПРЕДЛОЖЕНИЕ: x", "BG") == "ТЪРГОВСКО ПРЕДЛОЖЕНИЕ: x"


def test_season_detection():
    assert bg.season("Несебър", "Guest house") == "coast" and bg.season("Bansko", "Hotel") == "ski"
    assert bg.season("Plovdiv", "Hotel") == "" and bg.season("Varna", "Dentist") == ""
