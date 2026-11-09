"""Business discovery providers. Select with DISCOVERY_PROVIDER = google_places | osm | fake (🧪 mock)."""
from __future__ import annotations

import logging

from .base import DiscoveryError, DiscoveryProvider, DiscoveryUnavailable

logger = logging.getLogger("local_leads.discovery")

__all__ = ["DiscoveryError", "DiscoveryProvider", "DiscoveryUnavailable", "build_discovery"]


def build_discovery(settings, *, transport=None) -> DiscoveryProvider:
    name = settings.discovery_provider
    if name == "google_places":
        from .google_places import GooglePlacesProvider

        return GooglePlacesProvider(settings.google_places_api_key, transport=transport)
    if name == "osm":
        from .osm import OSMProvider

        return OSMProvider(user_agent=settings.crawler.user_agent, overpass_url=settings.osm_overpass_url,
                           nominatim_url=settings.osm_nominatim_url, transport=transport)
    if name == "fake":
        from .fake import FakeDiscoveryProvider

        logger.warning("DISCOVERY_PROVIDER=fake: using the MOCK discovery provider (no real businesses)")
        return FakeDiscoveryProvider(file=settings.fake_discovery_file)
    raise ValueError(f"Unknown DISCOVERY_PROVIDER {name!r} (expected google_places | osm | fake)")
