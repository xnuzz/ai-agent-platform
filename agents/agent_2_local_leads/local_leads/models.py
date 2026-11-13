"""Internal data structures (agent-side only; the wire format is the Result Bundle, see bundle.py)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Location:
    city: str
    country_code: str
    region: str = ""
    radius_km: int = 10
    latitude: float | None = None
    longitude: float | None = None

    @property
    def label(self) -> str:
        return ", ".join(p for p in (self.city, self.region, self.country_code) if p)


@dataclass
class TaskInput:
    """LOCAL_LEAD_DISCOVERY input with contract defaults applied (docs/AGENT_2_CONTRACT.md)."""
    location: Location
    categories: list[str] = field(default_factory=list)
    max_businesses: int = 25
    checks: list[str] = field(default_factory=list)
    min_score: int = 50
    language: str = "auto"         # "auto" = local language of the business's country (market.py)
    notes: str = ""

    def language_for(self, country_code: str) -> str:
        """Outreach language: the explicit task language, else the local language of the business's country."""
        if self.language.lower() not in ("", "auto"):
            return self.language
        from .market import market_for
        return market_for(country_code or self.location.country_code).language

    @classmethod
    def parse(cls, data: dict) -> "TaskInput":
        loc = data.get("location") or {}
        if not loc.get("city") or not loc.get("country_code"):
            raise ValueError("input.location.city and input.location.country_code are required")
        location = Location(
            city=str(loc["city"]).strip(), country_code=str(loc["country_code"]).strip().upper(),
            region=str(loc.get("region") or "").strip(),
            radius_km=min(100, max(1, int(loc.get("radius_km") or 10))),
            latitude=float(loc["latitude"]) if loc.get("latitude") is not None else None,
            longitude=float(loc["longitude"]) if loc.get("longitude") is not None else None,
        )
        categories = [str(c).strip() for c in (data.get("categories") or []) if str(c).strip()][:30]
        return cls(
            location=location, categories=categories,
            max_businesses=min(200, max(1, int(data.get("max_businesses") or 25))),
            checks=[str(c).strip().upper() for c in (data.get("checks") or []) if str(c).strip()],
            min_score=min(100, max(0, int(data["min_score"]))) if data.get("min_score") is not None else 50,
            language=(str(data.get("language") or "auto").strip() or "auto")[:10],
            notes=str(data.get("notes") or ""),
        )


@dataclass
class DiscoveredBusiness:
    """One business as returned by a discovery provider."""
    provider: str
    provider_id: str
    name: str
    category: str = ""
    website: str = ""
    email: str = ""
    phone: str = ""
    address_line1: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    listing_url: str = ""          # public listing page (maps / directory) used as evidence
    listing_title: str = ""
    source_data: dict[str, Any] = field(default_factory=dict)
    attribution: str = ""          # data licence notice (e.g. OSM ODbL)

    @property
    def key(self) -> str:
        """Stable short key used in bundle refs (same business -> same refs across retries)."""
        return hashlib.sha1(f"{self.provider}:{self.provider_id}".encode()).hexdigest()[:16]


@dataclass
class Finding:
    """A problem detected for a business, with the measured facts that prove it."""
    code: str
    severity: str
    title: str
    description: str
    url: str = ""                  # page the fact was measured on
    facts: dict[str, Any] = field(default_factory=dict)
