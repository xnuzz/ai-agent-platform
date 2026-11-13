"""Commercial lead assessment (v1, SHADOW): ranks opportunities by commercial value, not by problem count.

Runs next to `scoring.py` and does NOT change the production score/status yet; its result is attached to the
lead notes and `Business.source_data["commercial_v1"]` so it can be compared on real runs before it replaces
the ranking.

priority = need (0-45) + value (0-20) + contact (0-20) + legitimacy (0-15)            -> raw 0-100
           x (0.6 + 0.4 x data_confidence)                                             -> 0-100
  need       = sum of severity points (HIGH 15, MEDIUM 7, LOW 2) x confidence of that finding, capped
  value      = estimated project revenue midpoint / price of a typical 5-page site in that market, capped at 1
  contact    = generic business e-mail 20, other published e-mail 12, phone only 8, nothing 0
  legitimacy = listed street address 4, phone 4, live own website 4, opening hours / company details 3
  gate       = provider-reported closure caps the score (permanently 5, temporarily 30)

FACTS (measured or listed) are kept apart from ESTIMATES (derived from market rates and the brief's hours):
- revenue  = the quoted price range from briefs.py (hours x local market rate) — what the client would pay.
- dev_cost = hours x `cost_hourly_rate` (our own delivery cost). Not configured -> null; never guessed.
- profit   = revenue - dev_cost, only when dev_cost is known.
Win probability is unknown, so no "expected value" is produced.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .briefs import Estimate
from .contacts import ContactChoice
from .market import market_for
from .models import DiscoveredBusiness, Finding

VERSION = "commercial-v1"
SEVERITY_POINTS = {"HIGH": 15, "MEDIUM": 7, "LOW": 2}
NEED_CAP, VALUE_MAX = 45, 20
TYPICAL_SITE_HOURS = 50   # middle of a 5-page site incl. PM (briefs.py: ~37-62 h)

# How sure a finding is, given how it was established. Direct measurements are near-certain; heuristics and
# "absence" claims are not (a missing OSM website tag is weak evidence that no website exists).
FINDING_CONFIDENCE = {
    "NO_HTTPS": 0.95, "SSL_EXPIRED": 0.95, "SSL_INVALID_CERTIFICATE": 0.9, "SSL_EXPIRING_SOON": 0.95,
    "NO_HTTPS_REDIRECT": 0.9, "MIXED_CONTENT": 0.9, "WEBSITE_UNREACHABLE": 0.7, "SLOW_PAGE_LOAD": 0.7,
    "NOT_MOBILE_FRIENDLY": 0.85, "BROKEN_LINKS": 0.85, "OUTDATED_CMS": 0.8, "OUTDATED_DESIGN": 0.55,
    "MISSING_META": 0.9, "POOR_SEO": 0.7, "ACCESSIBILITY_ISSUES": 0.8, "SECURITY_HEADERS_MISSING": 0.9,
    "NO_ANALYTICS": 0.6, "NO_CONTACT_FORM": 0.6, "NO_ONLINE_BOOKING": 0.6, "FREE_SUBDOMAIN": 0.95,
    "SOCIAL_MEDIA_ONLY": 0.7, "PRICES_IN_BGN": 0.85, "MISSING_COMPANY_INFO": 0.6, "NO_PRIVACY_POLICY": 0.65,
}
NO_WEBSITE_CONFIDENCE = {"osm": 0.45, "google_places": 0.75}   # provider field completeness differs
NO_WEBSITE_SEARCHED_BONUS = 0.1                               # sitefinder looked and found nothing
STATUS_CAPS = {"CLOSED_PERMANENTLY": 5, "CLOSED_TEMPORARILY": 30}  # Google Places businessStatus


@dataclass
class Component:
    name: str
    points: float
    max: float
    reason: str


@dataclass
class CommercialAssessment:
    score: int
    data_confidence: float
    components: list[Component] = field(default_factory=list)
    finding_confidence: dict[str, float] = field(default_factory=dict)
    estimates: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"version": VERSION, "shadow": True, "score": self.score, "data_confidence": self.data_confidence,
                "components": [vars(c) for c in self.components], "finding_confidence": self.finding_confidence,
                "facts": self.facts, "estimates": self.estimates}

    def summary(self) -> str:
        parts = ", ".join(f"{c.name} {c.points:g}/{c.max:g}" for c in self.components)
        rev = self.estimates.get("revenue") or {}
        profit = self.estimates.get("profit")
        money = (f"; est. revenue {rev.get('min'):g}-{rev.get('max'):g} {rev.get('currency')}" if rev else "")
        money += (f", est. profit {profit['min']:g}-{profit['max']:g}" if profit else ", profit n/a (no cost rate)")
        return (f"Shadow commercial score {self.score}/100 ({parts}; data confidence {self.data_confidence:.2f})"
                f"{money}.")


def finding_confidence(f: Finding, b: DiscoveredBusiness, *, website_searched: bool) -> float:
    if f.code == "NO_WEBSITE":
        c = NO_WEBSITE_CONFIDENCE.get(b.provider, 0.5) + (NO_WEBSITE_SEARCHED_BONUS if website_searched else 0)
        return round(min(c, 0.95), 2)
    return FINDING_CONFIDENCE.get(f.code, 0.6)


def _complexity(hours_max: int) -> str:
    return "low" if hours_max <= 12 else "medium" if hours_max <= 40 else "high"


def assess(b: DiscoveredBusiness, findings: list[Finding], contact: ContactChoice | None, estimate: Estimate, *,
           scanned: bool, cost_hourly_rate: float = 0.0, website_searched: bool = False,
           company_info_found: bool = False) -> CommercialAssessment:
    comps: list[Component] = []

    # need: distinct codes, severity x confidence
    fconf: dict[str, float] = {}
    need = 0.0
    for f in findings:
        if f.code in fconf:
            continue
        fconf[f.code] = finding_confidence(f, b, website_searched=website_searched)
        need += SEVERITY_POINTS.get(f.severity, 0) * fconf[f.code]
    need = round(min(NEED_CAP, need), 1)
    comps.append(Component("need", need, NEED_CAP,
                           f"{len(fconf)} problem(s), severity x finding confidence" if fconf else "no problems found"))

    # value: project size vs a typical full site in the same market
    m = market_for(b.country_code)
    typical = TYPICAL_SITE_HOURS * m.hourly_rate
    mid = (estimate.budget_min + estimate.budget_max) / 2
    ratio = min(1.0, mid / typical) if typical and estimate.currency == m.currency else 0.0
    value = round(VALUE_MAX * ratio, 1)
    comps.append(Component("value", value, VALUE_MAX,
                           f"est. midpoint {mid:g} {estimate.currency} vs typical site {typical:g} {m.currency}"
                           if ratio else "no comparable market price"))

    # contactability
    phone = bool(b.phone.strip())
    if contact is not None and contact.email_type == "GENERIC_BUSINESS":
        cp, why = 20, "generic business e-mail"
    elif contact is not None:
        cp, why = 12, "published e-mail (not generic)"
    elif phone:
        cp, why = 8, "phone only"
    else:
        cp, why = 0, "no e-mail and no phone"
    comps.append(Component("contact", cp, 20, why))

    # legitimacy: listing completeness + live presence
    signals = {"street address": bool(b.address_line1.strip()), "phone": phone, "live own website": scanned,
               "opening hours / company details": bool(b.source_data.get("opening_hours")) or company_info_found
               or b.source_data.get("business_status") == "OPERATIONAL"}
    legit = 4 * signals["street address"] + 4 * phone + 4 * scanned + 3 * signals["opening hours / company details"]
    found = [k for k, v in signals.items() if v]
    comps.append(Component("legitimacy", legit, 15, ", ".join(found) or "listing name only"))

    # data confidence: mean confidence of findings, damped by listing completeness and site-matching method
    conf = (sum(fconf.values()) / len(fconf)) if fconf else 0.5
    if b.source_data.get("website_found", {}).get("method") == "domain_guess":
        conf -= 0.1
    if b.source_data.get("business_status") not in (None, "", "OPERATIONAL"):
        conf -= 0.3  # Google says closed (temporarily/permanently)
    conf = round(max(0.1, min(1.0, conf * (0.7 + 0.3 * len(found) / len(signals)))), 2)

    raw = need + value + cp + legit
    score = int(round(raw * (0.6 + 0.4 * conf)))
    cap = STATUS_CAPS.get(b.source_data.get("business_status") or "")
    if cap is not None and score > cap:  # provider says the business is closed: nobody to sell to
        comps.append(Component("closed_gate", cap - score, 0, f"listing status {b.source_data['business_status']}"))
        score = cap

    revenue = {"min": estimate.budget_min, "max": estimate.budget_max, "currency": estimate.currency,
               "basis": f"{estimate.hours_min}-{estimate.hours_max} h x market rate (briefs.py / market.py)"}
    dev_cost = profit = None
    if cost_hourly_rate > 0:
        dev_cost = {"min": round(estimate.hours_min * cost_hourly_rate, 2),
                    "max": round(estimate.hours_max * cost_hourly_rate, 2), "currency": estimate.currency,
                    "basis": f"hours x configured cost rate {cost_hourly_rate:g}/h"}
        # conservative band: lowest price with highest cost, and the reverse
        profit = {"min": round(estimate.budget_min - dev_cost["max"], 2),
                  "max": round(estimate.budget_max - dev_cost["min"], 2), "currency": estimate.currency}
    estimates = {"revenue": revenue, "dev_cost": dev_cost, "profit": profit,
                 "hours": {"min": estimate.hours_min, "max": estimate.hours_max},
                 "complexity": _complexity(estimate.hours_max), "approach": estimate.approach}
    facts = {"provider": b.provider, "has_email": contact is not None, "has_phone": phone,
             "website_scanned": scanned, "problem_codes": list(fconf)}
    return CommercialAssessment(score=max(0, min(100, score)), data_confidence=conf, components=comps,
                                finding_confidence=fconf, estimates=estimates, facts=facts)
