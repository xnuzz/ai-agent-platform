"""Deterministic template writer: the fallback when no LLM is configured or the LLM output is unusable.

Input is the same `facts` dict the LLM receives (writing.py). English only; the caller records when the
requested language differed so the reviewer knows.
"""
from __future__ import annotations

SUBJECTS = {
    "NO_WEBSITE": "A website for {name}?",
    "WEBSITE_UNREACHABLE": "{domain} is not loading at the moment",
    "SSL_EXPIRED": "The security certificate of {domain} has expired",
    "SSL_INVALID_CERTIFICATE": "Browsers show a certificate warning on {domain}",
    "NO_HTTPS": "Browsers mark {domain} as 'Not secure'",
    "NOT_MOBILE_FRIENDLY": "{domain} on mobile phones",
    "OUTDATED_CMS": "Software updates for {domain}",
}
APPROACH_TEXT = {
    "new_site": "a new mobile-first website",
    "relaunch": "relaunching the website on reliable hosting",
    "rebuild": "a modern rebuild of the website",
    "fixes": "a focused set of fixes",
}


def _money(estimate: dict) -> str:
    b = estimate["budget"]
    return f"{b['currency']} {b['min']:,.0f}-{b['max']:,.0f}"


def _first_sentence(text: str, limit: int = 220) -> str:
    s = (text or "").split(". ")[0].strip().rstrip(".")
    return (s[: limit - 1] + "…") if len(s) > limit else s


def brief_text(facts: dict) -> dict:
    b, est, problems = facts["business"], facts["estimate"], facts["problems"]
    name, approach = b["name"], est["approach"]
    title = {"new_site": f"New website for {name}", "relaunch": f"Website relaunch for {name}",
             "rebuild": f"Website rebuild for {name}"}.get(approach, f"Website improvements for {name}")
    where = ", ".join(p for p in (b.get("category"), b.get("city")) if p)
    if approach == "new_site":
        finding = "No website was found in the business listing."
    else:
        finding = (f"An automated scan of {b.get('website')} found {len(problems)} issue(s): "
                   + "; ".join(p["title"] for p in problems[:6]) + ".")
    summary = (f"{name}{f' ({where})' if where else ''}. {finding} Proposed: {APPROACH_TEXT[approach]}. "
               f"Estimated effort {est['hours']['min']}-{est['hours']['max']} hours, budget {_money(est)}.")
    solution = (f"Deliver {APPROACH_TEXT[approach]} that resolves the issues found:\n"
                + "\n".join(f"- {item}" for item in est["scope_items"])
                + f"\n\nSuggested stack: {', '.join(est['tech_stack']) or 'to be agreed with the client'}.")
    top = ", ".join(p["code"] for p in problems[:4]) or "none"
    approval = (f"Score {facts.get('score')}/100. Top issues: {top}. Estimate {est['hours']['min']}-"
                f"{est['hours']['max']} h / {_money(est)}.")
    return {"title": title[:120], "summary": summary, "proposed_solution": solution, "approval_summary": approval}


def outreach_text(facts: dict) -> dict:
    b, est, problems = facts["business"], facts["estimate"], facts["problems"]
    name = b["name"]
    domain = b.get("domain") or b.get("website") or name
    top = problems[0]["code"] if problems else ""
    subject = SUBJECTS.get(top, "A few technical notes about {domain}").format(name=name, domain=domain)
    category = (b.get("category") or "local").lower()
    city = b.get("city") or "your area"
    if est["approach"] == "new_site":
        body = (f"Hello {name} team,\n\n"
                f"I build websites for local businesses in {city}. While looking at {category} businesses in the "
                f"area I found {name} in a public business listing, but no website linked to it.\n\n"
                f"Many customers look a business up online before they call or visit. A simple, mobile-friendly "
                f"site with opening hours, services and a contact form usually helps with that.\n\n"
                f"I have outlined a small project ({est['hours']['min']}-{est['hours']['max']} hours, "
                f"estimated {_money(est)}). Would a short call or an e-mail with the details be useful?")
    else:
        lines = "\n".join(f"- {_first_sentence(p['description'])}." for p in problems[:4])
        body = (f"Hello {name} team,\n\n"
                f"I build and maintain websites for local businesses in {city}. While looking at {category} "
                f"businesses in the area, I ran a short automated check of {domain} and noticed a few technical "
                f"points:\n\n{lines}\n\n"
                f"These are common on sites that have been online for a while, and they can affect how visitors "
                f"and search engines see the site.\n\n"
                f"I have outlined how I would address them ({APPROACH_TEXT[est['approach']]}, estimated "
                f"{_money(est)}). Would a short call or an e-mail with the details be useful?")
    return {"subject": subject[:120], "body": body}
