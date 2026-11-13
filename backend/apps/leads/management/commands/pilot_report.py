"""Pilot evaluation for Agent 2 runs: export a review sheet, then score the human labels.

  manage.py pilot_report export <task_id> pilot.csv     # one row per lead, label columns left blank
  manage.py pilot_report score pilot.csv                # after a human filled the label columns

Label columns (y / n / blank = not checked): business_real, website_correct, contact_correct, problems_true,
price_plausible, outreach_ok; opportunity = A (pursue) / B (maybe) / C (skip). Metrics are computed only over
rows a human actually labelled, and the count is shown next to every rate - nothing is inferred.
"""
import csv
from itertools import product

from django.core.management.base import BaseCommand, CommandError

from apps.leads.models import Lead, ProjectBrief
from apps.outreach.models import OutreachMessage

LABELS = ("business_real", "website_correct", "contact_correct", "problems_true", "price_plausible", "outreach_ok")
RANK = {"A": 3, "B": 2, "C": 1}
FIELDS = ("lead_id", "business", "category", "city", "website", "website_source", "listing_url", "contact_email",
          "phone", "status", "score", "shadow_score", "data_confidence", "problems", "est_revenue", "est_hours",
          "outreach_subject", *LABELS, "opportunity", "reviewer_notes")


def _rows(task_id):
    leads = (Lead.objects.filter(research_task_id=task_id).select_related("business")
             .order_by("-score", "business__name"))
    briefs = {b.lead_id: b for b in ProjectBrief.objects.filter(lead__in=leads)}
    subjects = dict(OutreachMessage.objects.filter(lead__in=leads).values_list("lead_id", "subject"))
    for lead in leads:
        b, sd = lead.business, lead.business.source_data or {}
        shadow, brief = sd.get("commercial_v1") or {}, briefs.get(lead.id)
        rev = (shadow.get("estimates") or {}).get("revenue") or {}
        yield {
            "lead_id": lead.id, "business": b.name, "category": b.category, "city": b.city, "website": b.website,
            "website_source": (sd.get("website_found") or {}).get("method", "listing" if b.website else ""),
            "listing_url": next((e.url for e in b.evidence.all() if e.url), ""),
            "contact_email": lead.contact_email, "phone": b.phone, "status": lead.status, "score": lead.score,
            "shadow_score": shadow.get("score", ""), "data_confidence": shadow.get("data_confidence", ""),
            "problems": "; ".join(p.get("code", "") for p in lead.problems),
            "est_revenue": f"{rev['min']:g}-{rev['max']:g} {rev['currency']}" if rev else
            (f"{brief.estimated_budget_min}-{brief.estimated_budget_max} {brief.currency}"
             if brief else ""),
            "est_hours": f"{brief.estimated_effort_hours_min}-{brief.estimated_effort_hours_max}" if brief else "",
            "outreach_subject": subjects.get(lead.id, ""),
        }


def score(rows: list[dict]) -> dict:
    """Rates over labelled rows only, plus ranking agreement of production vs shadow score with `opportunity`."""
    out = {}
    for col in LABELS:
        vals = [r[col].strip().lower() for r in rows if r.get(col, "").strip().lower() in ("y", "n")]
        out[col] = {"labelled": len(vals), "rate": round(vals.count("y") / len(vals), 3) if vals else None}
    ranked = [r for r in rows if r.get("opportunity", "").strip().upper() in RANK]
    for key in ("score", "shadow_score"):
        usable = [r for r in ranked if str(r.get(key, "")).strip() != ""]
        pairs = [(a, b) for a, b in product(usable, usable)
                 if RANK[a["opportunity"].strip().upper()] > RANK[b["opportunity"].strip().upper()]]
        hits = sum(float(a[key]) > float(b[key]) for a, b in pairs)
        out[f"ranking_{key}"] = {"pairs": len(pairs), "accuracy": round(hits / len(pairs), 3) if pairs else None}
    return out


class Command(BaseCommand):
    help = "Export an Agent 2 pilot review sheet (export) or score a labelled one (score)."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["export", "score"])
        parser.add_argument("arg1", help="task id (export) or labelled CSV (score)")
        parser.add_argument("arg2", nargs="?", help="output CSV (export)")

    def handle(self, action, arg1, arg2=None, **_):
        if action == "export":
            if not arg2:
                raise CommandError("export needs <task_id> <out.csv>")
            rows = list(_rows(arg1))
            with open(arg2, "w", newline="", encoding="utf-8-sig") as fh:  # BOM: Excel opens Cyrillic correctly
                w = csv.DictWriter(fh, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(rows)
            self.stdout.write(f"{len(rows)} leads written to {arg2}; fill the label columns, then run 'score'.")
            return
        with open(arg1, newline="", encoding="utf-8-sig") as fh:
            result = score(list(csv.DictReader(fh)))
        for k, v in result.items():
            self.stdout.write(f"{k:22} {v}")
