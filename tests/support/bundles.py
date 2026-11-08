"""Example result bundles (schema v1.0). MOCK data, no Django dependency.

These are executable contract examples for Team 1 / Team 2: the backend test-suite asserts they are accepted.
"""


def opportunity_bundle(submit=True):
    return {
        "schema_version": "1.0",
        "evidence": [
            {"ref": "ev1", "url": "https://forum.example.com/t/123", "title": "Dentists hate scheduling",
             "source_type": "FORUM", "excerpt": "We lose 10 hours a week on manual rescheduling."},
            {"ref": "ev2", "url": "https://reviews.example.com/app/1", "source_type": "REVIEW",
             "excerpt": "Existing tool is too expensive for small clinics."},
        ],
        "opportunities": [
            {"ref": "op1", "title": "Manual appointment rescheduling in small dental clinics",
             "problem_statement": "Small clinics reschedule by phone.", "industry": "Dental",
             "target_segment": "1-5 chair clinics", "pain_severity": 4, "score": 78,
             "competitors": [{"name": "BigDentSuite", "url": "https://bigdent.example.com", "notes": "Pricey"}],
             "evidence_refs": ["ev1", "ev2"]},
        ],
        "software_ideas": [
            {"ref": "idea1", "opportunity_ref": "op1", "name": "ChairFill",
             "summary": "SMS waitlist that auto-fills cancelled dental slots.", "key_features": ["Waitlist", "SMS"],
             "pricing_model": "EUR 49/month per clinic", "score": 81, "evidence_refs": ["ev1"],
             "submit_for_approval": submit, "approval_summary": "Strong pain signal, weak competition."},
        ],
    }


def customer_bundle(submit=True, legal_basis="LEGITIMATE_INTEREST", email="info@smile-dental.test"):
    return {
        "schema_version": "1.0",
        "evidence": [{"ref": "ev1", "url": "https://maps.example.com/smile", "source_type": "DIRECTORY"}],
        "businesses": [
            {"ref": "b1", "name": "Smile Dental", "website": "https://www.smile-dental.test", "email": email,
             "address": {"city": "Sofia", "country_code": "bg"}, "category": "Dentist", "evidence_refs": ["ev1"]},
        ],
        "leads": [
            {"ref": "l1", "business_ref": "b1", "status": "QUALIFIED", "score": 70,
             "qualification_notes": "3 chairs, online booking missing.",
             "contact": {"email": email, "email_type": "GENERIC_BUSINESS", "legal_basis": legal_basis}},
        ],
        "campaigns": [
            {"ref": "c1", "name": "ChairFill pilot - Sofia",
             "offer": {"headline": "Fill cancelled slots automatically", "call_to_action": "15-min call?"},
             "messages": [{"lead_ref": "l1", "subject": "Cancelled appointments at Smile Dental",
                           "body": "Hi Smile Dental team, ..."}],
             "submit_for_approval": submit},
        ],
    }


def local_leads_bundle(submit=True):
    return {
        "schema_version": "1.0",
        "evidence": [{"ref": "scan1", "url": "http://bakery.test", "source_type": "WEBSITE_SCAN",
                      "excerpt": "No TLS; 7.9s LCP on mobile."}],
        "businesses": [
            {"ref": "b1", "name": "Corner Bakery", "website": "http://bakery.test", "email": "hello@bakery.test",
             "phone": "+359 2 123 456", "address": {"line1": "5 Main St", "city": "Plovdiv", "country_code": "BG"},
             "category": "Bakery", "evidence_refs": ["scan1"]},
        ],
        "leads": [
            {"ref": "l1", "business_ref": "b1", "status": "QUALIFIED", "score": 82,
             "problems": [{"code": "NO_HTTPS", "title": "Site served over HTTP", "severity": "HIGH",
                           "evidence_refs": ["scan1"]},
                          {"code": "SLOW_PAGE_LOAD", "title": "Slow mobile load", "severity": "MEDIUM"}],
             "contact": {"email": "hello@bakery.test", "email_type": "GENERIC_BUSINESS",
                         "legal_basis": "LEGITIMATE_INTEREST"}},
        ],
        "project_briefs": [
            {"ref": "pb1", "lead_ref": "l1", "title": "Secure, fast website for Corner Bakery",
             "summary": "Migrate to HTTPS, rebuild as static site with online pre-orders.",
             "scope_items": ["TLS", "Static rebuild", "Pre-order form"],
             "estimated_effort_hours": {"min": 20, "max": 35},
             "estimated_budget": {"min": 900, "max": 1500, "currency": "eur"},
             "evidence_refs": ["scan1"], "submit_for_approval": submit},
        ],
        "campaigns": [
            {"ref": "c1", "name": "Corner Bakery website offer", "project_brief_ref": "pb1",
             "messages": [{"lead_ref": "l1", "subject": "Your website shows a security warning",
                           "body": "Hello Corner Bakery, ..."}],
             "submit_for_approval": submit},
        ],
    }
