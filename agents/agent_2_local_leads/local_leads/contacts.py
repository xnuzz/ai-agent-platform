"""Contact selection: prefer generic business addresses, never keep personal ones, set an honest legal basis.

Data minimisation: addresses that look personal (firstname.lastname@) are discarded, not stored.
Legal basis is an *agent assessment* for the reviewer, not legal advice; the backend still enforces
suppression, consent-required countries and blocks `UNKNOWN`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

GENERIC_LOCALPARTS = {
    "info", "office", "contact", "contacts", "hello", "hi", "mail", "email", "kontakt", "team", "reception",
    "booking", "bookings", "book", "reservations", "reservation", "reserve", "enquiries", "enquiry", "inquiries",
    "inquiry", "sales", "service", "services", "support", "studio", "shop", "store", "orders", "order", "welcome",
    "post", "office1", "hola", "ciao", "bonjour", "praxis", "clinic", "salon", "admin", "general", "front",
    "frontdesk", "appointments", "appointment", "termin", "termine", "help", "customerservice", "kundenservice",
}
EXCLUDED_LOCALPARTS = {"noreply", "no-reply", "donotreply", "do-not-reply", "postmaster", "abuse", "webmaster",
                       "hostmaster", "privacy", "dpo", "gdpr", "dsgvo", "datenschutz", "unsubscribe", "bounce",
                       "mailer-daemon", "security", "legal", "jobs", "careers", "press", "invoice", "billing"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,190}\.[a-z]{2,24}$")
PERSONAL_RE = re.compile(r"^[a-z]{2,}[._-][a-z]{2,}$|^[a-z][._-][a-z]{2,}$")


@dataclass
class ContactChoice:
    email: str
    email_type: str          # GENERIC_BUSINESS | UNKNOWN   (PERSONAL_WORK is never selected)
    legal_basis: str         # LEGITIMATE_INTEREST | UNKNOWN
    legal_basis_note: str
    source: str              # where the address was published


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if len(t) >= 4}


def classify_email(email: str, business_name: str = "") -> str:
    """GENERIC_BUSINESS | PERSONAL_WORK | UNKNOWN | EXCLUDED."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return "EXCLUDED"
    local = email.split("@", 1)[0]
    base = re.sub(r"\d+$", "", local)
    if local in EXCLUDED_LOCALPARTS or base in EXCLUDED_LOCALPARTS:
        return "EXCLUDED"
    if local in GENERIC_LOCALPARTS or base in GENERIC_LOCALPARTS:
        return "GENERIC_BUSINESS"
    squashed = re.sub(r"[^a-z0-9]", "", local)
    if any(tok in squashed for tok in _name_tokens(business_name)):
        return "GENERIC_BUSINESS"     # e.g. cornerbakery@ for "Corner Bakery"
    if PERSONAL_RE.match(local):
        return "PERSONAL_WORK"
    return "UNKNOWN"


def _domain(value: str) -> str:
    v = (value or "").lower()
    v = v.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return v[4:] if v.startswith("www.") else v


def choose_contact(candidates: list[tuple[str, str]], *, business_name: str, website: str = "",
                   country_code: str = "") -> ContactChoice | None:
    """candidates: [(email, source description)] in provider-then-website order."""
    site = _domain(website)
    ranked = []
    for idx, (email, source) in enumerate(candidates):
        email = (email or "").strip().lower()
        kind = classify_email(email, business_name)
        if kind in ("EXCLUDED", "PERSONAL_WORK"):
            continue
        on_site = bool(site) and email.endswith("@" + site)
        ranked.append((kind != "GENERIC_BUSINESS", not on_site, idx, email, kind, source))
    if not ranked:
        return None
    *_, email, kind, source = min(ranked)
    if kind == "GENERIC_BUSINESS":
        return ContactChoice(
            email=email, email_type=kind, legal_basis="LEGITIMATE_INTEREST", source=source,
            legal_basis_note=(f"Generic business address published by the business ({source}). B2B contact about "
                              f"publicly observable website issues relevant to its business; one message, opt-out "
                              f"footer added by the platform. Agent assessment, not legal advice - confirm the "
                              f"rules for {country_code or 'the recipient country'} before sending."))
    return ContactChoice(
        email=email, email_type="UNKNOWN", legal_basis="UNKNOWN", source=source,
        legal_basis_note=(f"Address found at {source} but it is unclear whether it is a role address or belongs to "
                          f"a person; a human must confirm the legal basis before any outreach (sending is blocked "
                          f"while UNKNOWN)."))
