"""Business discovery provider interface."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from ..models import DiscoveredBusiness, TaskInput

# Used when the task gives no categories ("[] = any"): broad mix of local service businesses.
DEFAULT_CATEGORIES = ["Restaurant", "Dentist", "Hair salon", "Bakery", "Auto repair", "Plumber", "Lawyer",
                      "Accountant", "Beauty salon", "Florist"]


class DiscoveryError(Exception):
    """Non-retryable provider problem (bad credentials, invalid request)."""


class DiscoveryUnavailable(DiscoveryError):
    """Transient provider problem (rate limit, 5xx, network) -> task should be retried later."""


class DiscoveryProvider(ABC):
    name = "base"

    @abstractmethod
    def discover(self, inp: TaskInput, *, limit: int) -> list[DiscoveredBusiness]:
        """Return up to `limit` businesses in the task location (and categories, if any)."""

    def close(self) -> None:  # noqa: B027 - optional hook; providers with HTTP clients override
        """Release provider resources (HTTP clients)."""


def categories_for(inp: TaskInput) -> list[str]:
    return inp.categories or list(DEFAULT_CATEGORIES)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def within_radius(b: DiscoveredBusiness, inp: TaskInput) -> bool:
    loc = inp.location
    if loc.latitude is None or loc.longitude is None or b.latitude is None or b.longitude is None:
        return True  # cannot measure -> keep (provider query is already location-scoped)
    return haversine_km(loc.latitude, loc.longitude, b.latitude, b.longitude) <= loc.radius_km
