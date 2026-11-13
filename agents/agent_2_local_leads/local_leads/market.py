"""Local market profile per country: outreach language, currency and a market hourly rate.

Rates are mid-market freelancer / small-studio rates for small-business web work (2026), calibrated so a
5-page site (briefs.py: ~37-62 h incl. PM) lands inside the typical local price range, e.g. BG ~EUR 950-1,550,
DE ~EUR 2,600-4,350, UK ~GBP 1,850-3,100, US ~USD 2,800-4,650. Sources: public 2026 rate/price surveys
(Eastern Europe ~$25-60/h, Western Europe ~$50-110/h; UK brochure site GBP 1,500-3,000 freelance; US
$1,500-5,000 freelance; DE EUR 1,500-4,500). Bulgaria uses the euro since 2026-01-01.
ponytail: a static table; refresh yearly, or set BRIEF_HOURLY_RATE / BRIEF_CURRENCY to override.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    language: str       # ISO 639-1 outreach language
    currency: str       # ISO 4217
    hourly_rate: float  # in `currency`


_M = Market
MARKETS: dict[str, Market] = {
    # Eastern / Southern Europe
    "BG": _M("bg", "EUR", 25), "RO": _M("ro", "RON", 125), "RS": _M("sr", "EUR", 25), "MK": _M("mk", "EUR", 20),
    "AL": _M("sq", "EUR", 20), "BA": _M("bs", "EUR", 22), "ME": _M("sr", "EUR", 25), "MD": _M("ro", "EUR", 20),
    "UA": _M("uk", "EUR", 20), "TR": _M("tr", "EUR", 25), "GR": _M("el", "EUR", 35), "CY": _M("el", "EUR", 40),
    "HR": _M("hr", "EUR", 35), "SI": _M("sl", "EUR", 40), "HU": _M("hu", "HUF", 12000), "PL": _M("pl", "PLN", 150),
    "CZ": _M("cs", "CZK", 900), "SK": _M("sk", "EUR", 35), "EE": _M("et", "EUR", 40), "LV": _M("lv", "EUR", 35),
    "LT": _M("lt", "EUR", 35),
    # Western / Northern Europe
    "DE": _M("de", "EUR", 70), "AT": _M("de", "EUR", 70), "CH": _M("de", "CHF", 110), "FR": _M("fr", "EUR", 60),
    "BE": _M("nl", "EUR", 70), "NL": _M("nl", "EUR", 75), "LU": _M("fr", "EUR", 80), "ES": _M("es", "EUR", 45),
    "PT": _M("pt", "EUR", 40), "IT": _M("it", "EUR", 50), "IE": _M("en", "EUR", 70), "GB": _M("en", "GBP", 50),
    "DK": _M("da", "DKK", 650), "SE": _M("sv", "SEK", 800), "NO": _M("no", "NOK", 900), "FI": _M("fi", "EUR", 65),
    "MT": _M("en", "EUR", 40), "IS": _M("is", "EUR", 80),
    # Elsewhere
    "US": _M("en", "USD", 75), "CA": _M("en", "CAD", 85), "AU": _M("en", "AUD", 100), "NZ": _M("en", "NZD", 95),
}
DEFAULT = Market("en", "EUR", 50)


def market_for(country_code: str) -> Market:
    return MARKETS.get((country_code or "").upper(), DEFAULT)


def round_price(x: float) -> float:
    """Round up to a 'quote-like' number: 50s for small amounts, coarser for HUF/CZK-sized ones."""
    step = 50 if x < 10_000 else 500 if x < 100_000 else 5_000
    return float(math.ceil(x / step) * step)
