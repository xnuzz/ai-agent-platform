"""Deterministic project estimate for a qualified lead: approach, scope items, tech stack, hours, budget.

Rules (all traceable to problems.py):
- NO_WEBSITE -> new site; WEBSITE_UNREACHABLE -> relaunch;
- >=2 rebuild triggers (mobile / design / CMS) or >=6 distinct problems -> rebuild (covers most fixes);
- otherwise one fix item per problem.
Plus project management/QA (15 %, min 2 h). Budget = hours x hourly rate, rounded to 50.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import Finding
from .problems import REBUILD_TRIGGERS, spec

REBUILD_ITEM = "Rebuild the website as a modern, responsive and secure site (content migration included)"
REBUILD_HOURS = (30, 60)
REBUILD_TECH = ("Modern CMS or static site generator", "Managed hosting with automatic TLS")


@dataclass
class Estimate:
    approach: str                       # new_site | relaunch | rebuild | fixes
    scope_items: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    hours_min: int = 0
    hours_max: int = 0
    budget_min: float = 0
    budget_max: float = 0
    currency: str = "EUR"

    def as_facts(self) -> dict:
        return {"approach": self.approach, "scope_items": self.scope_items, "tech_stack": self.tech_stack,
                "hours": {"min": self.hours_min, "max": self.hours_max},
                "budget": {"min": self.budget_min, "max": self.budget_max, "currency": self.currency}}


def _round50(x: float) -> float:
    return float(int(math.ceil(x / 50.0)) * 50)


def build_estimate(findings: list[Finding], *, hourly_rate: float, currency: str = "EUR", cms: str = ""
                   ) -> Estimate:
    codes = list(dict.fromkeys(f.code for f in findings))
    items: list[tuple[str, tuple[int, int]]] = []
    tech: list[str] = []

    def add(item: str, hours: tuple[int, int], stack=()):
        if item not in (i for i, _ in items):
            items.append((item, hours))
        tech.extend(t for t in stack if t not in tech)

    if "NO_WEBSITE" in codes:
        approach = "new_site"
        add(spec("NO_WEBSITE").scope_item, spec("NO_WEBSITE").hours, spec("NO_WEBSITE").tech)
        add("Contact form and click-to-call", (2, 4))
    elif "WEBSITE_UNREACHABLE" in codes:
        approach = "relaunch"
        s = spec("WEBSITE_UNREACHABLE")
        add(s.scope_item, s.hours, s.tech)
    elif len(REBUILD_TRIGGERS.intersection(codes)) >= 2 or len(codes) >= 6:
        approach = "rebuild"
        add(REBUILD_ITEM, REBUILD_HOURS, REBUILD_TECH)
        for code in codes:
            s = spec(code)
            if not s.rebuild_covers:
                add(s.scope_item, s.hours, s.tech)
    else:
        approach = "fixes"
        for code in codes:
            s = spec(code)
            add(s.scope_item, s.hours, s.tech)
            if code == "OUTDATED_CMS" and cms:
                tech.append(f"{cms} (current supported version)")
    if not items:
        add("Technical website review and quick fixes", (2, 4))
    hmin = sum(h[0] for _, h in items)
    hmax = sum(h[1] for _, h in items)
    pm = (max(2, round(hmin * 0.15)), max(2, round(hmax * 0.15)))
    items.append(("Project management, testing and handover", pm))
    hmin, hmax = hmin + pm[0], hmax + pm[1]
    return Estimate(approach=approach, scope_items=[i for i, _ in items], tech_stack=tech, hours_min=hmin,
                    hours_max=hmax, budget_min=_round50(hmin * hourly_rate), budget_max=_round50(hmax * hourly_rate),
                    currency=(currency or "EUR").upper()[:3])
