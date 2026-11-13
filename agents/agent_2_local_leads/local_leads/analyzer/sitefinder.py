"""Look for a website the listing does not mention, before calling a business "no website".

Listings (OSM especially) often lack the website tag although the business has a site. Pitching
"you have no website" to such a business is wrong, so for every business without a listed site we
try a few domains guessed from its name (`<name>.<ccTLD>`, `<name>.com`, hyphenated) and accept a
hit only if the page shows the business name AND its phone number or city. Requests go through the
polite fetcher (robots.txt, per-host rate limit, timeouts).
ponytail: domain guessing misses sites on unrelated domains or social pages; a web-search provider
would find more (add when a search key is available to Agent 2).
"""
from __future__ import annotations

import re
import unicodedata

from ..models import DiscoveredBusiness
from .fetcher import PoliteFetcher
from .htmlparse import parse_html

# Bulgarian/Russian Cyrillic -> Latin (domains are ASCII; local names often are not).
_CYR = dict(zip("абвгдежзийклмнопрстуфхцчшщъьюяыэё",
                ["a", "b", "v", "g", "d", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                 "t", "u", "f", "h", "ts", "ch", "sh", "sht", "a", "", "yu", "ya", "y", "e", "yo"], strict=True))
# Legal forms and filler words that are rarely part of the domain or a reliable name match.
_STOP = {"ltd", "llc", "gmbh", "ood", "eood", "ad", "et", "inc", "srl", "sarl", "bv", "the", "and", "und", "co",
         "dr", "a", "of", "de", "la", "le", "el"}
MAX_CANDIDATES = 4


def _ascii(text: str) -> str:
    text = "".join(_CYR.get(ch, ch) for ch in text.lower())
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", _ascii(text)) if w not in _STOP]


def candidate_urls(b: DiscoveredBusiness) -> list[str]:
    words = _words(b.name)
    if not words or len("".join(words)) < 4:
        return []  # too generic to guess ("Bar", "A1")
    tlds = [t for t in dict.fromkeys([(b.country_code or "").lower(), "com"]) if len(t) == 2 or t == "com"]
    slugs = list(dict.fromkeys(["".join(words), "-".join(words)]))
    return [f"https://{s}.{t}" for t in tlds for s in slugs][:MAX_CANDIDATES]


def _matches(b: DiscoveredBusiness, html: str) -> list[str]:
    """Evidence that the page belongs to this business; [] = not proven."""
    page = parse_html(html)
    hay = " ".join(_words(f"{page.title} {page.text}"))
    name_words = [w for w in _words(b.name) if len(w) >= 3] or _words(b.name)
    if not name_words or not all(re.search(rf"\b{re.escape(w)}\b", hay) for w in name_words):
        return []
    proof = ["name"]
    digits = re.sub(r"\D", "", b.phone or "")
    if len(digits) >= 6 and digits[-6:] in re.sub(r"\D", "", page.text):
        proof.append("phone")
    city = _words(b.city or "")
    if city and all(re.search(rf"\b{re.escape(w)}\b", hay) for w in city):
        proof.append("city")
    return proof if len(proof) >= 2 else []


def find_website(b: DiscoveredBusiness, fetcher: PoliteFetcher) -> tuple[str, list[str]]:
    """Return (homepage URL, proof) for a verified site, or ("", [])."""
    for url in candidate_urls(b):
        res = fetcher.get(url, max_bytes=500_000)
        if not res.ok or res.status != 200 or not res.is_html:
            continue
        proof = _matches(b, res.text())
        if proof:
            return res.final_url or url, proof
    return "", []
