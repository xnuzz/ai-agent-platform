import csv

import pytest
from django.core.management import call_command

from apps.leads.management.commands.pilot_report import score
from support.bundles import local_leads_bundle

from .conftest import LOCAL_INPUT

pytestmark = pytest.mark.django_db


def test_export_then_score_only_counts_labelled_rows(create_task, agent2, claim, tmp_path):
    task_id = create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)["id"]
    claim(agent2).results(local_leads_bundle())
    out = tmp_path / "pilot.csv"
    call_command("pilot_report", "export", task_id, str(out))
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 1 and rows[0]["business"] and rows[0]["business_real"] == ""
    assert rows[0]["outreach_subject"].startswith("Търговско предложение")

    labelled = [{"business_real": "y", "website_correct": "n", "opportunity": "A", "score": "80", "shadow_score": "70"},
                {"business_real": "y", "website_correct": "", "opportunity": "C", "score": "90", "shadow_score": "20"},
                {"business_real": "n", "opportunity": "", "score": "10", "shadow_score": "5"}]
    r = score(labelled)
    assert r["business_real"] == {"labelled": 3, "rate": 0.667}
    assert r["website_correct"] == {"labelled": 1, "rate": 0.0}
    assert r["contact_correct"] == {"labelled": 0, "rate": None}          # nothing labelled -> no number
    assert r["ranking_score"] == {"pairs": 1, "accuracy": 0.0}
    assert r["ranking_shadow_score"] == {"pairs": 1, "accuracy": 1.0}
