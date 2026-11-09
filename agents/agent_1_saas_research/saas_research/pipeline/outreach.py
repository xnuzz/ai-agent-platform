"""Step 5: sales offer + first-touch outreach drafts (one plain-text email per lead, sequence_step 1).

Bodies are sanitised: no signature / sign-off, no unsubscribe or opt-out text (the backend appends sender identity
and the unsubscribe footer), no placeholders. Agents never send — drafts go to the campaign approval gate.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..llm.base import LLMProvider, render_input
from ..schemas import MessageDrafts, OfferDraft
from .common import GROUNDING_RULES, squash, truncate
from .customers import Candidate, CustomerRequest

logger = logging.getLogger("saas_research.pipeline.outreach")

OFFER_SYSTEM = f"""You turn an approved software idea into a clear, honest B2B sales offer.
{GROUNDING_RULES}
- No invented customers, testimonials, statistics, discounts or deadlines.
- pricing: restate the idea's pricing model as an indicative offer (e.g. a pilot), or leave empty if none.
- call_to_action: one low-commitment next step (e.g. a 15-minute call)."""

MESSAGE_SYSTEM = f"""You write short, respectful first-contact B2B emails (plain text, under 150 words).
{GROUNDING_RULES}
- One email per lead_id. Personalise only with facts given for that lead (name, category, city, website).
- Do NOT add a greeting signature, sign-off, sender name, company footer, unsubscribe/opt-out text, links you were \
not given, or placeholders like [Name]. The platform appends sender identity and the opt-out footer.
- No false claims, no fake urgency, no pretending to be a customer or to know them personally.
- End with the call to action as a question."""

_SIGNOFF_RE = re.compile(
    r"^(best|best regards|kind regards|regards|warm regards|cheers|sincerely|yours sincerely|yours truly|thanks|"
    r"thank you|many thanks|all the best|with best regards|viele grüße|mit freundlichen grüßen|beste grüße|"
    r"liebe grüße|cordialement|bien à vous|saludos|un saludo|atentamente|cordiali saluti|distinti saluti|"
    r"met vriendelijke groet|с уважение|поздрави)\b[\s,.!]*$", re.I)
_OPTOUT_RE = re.compile(r"unsubscribe|opt[\s-]?out|abmelden|désabonner|darse de baja|\[[^\]]{1,40}\]", re.I)


@dataclass
class DraftMessage:
    lead_ref: str
    subject: str
    body: str
    language: str


def sanitize_body(body: str) -> str:
    """Strip opt-out lines, placeholder lines and a trailing sign-off block; normalise blank lines."""
    lines = [ln.rstrip() for ln in (body or "").replace("\r\n", "\n").split("\n")]
    lines = [ln for ln in lines if not _OPTOUT_RE.search(ln)]
    non_empty = [i for i, ln in enumerate(lines) if ln.strip()]
    for i in non_empty[-4:]:
        if _SIGNOFF_RE.match(lines[i].strip()):
            lines = lines[:i]
            break
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text[:20000]


def draft_offer(llm: LLMProvider, req: CustomerRequest) -> OfferDraft:
    payload = {"task": "draft_offer", "idea": req.idea_view(), "language": req.language, "user_notes": req.notes}
    offer = llm.generate(system=OFFER_SYSTEM, prompt=f"Draft the offer.\n{render_input(payload)}",
                         output_model=OfferDraft)
    return OfferDraft(headline=truncate(squash(offer.headline), 300),
                      value_proposition=truncate(offer.value_proposition.strip(), 5000),
                      pricing=truncate(squash(offer.pricing), 2000),
                      call_to_action=truncate(squash(offer.call_to_action), 500))


def draft_messages(llm: LLMProvider, req: CustomerRequest, offer: OfferDraft, leads: list[Candidate], *,
                   batch_size: int = 10, on_batch=None) -> list[DraftMessage]:
    out: list[DraftMessage] = []
    for start in range(0, len(leads), batch_size):
        chunk = leads[start:start + batch_size]
        ids = {f"L{start + i + 1}": c for i, c in enumerate(chunk)}
        payload = {"task": "draft_messages", "idea": req.idea_view(), "offer": offer.model_dump(),
                   "language": req.language, "user_notes": req.notes,
                   "leads": [{"lead_id": lid, "business_name": c.name, "category": c.category, "city": c.city,
                              "country_code": c.country_code, "website": c.website,
                              "why_relevant": c.fit_rationale} for lid, c in ids.items()]}
        drafts = llm.generate(system=MESSAGE_SYSTEM,
                              prompt=f"Write one email per lead_id.\n{render_input(payload)}",
                              output_model=MessageDrafts)
        done: set[str] = set()
        for d in drafts.messages:
            c = ids.get(d.lead_id.strip())
            if c is None or d.lead_id in done:
                continue
            body, subject = sanitize_body(d.body), truncate(squash(d.subject), 300)
            if not body or not subject:
                logger.info("dropping empty draft for %s", d.lead_id)
                continue
            done.add(d.lead_id)
            out.append(DraftMessage(lead_ref=c.lead_ref, subject=subject, body=body, language=req.language))
        missing = set(ids) - done
        if missing:
            logger.warning("model returned no usable draft for %d lead(s)", len(missing))
        if on_batch:
            on_batch(min(start + batch_size, len(leads)), len(leads))
    return out
