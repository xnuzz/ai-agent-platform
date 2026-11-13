"""Google Places API (New) - Text Search provider (DISCOVERY_PROVIDER=google_places).

POST https://places.googleapis.com/v1/places:searchText with `X-Goog-Api-Key` and `X-Goog-FieldMask`.
One query per category ("<category> in <city>, <region>, <country>"), paged via `nextPageToken`
(pageSize <= 20). With coordinates, a circular `locationBias` (radius <= 50 km, API limit) is sent and
results outside `radius_km` are dropped. Permanently closed places are skipped.
Requires GOOGLE_PLACES_API_KEY. The HTTP transport is injectable (tests use httpx.MockTransport).
Note: Google's terms restrict caching Places content other than place IDs - see README §Compliance.
"""
from __future__ import annotations

import logging

import httpx

from .. import bulgaria
from ..models import DiscoveredBusiness, TaskInput
from .base import DiscoveryError, DiscoveryProvider, DiscoveryUnavailable, categories_for, within_radius

logger = logging.getLogger("local_leads.discovery.google")
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.addressComponents", "places.location",
    "places.websiteUri", "places.nationalPhoneNumber", "places.internationalPhoneNumber", "places.googleMapsUri",
    "places.businessStatus", "places.primaryTypeDisplayName", "nextPageToken",
])
MAX_PAGES = 3          # API returns at most 60 results per query
MAX_BIAS_RADIUS_M = 50_000


class GooglePlacesProvider(DiscoveryProvider):
    name = "google_places"

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 20.0,
                 endpoint: str = ENDPOINT):
        if not api_key:
            raise DiscoveryError("GOOGLE_PLACES_API_KEY is required for DISCOVERY_PROVIDER=google_places")
        self.endpoint = endpoint
        self._http = httpx.Client(transport=transport, timeout=timeout, headers={
            "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK, "Content-Type": "application/json"})

    def close(self) -> None:
        self._http.close()

    def _search(self, body: dict) -> dict:
        try:
            resp = self._http.post(self.endpoint, json=body)
        except httpx.HTTPError as exc:
            raise DiscoveryUnavailable(f"Google Places request failed: {exc}") from exc
        if resp.status_code == 429 or resp.status_code >= 500:
            raise DiscoveryUnavailable(f"Google Places HTTP {resp.status_code}")
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("error", {}).get("message", "")
            except ValueError:
                msg = resp.text[:200]
            raise DiscoveryError(f"Google Places HTTP {resp.status_code}: {msg}")
        return resp.json()

    def discover(self, inp: TaskInput, *, limit: int) -> list[DiscoveredBusiness]:
        loc = inp.location
        out: dict[str, DiscoveredBusiness] = {}
        cats = categories_for(inp)
        per_cat = max(1, -(-limit // len(cats)))  # ceil: spread the budget across categories
        for cat in cats:
            if len(out) >= limit:
                break
            query = f"{cat} in {loc.label}"
            body: dict = {"textQuery": query, "pageSize": min(20, per_cat), "languageCode": inp.language_for(inp.location.country_code),
                          "regionCode": loc.country_code}
            if loc.latitude is not None and loc.longitude is not None:
                body["locationBias"] = {"circle": {
                    "center": {"latitude": loc.latitude, "longitude": loc.longitude},
                    "radius": float(min(MAX_BIAS_RADIUS_M, loc.radius_km * 1000))}}
            taken = 0
            for _page in range(MAX_PAGES):
                data = self._search(body)
                for place in data.get("places", []):
                    b = self._to_business(place, cat, inp)
                    if b is None or b.provider_id in out or not within_radius(b, inp):
                        continue
                    out[b.provider_id] = b
                    taken += 1
                    if len(out) >= limit or taken >= per_cat:
                        break
                token = data.get("nextPageToken")
                if not token or len(out) >= limit or taken >= per_cat:
                    break
                body = {**body, "pageToken": token}
        return list(out.values())[:limit]

    @staticmethod
    def _to_business(p: dict, category: str, inp: TaskInput) -> DiscoveredBusiness | None:
        if not p.get("id") or p.get("businessStatus") == "CLOSED_PERMANENTLY":
            return None
        comps = {t: c for c in p.get("addressComponents", []) for t in c.get("types", [])}
        get = lambda t, k="longText": (comps.get(t) or {}).get(k, "")  # noqa: E731
        street = " ".join(x for x in (get("route"), get("street_number")) if x)
        name = (p.get("displayName") or {}).get("text", "").strip()
        if not name or bulgaria.is_chain(name):  # chains are not small-business clients
            return None
        loc = p.get("location") or {}
        return DiscoveredBusiness(
            provider="google_places", provider_id=p["id"], name=name,
            category=(p.get("primaryTypeDisplayName") or {}).get("text") or category,
            website=p.get("websiteUri", ""),
            phone=p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber", ""),
            address_line1=street or (p.get("formattedAddress", "").split(",")[0]),
            city=get("locality") or get("postal_town") or inp.location.city,
            region=get("administrative_area_level_1"), postal_code=get("postal_code"),
            country_code=(get("country", "shortText") or inp.location.country_code).upper(),
            latitude=loc.get("latitude"), longitude=loc.get("longitude"),
            listing_url=p.get("googleMapsUri", ""), listing_title=f"Google Maps listing: {name}",
            source_data={"place_id": p["id"], "provider": "google_places", "query_category": category,
                         "formatted_address": p.get("formattedAddress", ""),
                         "business_status": p.get("businessStatus", "")},
        )
