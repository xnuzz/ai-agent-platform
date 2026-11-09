"""Discovery providers against mocked HTTP (httpx.MockTransport): request shape, paging, mapping, errors."""
import json
from urllib.parse import parse_qs

import httpx
import pytest
from local_leads.config import Settings
from local_leads.discovery import DiscoveryError, DiscoveryUnavailable, build_discovery
from local_leads.discovery.fake import FakeDiscoveryProvider
from local_leads.discovery.google_places import FIELD_MASK, GooglePlacesProvider
from local_leads.discovery.osm import ATTRIBUTION, OSMProvider
from local_leads.models import TaskInput


def place(pid, name, *, lat=42.15, lng=24.75, status="OPERATIONAL", website="https://x.test"):
    return {"id": pid, "displayName": {"text": name}, "formattedAddress": "1 Main St, Plovdiv, Bulgaria",
            "addressComponents": [{"longText": "Main St", "types": ["route"]},
                                  {"longText": "1", "types": ["street_number"]},
                                  {"longText": "Plovdiv", "types": ["locality"]},
                                  {"longText": "4000", "types": ["postal_code"]},
                                  {"longText": "Bulgaria", "shortText": "BG", "types": ["country"]}],
            "location": {"latitude": lat, "longitude": lng}, "websiteUri": website,
            "internationalPhoneNumber": "+359 32 000 000", "googleMapsUri": f"https://maps.google.com/?cid={pid}",
            "businessStatus": status, "primaryTypeDisplayName": {"text": "Dentist"}}


def test_google_places_paging_mapping_and_radius():
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append((dict(request.headers), body))
        if "pageToken" not in body:
            return httpx.Response(200, json={"places": [place("p1", "Smile"), place("p2", "Closed", status=
                                                                                     "CLOSED_PERMANENTLY"),
                                                        place("p3", "Far away", lat=43.5)],
                                             "nextPageToken": "tok"})
        return httpx.Response(200, json={"places": [place("p4", "Second page")]})

    inp = TaskInput.parse({"location": {"city": "Plovdiv", "country_code": "bg", "radius_km": 5,
                                        "latitude": 42.15, "longitude": 24.75},
                           "categories": ["Dentist"], "max_businesses": 10, "language": "bg"})
    out = GooglePlacesProvider("secret", transport=httpx.MockTransport(handler)).discover(inp, limit=10)

    assert [b.name for b in out] == ["Smile", "Second page"]       # closed + out-of-radius dropped
    headers, body = calls[0]
    assert headers["x-goog-api-key"] == "secret" and headers["x-goog-fieldmask"] == FIELD_MASK
    assert body["textQuery"] == "Dentist in Plovdiv, BG" and body["languageCode"] == "bg"
    assert body["locationBias"]["circle"]["radius"] == 5000.0 and body["regionCode"] == "BG"
    assert calls[1][1]["pageToken"] == "tok"
    b = out[0]
    assert b.provider_id == "p1" and b.source_data["place_id"] == "p1" and b.listing_url.endswith("cid=p1")
    assert (b.address_line1, b.city, b.postal_code, b.country_code) == ("Main St 1", "Plovdiv", "4000", "BG")
    assert b.website == "https://x.test" and b.phone == "+359 32 000 000" and b.category == "Dentist"


def test_google_places_spreads_limit_over_default_categories():
    queries = []

    def handler(request):
        q = json.loads(request.content)["textQuery"]
        queries.append(q)
        return httpx.Response(200, json={"places": [place(f"{q}-{i}", f"{q} {i}") for i in range(5)]})

    inp = TaskInput.parse({"location": {"city": "Sofia", "country_code": "BG"}, "max_businesses": 4})
    out = GooglePlacesProvider("k", transport=httpx.MockTransport(handler)).discover(inp, limit=4)
    assert len(out) == 4 and len(queries) == 4  # 10 default categories, ceil(4/10)=1 per category


@pytest.mark.parametrize("status,error", [(429, DiscoveryUnavailable), (503, DiscoveryUnavailable),
                                          (403, DiscoveryError)])
def test_google_places_errors(status, error):
    provider = GooglePlacesProvider("k", transport=httpx.MockTransport(
        lambda r: httpx.Response(status, json={"error": {"message": "nope"}})))
    with pytest.raises(error):
        provider.discover(TaskInput.parse({"location": {"city": "A", "country_code": "BG"}}), limit=3)
    with pytest.raises(DiscoveryError):
        GooglePlacesProvider("")


def test_osm_geocodes_then_queries_overpass():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if "nominatim" in request.url.host:
            return httpx.Response(200, json=[{"lat": "42.1354", "lon": "24.7453"}])
        query = parse_qs(request.content.decode())["data"][0]
        assert '["amenity"="dentist"]' in query and "around:3000,42.1354,24.7453" in query
        assert '["name"~"Pottery studio",i]' in query
        return httpx.Response(200, json={"elements": [
            {"type": "node", "id": 1, "lat": 42.1, "lon": 24.7,
             "tags": {"name": "Smile", "amenity": "dentist", "website": "https://smile.test",
                      "contact:email": "info@smile.test", "addr:street": "Main", "addr:housenumber": "5"}},
            {"type": "way", "id": 2, "center": {"lat": 42.2, "lon": 24.8}, "tags": {"amenity": "dentist"}},
        ]})

    provider = OSMProvider(user_agent="LocalLeadsBot/0.1 (+https://bot.test)", overpass_url="https://overpass.test/i",
                           nominatim_url="https://nominatim.test/search", transport=httpx.MockTransport(handler))
    inp = TaskInput.parse({"location": {"city": "Plovdiv", "country_code": "BG", "radius_km": 3},
                           "categories": ["Dentist", "Pottery studio"]})
    out = provider.discover(inp, limit=5)
    assert len(out) == 1  # unnamed element skipped
    b = out[0]
    assert (b.provider_id, b.category, b.email, b.address_line1) == ("node/1", "Dentist", "info@smile.test", "Main 5")
    assert b.attribution == ATTRIBUTION and b.listing_url == "https://www.openstreetmap.org/node/1"
    assert parse_qs(calls[0].url.query.decode())["countrycodes"] == ["bg"]
    assert all(c.headers["user-agent"].startswith("LocalLeadsBot/") for c in calls)


def test_fake_provider_filters_and_file(tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps([{"provider_id": "1", "name": "A", "category": "Bakery"},
                             {"provider_id": "2", "name": "B", "category": "Dentist"},
                             {"provider_id": "3", "name": "C", "category": "Dentist"}]))
    p = FakeDiscoveryProvider(file=str(f))
    inp = TaskInput.parse({"location": {"city": "X", "country_code": "DE"}, "categories": ["dentist"]})
    out = p.discover(inp, limit=1)
    assert [b.name for b in out] == ["B"] and out[0].city == "X" and out[0].country_code == "DE"
    assert out[0].source_data["provider"] == "fake (mock)"


def test_build_discovery_selects_provider():
    assert build_discovery(Settings.from_env({"DISCOVERY_PROVIDER": "fake"})).name == "fake"
    assert build_discovery(Settings.from_env({"DISCOVERY_PROVIDER": "osm"})).name == "osm"
    assert build_discovery(Settings.from_env({"GOOGLE_PLACES_API_KEY": "k"})).name == "google_places"
    with pytest.raises(ValueError):
        build_discovery(Settings.from_env({"DISCOVERY_PROVIDER": "yelp"}))
