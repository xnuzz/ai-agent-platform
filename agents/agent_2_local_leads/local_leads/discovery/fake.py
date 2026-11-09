"""🧪 MOCK discovery provider - for tests and offline development ONLY (DISCOVERY_PROVIDER=fake).

Returns businesses from a list given in code, or from a JSON file (FAKE_DISCOVERY_FILE: a list of objects
with DiscoveredBusiness fields). Without either it returns a tiny built-in sample whose websites use the
reserved `.invalid` TLD (they never resolve -> WEBSITE_UNREACHABLE). No real business data.
"""
from __future__ import annotations

import json
from dataclasses import fields

from ..models import DiscoveredBusiness, TaskInput
from .base import DiscoveryProvider, within_radius

SAMPLE = [
    {"provider_id": "sample-1", "name": "Sample Bakery (mock)", "category": "Bakery",
     "website": "http://sample-bakery.invalid", "email": "info@sample-bakery.invalid"},
    {"provider_id": "sample-2", "name": "Sample Dental (mock)", "category": "Dentist", "website": "",
     "phone": "+00 000 000"},
]
_FIELDS = {f.name for f in fields(DiscoveredBusiness)}


class FakeDiscoveryProvider(DiscoveryProvider):
    name = "fake"

    def __init__(self, businesses: list[dict | DiscoveredBusiness] | None = None, *, file: str = ""):
        if businesses is None and file:
            with open(file, encoding="utf-8") as fh:
                businesses = json.load(fh)
        self.businesses = [b if isinstance(b, DiscoveredBusiness) else self._from_dict(b)
                           for b in (businesses if businesses is not None else SAMPLE)]
        self.calls: list[tuple[TaskInput, int]] = []

    @staticmethod
    def _from_dict(d: dict) -> DiscoveredBusiness:
        data = {k: v for k, v in d.items() if k in _FIELDS}
        data.setdefault("provider", "fake")
        data.setdefault("listing_url", f"https://directory.invalid/{data.get('provider_id', 'x')}")
        data.setdefault("listing_title", f"Mock directory listing: {data.get('name', '')}")
        data.setdefault("source_data", {"fake_id": data.get("provider_id"), "provider": "fake (mock)"})
        return DiscoveredBusiness(**data)

    def discover(self, inp: TaskInput, *, limit: int) -> list[DiscoveredBusiness]:
        self.calls.append((inp, limit))
        cats = [c.lower() for c in inp.categories]
        out = []
        for b in self.businesses:
            if cats and not any(c in (b.category or "").lower() for c in cats):
                continue
            if not within_radius(b, inp):
                continue
            out.append(DiscoveredBusiness(**{**b.__dict__, "city": b.city or inp.location.city,
                                             "country_code": b.country_code or inp.location.country_code}))
            if len(out) >= limit:
                break
        return out
