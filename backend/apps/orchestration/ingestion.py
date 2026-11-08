"""Persists an agent ResultBundle into canonical backend entities.

Rules (docs/API_CONTRACTS.md §Agent result bundle):
- Whole bundle is atomic: any invalid reference -> 400, nothing persisted.
- `ref` is unique per (task, kind). Re-sent refs update the record only while it is still editable,
  otherwise they are reported under `skipped` (idempotent retries are safe).
- Sections allowed depend on the task type.
- Agents may *request* approval; they can never approve.
"""
from collections import Counter, defaultdict

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.common.actor import Actor
from apps.common.enums import ApprovalStatus, MessageStatus, TaskType
from apps.leads.models import Business, Lead, ProjectBrief
from apps.outreach.models import Campaign, OutreachMessage
from apps.research.models import Evidence, Opportunity, SoftwareIdea

from .models import ResearchTask, ResultRef

ALLOWED_SECTIONS = {
    TaskType.SAAS_OPPORTUNITY_RESEARCH: {"evidence", "opportunities", "software_ideas"},
    TaskType.SAAS_CUSTOMER_RESEARCH: {"evidence", "businesses", "leads", "campaigns"},
    TaskType.LOCAL_LEAD_DISCOVERY: {"evidence", "businesses", "leads", "project_briefs", "campaigns"},
}
SECTION_ORDER = ["evidence", "opportunities", "software_ideas", "businesses", "leads", "project_briefs",
                 "campaigns"]
KIND_MODEL = {"evidence": Evidence, "opportunities": Opportunity, "software_ideas": SoftwareIdea,
              "businesses": Business, "leads": Lead, "project_briefs": ProjectBrief, "campaigns": Campaign}


def _fill_blanks(obj, values: dict) -> list[str]:
    changed = []
    for k, v in values.items():
        if v not in (None, "", [], {}) and getattr(obj, k) in (None, "", [], {}):
            setattr(obj, k, v)
            changed.append(k)
    return changed


class Ingestor:
    def __init__(self, task: ResearchTask, actor: Actor):
        self.task, self.ws, self.actor = task, task.workspace, actor
        self.refs = {(r.kind, r.ref): r.object_id for r in task.result_refs.all()}
        self.created, self.updated = Counter(), Counter()
        self.skipped: list[dict] = []
        self.out_refs: dict[str, dict[str, str]] = defaultdict(dict)
        self.to_submit: list[tuple[object, str]] = []

    # ------------------------------------------------------------ helpers
    def _existing(self, kind, ref):
        oid = self.refs.get((kind, ref))
        return KIND_MODEL[kind].objects.get(pk=oid) if oid else None

    def _register(self, kind, ref, obj, created):
        if (kind, ref) not in self.refs:
            ResultRef.objects.create(task=self.task, kind=kind, ref=ref, object_id=obj.pk)
            self.refs[(kind, ref)] = obj.pk
        (self.created if created else self.updated)[kind] += 1
        self.out_refs[kind][ref] = str(obj.pk)

    def _skip(self, kind, ref, reason, obj=None):
        self.skipped.append({"kind": kind, "ref": ref, "reason": reason})
        if obj is not None:
            self.out_refs[kind][ref] = str(obj.pk)

    def _resolve(self, kind, ref, path):
        oid = self.refs.get((kind, ref))
        if oid is None:
            raise ValidationError({path: [f"Unknown {kind} ref '{ref}'."]})
        return KIND_MODEL[kind].objects.get(pk=oid)

    def _by_id(self, model, pk, path):
        obj = model.objects.filter(pk=pk, workspace=self.ws).first()
        if obj is None:
            raise ValidationError({path: [f"{model.__name__} {pk} not found in task workspace."]})
        return obj

    def _evidence(self, refs, path):
        return [self._resolve("evidence", r, path) for r in refs]

    def _problems(self, problems, path):
        out = []
        for i, p in enumerate(problems):
            ev = self._evidence(p.pop("evidence_refs", []), f"{path}[{i}].evidence_refs")
            out.append({**p, "evidence_ids": [str(e.pk) for e in ev]})
        return out

    # ------------------------------------------------------------ sections
    def evidence(self, items):
        for it in items:
            ref = it.pop("ref")
            if (obj := self._existing("evidence", ref)) is not None:
                self._skip("evidence", ref, "immutable", obj)
                continue
            obj = Evidence.objects.create(workspace=self.ws, research_task=self.task, **it)
            self._register("evidence", ref, obj, True)

    def opportunities(self, items):
        for i, it in enumerate(items):
            ref, ev = it.pop("ref"), self._evidence(it.pop("evidence_refs"), f"opportunities[{i}].evidence_refs")
            obj = self._existing("opportunities", ref)
            if obj is not None and obj.status != "NEW":
                self._skip("opportunities", ref, "not_editable", obj)
                continue
            created = obj is None
            obj = obj or Opportunity(workspace=self.ws, research_task=self.task)
            for k, v in it.items():
                setattr(obj, k, v)
            obj.save()
            obj.evidence.add(*ev)
            self._register("opportunities", ref, obj, created)

    def software_ideas(self, items):
        for i, it in enumerate(items):
            ref = it.pop("ref")
            ev = self._evidence(it.pop("evidence_refs"), f"software_ideas[{i}].evidence_refs")
            submit, summary = it.pop("submit_for_approval"), it.pop("approval_summary")
            opp_ref = it.pop("opportunity_ref", None)
            opp = self._resolve("opportunities", opp_ref, f"software_ideas[{i}].opportunity_ref") if opp_ref else None
            obj = self._existing("software_ideas", ref)
            if obj is not None and not obj.is_editable:
                self._skip("software_ideas", ref, "not_editable", obj)
                continue
            created = obj is None
            obj = obj or SoftwareIdea(workspace=self.ws, research_task=self.task)
            for k, v in it.items():
                setattr(obj, k, v)
            obj.opportunity = opp
            obj.save()
            obj.evidence.add(*ev)
            self._register("software_ideas", ref, obj, created)
            if submit:
                self.to_submit.append((obj, summary))

    def businesses(self, items):
        for i, it in enumerate(items):
            ref = it.pop("ref")
            ev = self._evidence(it.pop("evidence_refs"), f"businesses[{i}].evidence_refs")
            addr = it.pop("address") or {}
            values = {**it, "address_line1": addr.get("line1", ""), "city": addr.get("city", ""),
                      "region": addr.get("region", ""), "postal_code": addr.get("postal_code", ""),
                      "country_code": (addr.get("country_code") or "").upper()}
            obj = self._existing("businesses", ref)
            if obj is None:
                key = Business.build_dedupe_key(name=values["name"], website=values["website"],
                                                city=values["city"], country_code=values["country_code"])
                obj = Business.objects.filter(workspace=self.ws, dedupe_key=key).first()
                if obj is None:
                    obj = Business.objects.create(workspace=self.ws, first_seen_task=self.task, dedupe_key=key,
                                                  **values)
                    obj.evidence.add(*ev)
                    self._register("businesses", ref, obj, True)
                    continue
            if _fill_blanks(obj, values):
                obj.save()
            obj.evidence.add(*ev)
            self._register("businesses", ref, obj, False)

    def leads(self, items):
        software_idea = self.task.software_idea if self.task.task_type == TaskType.SAAS_CUSTOMER_RESEARCH else None
        for i, it in enumerate(items):
            path = f"leads[{i}]"
            ref = it.pop("ref")
            ev = self._evidence(it.pop("evidence_refs"), f"{path}.evidence_refs")
            business = (self._resolve("businesses", it["business_ref"], f"{path}.business_ref")
                        if it.get("business_ref") else self._by_id(Business, it["business_id"], f"{path}.business_id"))
            contact = it.pop("contact") or {}
            values = {
                "status": it["status"], "score": it.get("score"), "qualification_notes": it["qualification_notes"],
                "problems": self._problems(it["problems"], f"{path}.problems"),
                "contact_name": contact.get("name", ""), "contact_role": contact.get("role", ""),
                "contact_email": contact.get("email", ""), "contact_phone": contact.get("phone", ""),
                "contact_email_type": contact.get("email_type", "UNKNOWN"),
                "legal_basis": contact.get("legal_basis", "UNKNOWN"),
                "legal_basis_note": contact.get("legal_basis_note", ""),
            }
            obj = self._existing("leads", ref) or Lead.objects.filter(
                workspace=self.ws, business=business, source=self.task.agent, software_idea=software_idea).first()
            if obj is not None and obj.status not in Lead.AGENT_EDITABLE_STATES:
                self._register_quiet("leads", ref, obj)
                self._skip("leads", ref, "not_editable", obj)
                continue
            created = obj is None
            obj = obj or Lead(workspace=self.ws, business=business, source=self.task.agent,
                              software_idea=software_idea, research_task=self.task)
            for k, v in values.items():
                setattr(obj, k, v)
            obj.save()
            obj.evidence.add(*ev)
            self._register("leads", ref, obj, created)

    def _register_quiet(self, kind, ref, obj):
        if (kind, ref) not in self.refs:
            ResultRef.objects.create(task=self.task, kind=kind, ref=ref, object_id=obj.pk)
            self.refs[(kind, ref)] = obj.pk

    def _lead(self, it, path) -> Lead:
        if it.get("lead_ref"):
            return self._resolve("leads", it["lead_ref"], f"{path}.lead_ref")
        return self._by_id(Lead, it["lead_id"], f"{path}.lead_id")

    def project_briefs(self, items):
        for i, it in enumerate(items):
            path = f"project_briefs[{i}]"
            ref = it.pop("ref")
            ev = self._evidence(it.pop("evidence_refs"), f"{path}.evidence_refs")
            submit, summary = it.pop("submit_for_approval"), it.pop("approval_summary")
            lead = self._lead(it, path)
            effort, budget = it.pop("estimated_effort_hours") or {}, it.pop("estimated_budget") or {}
            values = {
                "title": it["title"], "summary": it["summary"],
                "problems": self._problems(it["problems"], f"{path}.problems"),
                "proposed_solution": it["proposed_solution"], "scope_items": it["scope_items"],
                "tech_stack": it["tech_stack"],
                "estimated_effort_hours_min": int(effort["min"]) if effort.get("min") is not None else None,
                "estimated_effort_hours_max": int(effort["max"]) if effort.get("max") is not None else None,
                "estimated_budget_min": budget.get("min"), "estimated_budget_max": budget.get("max"),
                "currency": (budget.get("currency") or "").upper(),
            }
            obj = self._existing("project_briefs", ref)
            if obj is not None and not obj.is_editable:
                self._skip("project_briefs", ref, "not_editable", obj)
                continue
            created = obj is None
            obj = obj or ProjectBrief(workspace=self.ws, research_task=self.task, lead=lead)
            for k, v in values.items():
                setattr(obj, k, v)
            obj.save()
            obj.evidence.add(*ev)
            self._register("project_briefs", ref, obj, created)
            if submit:
                self.to_submit.append((obj, summary))

    def campaigns(self, items):
        from apps.outreach.services import is_suppressed

        for i, it in enumerate(items):
            path = f"campaigns[{i}]"
            ref = it.pop("ref")
            submit, summary = it.pop("submit_for_approval"), it.pop("approval_summary")
            brief = None
            if it.get("project_brief_ref"):
                brief = self._resolve("project_briefs", it["project_brief_ref"], f"{path}.project_brief_ref")
            elif it.get("project_brief_id"):
                brief = self._by_id(ProjectBrief, it["project_brief_id"], f"{path}.project_brief_id")
            if brief is not None and self.task.task_type != TaskType.LOCAL_LEAD_DISCOVERY:
                raise ValidationError({path: ["project_brief is only valid for LOCAL_LEAD_DISCOVERY."]})

            obj = self._existing("campaigns", ref)
            if obj is not None and not obj.is_editable:
                self._skip("campaigns", ref, "not_editable", obj)
                continue
            created = obj is None
            if created:
                obj = Campaign.objects.create(
                    workspace=self.ws, research_task=self.task, source=self.task.agent, name=it["name"],
                    channel=it["channel"], offer=it["offer"], project_brief=brief,
                    software_idea=self.task.software_idea if self.task.task_type == TaskType.SAAS_CUSTOMER_RESEARCH
                    else None)
            else:
                obj.name, obj.offer = it["name"], it["offer"]
                obj.project_brief = brief or obj.project_brief
                obj.save()
            self._register("campaigns", ref, obj, created)

            for j, m in enumerate(it["messages"]):
                mpath = f"{path}.messages[{j}]"
                lead = self._lead(m, mpath)
                if obj.software_idea_id and lead.software_idea_id != obj.software_idea_id:
                    raise ValidationError({mpath: ["Lead does not belong to this campaign's software idea."]})
                mref = f"{ref}/{m.get('lead_ref') or m.get('lead_id')}/{m['sequence_step']}"
                to_email = lead.recipient_email
                if not to_email:
                    self._skip("messages", mref, "no_recipient")
                    continue
                if is_suppressed(self.ws.pk, email=to_email, phone=lead.contact_phone):
                    self._skip("messages", mref, "suppressed")
                    continue
                msg = OutreachMessage.objects.filter(campaign=obj, lead=lead,
                                                     sequence_step=m["sequence_step"]).first()
                if msg is not None and msg.status != MessageStatus.DRAFT:
                    self._skip("messages", mref, "not_editable", msg)
                    continue
                created_msg = msg is None
                msg = msg or OutreachMessage(workspace=self.ws, campaign=obj, lead=lead,
                                             sequence_step=m["sequence_step"], channel=obj.channel)
                msg.to_email, msg.subject, msg.body, msg.language = to_email, m["subject"], m["body"], m["language"]
                msg.save()
                (self.created if created_msg else self.updated)["messages"] += 1
                self.out_refs["messages"][mref] = str(msg.pk)
            if submit:
                self.to_submit.append((obj, summary))

    # ------------------------------------------------------------ run
    def run(self, bundle: dict) -> dict:
        allowed = ALLOWED_SECTIONS[self.task.task_type]
        bad = [s for s in SECTION_ORDER if bundle.get(s) and s not in allowed]
        if bad:
            raise ValidationError({s: [f"Not allowed for {self.task.task_type}."] for s in bad})
        approvals = []
        with transaction.atomic():
            for section in SECTION_ORDER:
                if bundle.get(section):
                    getattr(self, section)(bundle[section])
            approvals = self._submit_approvals()
        return {
            "created": dict(self.created), "updated": dict(self.updated), "skipped": self.skipped,
            "refs": dict(self.out_refs), "approvals_requested": approvals,
        }

    def _submit_approvals(self):
        from apps.approvals.models import Approval
        from apps.approvals.services import request_approval, target_type_of

        out = []
        for obj, summary in self.to_submit:
            obj.refresh_from_db()
            pending = Approval.objects.filter(target_type=target_type_of(obj), target_id=obj.pk,
                                              status=ApprovalStatus.PENDING).first()
            if pending:
                out.append({"target_type": pending.target_type, "target_id": str(obj.pk),
                            "approval_id": str(pending.pk), "status": "ALREADY_PENDING"})
                continue
            if not obj.is_editable:
                continue
            if isinstance(obj, Campaign) and not obj.messages.filter(status=MessageStatus.DRAFT).exists():
                self._skip("campaigns", str(obj.pk), "no_messages_to_approve", obj)
                continue
            a = request_approval(obj, actor=self.actor, research_task=self.task, summary=summary)
            out.append({"target_type": a.target_type, "target_id": str(obj.pk), "approval_id": str(a.pk),
                        "status": "PENDING"})
        return out
