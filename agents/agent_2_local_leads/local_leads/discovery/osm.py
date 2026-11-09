"""OpenStreetMap provider - keyless (DISCOVERY_PROVIDER=osm).

1. Geocode the city with Nominatim (only when the task has no coordinates; one request per task).
2. One Overpass query: named shops/amenities/offices matching the categories within `radius_km`.
Usage policies: identify with a User-Agent, keep volume low (Nominatim max 1 req/s), attribute
"© OpenStreetMap contributors" (ODbL) - carried in evidence metadata. Transport is injectable for tests.
"""
from __future__ import annotations

import logging
import re

import httpx

from ..models import DiscoveredBusiness, TaskInput
from .base import DiscoveryError, DiscoveryProvider, DiscoveryUnavailable, categories_for

logger = logging.getLogger("local_leads.discovery.osm")
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
CATEGORY_TAGS: dict[str, list[str]] = {
    "dentist": ["amenity=dentist"], "bakery": ["shop=bakery"], "restaurant": ["amenity=restaurant"],
    "cafe": ["amenity=cafe"], "coffee": ["amenity=cafe"], "bar": ["amenity=bar", "amenity=pub"],
    "hair salon": ["shop=hairdresser"], "hairdresser": ["shop=hairdresser"], "barber": ["shop=hairdresser"],
    "beauty salon": ["shop=beauty"], "beauty": ["shop=beauty"], "nail salon": ["shop=beauty"],
    "doctor": ["amenity=doctors"], "clinic": ["amenity=clinic"], "pharmacy": ["amenity=pharmacy"],
    "veterinarian": ["amenity=veterinary"], "vet": ["amenity=veterinary"],
    "physiotherapist": ["healthcare=physiotherapist"], "optician": ["shop=optician"],
    "plumber": ["craft=plumber"], "electrician": ["craft=electrician"], "carpenter": ["craft=carpenter"],
    "painter": ["craft=painter"], "photographer": ["craft=photographer", "shop=photo"],
    "auto repair": ["shop=car_repair"], "car repair": ["shop=car_repair"], "mechanic": ["shop=car_repair"],
    "lawyer": ["office=lawyer"], "accountant": ["office=accountant"], "real estate": ["office=estate_agent"],
    "hotel": ["tourism=hotel"], "guest house": ["tourism=guest_house"], "florist": ["shop=florist"],
    "butcher": ["shop=butcher"], "gym": ["leisure=fitness_centre"], "fitness": ["leisure=fitness_centre"],
    "yoga": ["leisure=fitness_centre"], "bookstore": ["shop=books"], "clothing": ["shop=clothes"],
    "dry cleaning": ["shop=dry_cleaning"], "tattoo": ["shop=tattoo"], "driving school": ["amenity=driving_school"],
}


def _tag_filters(category: str) -> list[str]:
    key = category.strip().lower()
    if key in CATEGORY_TAGS:
        return [f'["{k}"="{v}"]' for k, v in (t.split("=") for t in CATEGORY_TAGS[key])]
    safe = re.sub(r'[\\"~^$.*+?()\[\]{}|]', "", category.strip())[:60]
    return [f'["name"~"{safe}",i]'] if safe else []


class OSMProvider(DiscoveryProvider):
    name = "osm"

    def __init__(self, *, user_agent: str, overpass_url: str, nominatim_url: str,
                 transport: httpx.BaseTransport | None = None, timeout: float = 40.0):
        self.overpass_url, self.nominatim_url = overpass_url, nominatim_url
        self._http = httpx.Client(transport=transport, timeout=timeout, headers={"User-Agent": user_agent})

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, url: str, **kw) -> httpx.Response:
        try:
            resp = self._http.request(method, url, **kw)
        except httpx.HTTPError as exc:
            raise DiscoveryUnavailable(f"OSM request failed: {exc}") from exc
        if resp.status_code in (429, 504) or resp.status_code >= 500:
            raise DiscoveryUnavailable(f"OSM HTTP {resp.status_code} from {url}")
        if resp.status_code >= 400:
            raise DiscoveryError(f"OSM HTTP {resp.status_code} from {url}: {resp.text[:200]}")
        return resp

    def geocode(self, inp: TaskInput) -> tuple[float, float]:
        loc = inp.location
        params = {"city": loc.city, "countrycodes": loc.country_code.lower(), "format": "jsonv2", "limit": 1}
        if loc.region:
            params["state"] = loc.region
        results = self._call("GET", self.nominatim_url, params=params).json()
        if not results:
            raise DiscoveryError(f"Location not found: {loc.label}")
        return float(results[0]["lat"]), float(results[0]["lon"])

    def discover(self, inp: TaskInput, *, limit: int) -> list[DiscoveredBusiness]:
        loc = inp.location
        lat, lon = ((loc.latitude, loc.longitude) if loc.latitude is not None and loc.longitude is not None
                    else self.geocode(inp))
        radius_m = int(loc.radius_km * 1000)
        parts, cat_of = [], {}
        for cat in categories_for(inp):
            for f in _tag_filters(cat):
                parts.append(f'nwr{f}["name"](around:{radius_m},{lat},{lon});')
                cat_of[f] = cat
        if not parts:
            return []
        query = f"[out:json][timeout:25];({''.join(parts)});out center tags {max(limit * 3, 30)};"
        data = self._call("POST", self.overpass_url, data={"data": query}).json()
        out: dict[str, DiscoveredBusiness] = {}
        for el in data.get("elements", []):
            b = self._to_business(el, inp, cat_of)
            if b and b.provider_id not in out:
                out[b.provider_id] = b
            if len(out) >= limit:
                break
        return list(out.values())

    @staticmethod
    def _to_business(el: dict, inp: TaskInput, cat_of: dict[str, str]) -> DiscoveredBusiness | None:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name or "type" not in el or "id" not in el:
            return None
        category = ""
        for f, cat in cat_of.items():
            m = re.match(r'\["([^"]+)"="([^"]+)"\]', f)
            if m and tags.get(m.group(1)) == m.group(2):
                category = cat
                break
        center = el.get("center") or {}
        pid = f"{el['type']}/{el['id']}"
        street = " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x)
        return DiscoveredBusiness(
            provider="osm", provider_id=pid, name=name, category=category or next(iter(cat_of.values()), ""),
            website=tags.get("website") or tags.get("contact:website") or tags.get("url") or "",
            email=tags.get("email") or tags.get("contact:email") or "",
            phone=tags.get("phone") or tags.get("contact:phone") or "",
            address_line1=street, city=tags.get("addr:city") or inp.location.city,
            postal_code=tags.get("addr:postcode", ""),
            country_code=(tags.get("addr:country") or inp.location.country_code).upper()[:2],
            latitude=el.get("lat", center.get("lat")), longitude=el.get("lon", center.get("lon")),
            listing_url=f"https://www.openstreetmap.org/{pid}", listing_title=f"OpenStreetMap: {name}",
            source_data={"osm_id": pid, "provider": "osm"}, attribution=ATTRIBUTION,
        )
