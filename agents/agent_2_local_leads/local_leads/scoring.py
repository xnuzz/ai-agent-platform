"""Deterministic, explainable lead scoring.

score = min(NEED_CAP, sum of problem weights)            (problems.py, one weight per distinct code)
      + contactability adjustment                          (generic e-mail +10, other e-mail +3, none -10,
                                                           no e-mail and no phone -30: nobody to contact)
clamped to 0..100. QUALIFIED iff score >= min_score, else DISQUALIFIED (still submitted).
The full breakdown is written to `qualification_notes`, so a reviewer can recompute every point.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contacts import ContactChoice
from .models import Finding
from .problems import spec

NEED_CAP = 85
CONTACT_POINTS = {"GENERIC_BUSINESS": 10, "UNKNOWN": 3}
NO_EMAIL_POINTS = -10
NO_CONTACT_POINTS = -30


@dataclass
class Assessment:
    score: int
    status: str                       # QUALIFIED | DISQUALIFIED
    breakdown: list[tuple[str, int]] = field(default_factory=list)
    notes: str = ""

    @property
    def qualified(self) -> bool:
        return self.status == "QUALIFIED"


def score_lead(findings: list[Finding], contact: ContactChoice | None, *, min_score: int,
               scan_note: str = "", has_phone: bool = True) -> Assessment:
    breakdown: list[tuple[str, int]] = []
    seen = set()
    for f in sorted(findings, key=lambda x: -spec(x.code).weight):
        if f.code not in seen:
            seen.add(f.code)
            breakdown.append((f.code, spec(f.code).weight))
    raw_need = sum(p for _, p in breakdown)
    need = min(NEED_CAP, raw_need)
    if contact is not None:
        adj_label, adj = f"contact: {contact.email_type.lower()} e-mail", CONTACT_POINTS.get(contact.email_type, 0)
    elif has_phone:
        adj_label, adj = "contact: no usable e-mail address (phone only)", NO_EMAIL_POINTS
    else:
        adj_label, adj = "contact: no e-mail and no phone", NO_CONTACT_POINTS
    score = max(0, min(100, need + adj))
    status = "QUALIFIED" if score >= min_score else "DISQUALIFIED"
    parts = ", ".join(f"{code} +{pts}" for code, pts in breakdown) or "no website problems found"
    cap = f" (capped at {NEED_CAP})" if raw_need > NEED_CAP else ""
    notes = (f"Score {score}/100 (threshold {min_score}) -> {status}. Problems: {parts}{cap}; "
             f"{adj_label} {adj:+d}.")
    if scan_note:
        notes += f" {scan_note}"
    return Assessment(score=score, status=status, breakdown=breakdown + [(adj_label, adj)], notes=notes)
