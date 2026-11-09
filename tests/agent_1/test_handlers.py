"""Handlers with a fake TaskContext: stages, batching, input handling, suppression, cancellation, error mapping."""
import pytest

from agent_1.fakes import FakeCtx
from platform_sdk import RetryableError, TaskCancelled
from saas_research.errors import InvalidTaskInput, ProviderTransientError
from saas_research.handlers import Agent1Handlers, PipelineOptions, Providers
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.schemas import ProblemExtraction
from saas_research.sources.fake import FakePageFetcher, FakeSearchProvider

IDEA = {"id": "11111111-1111-1111-1111-111111111111", "name": "ChairFill", "status": "APPROVED",
        "target_customers": "small dental clinics"}
RECOMMENDED_STAGES = {"PLANNING", "SEARCHING", "ANALYZING_COMPETITORS", "SCORING", "GENERATING_IDEAS",
                      "FINDING_CUSTOMERS", "DRAFTING_OUTREACH", "SUBMITTING"}


def make(llm=None, search=None, fetcher=None, **opts):
    llm, search, fetcher = llm or FakeLLMProvider(), search or FakeSearchProvider(), fetcher or FakePageFetcher()
    return Agent1Handlers(Providers(llm, search, fetcher), PipelineOptions(**opts)), llm, search, fetcher


def customer_ctx(**inp):
    return FakeCtx("SAAS_CUSTOMER_RESEARCH", {"software_idea_id": IDEA["id"], **inp},
                   {"software_idea": IDEA, "opportunity": {"title": "Cancelled slots", "industry": "Dental"}})


def test_handler_mapping():
    h, *_ = make()
    assert set(h.as_dict()) == {"SAAS_OPPORTUNITY_RESEARCH", "SAAS_CUSTOMER_RESEARCH"}


def test_opportunity_research_stages_inputs_and_summary():
    h, llm, search, _ = make()
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "Dental clinics", "regions": ["BG", "DE"],
                                                "keywords": ["no-shows"], "customer_segment": "SMB",
                                                "max_opportunities": 2, "max_ideas": 1, "language": "de",
                                                "notes": "focus on small practices"})
    summary = h.opportunity_research(ctx)
    stages = ctx.stages
    assert stages[0] == "PLANNING" and stages[-1] == "SUBMITTING" and set(stages) <= RECOMMENDED_STAGES
    assert stages.index("SEARCHING") < stages.index("ANALYZING_COMPETITORS") < stages.index("SCORING") \
        < stages.index("GENERATING_IDEAS")
    progress = [p for p, *_ in ctx.progress_calls]
    assert progress == sorted(progress)
    assert {c["country"] for c in search.calls} == {"BG", "DE"} and all(c["language"] == "de" for c in search.calls)
    assert any("no-shows" in c["query"] for c in search.calls)
    first = llm.calls[0]["input"]
    assert first["user_notes"] == "focus on small practices" and first["language"] == "de"
    assert summary["opportunities"] == len(ctx.section("opportunities")) <= 2
    assert summary["ideas"] == len(ctx.section("software_ideas")) == 1
    assert len(ctx.bundles) >= 2  # evidence/opportunities batch(es) before ideas


def test_batches_respect_batch_size():
    h, *_ = make(batch_size=2)
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "x", "max_opportunities": 5, "max_ideas": 3})
    h.opportunity_research(ctx)
    assert all(len(b[s]) <= 2 for b in ctx.bundles for s in ("evidence", "opportunities", "software_ideas"))


def test_no_sources_completes_without_submitting():
    class Empty:
        name = "empty"

        def search(self, *a, **k):
            return []

    h, llm, *_ = make(search=Empty())
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "x"})
    assert h.opportunity_research(ctx)["opportunities"] == 0 and ctx.bundles == [] and llm.calls == []


def test_unsupported_llm_output_yields_no_opportunities():
    llm = FakeLLMProvider(responders={ProblemExtraction: lambda d: ProblemExtraction(problems=[])})
    h, *_ = make(llm=llm)
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "x"})
    assert h.opportunity_research(ctx)["opportunities"] == 0 and ctx.section("opportunities") == []


def test_customer_research_flow_respects_inputs():
    h, llm, search, fetcher = make()
    ctx = customer_ctx(max_leads=3, regions=["BG"], language="bg")
    summary = h.customer_research(ctx)
    assert ctx.stages[0] == "PLANNING" and set(ctx.stages) <= RECOMMENDED_STAGES
    assert ctx.stages.index("FINDING_CUSTOMERS") < ctx.stages.index("DRAFTING_OUTREACH")
    assert all(c["country"] == "BG" and c["language"] == "bg" for c in search.calls)
    assert llm.calls[0]["input"]["idea"]["name"] == "ChairFill"
    assert llm.calls[0]["input"]["idea"]["opportunity"]["title"] == "Cancelled slots"
    leads = ctx.section("leads")
    assert summary["leads"] == len(leads) <= 3 and summary["messages"] == len(ctx.section("campaigns")[0]["messages"])
    # suppression checked BEFORE any lead or campaign is submitted
    assert ctx.suppression_checks and sorted(ctx.suppression_checks[0]) == sorted(
        lead["contact"]["email"] for lead in leads)
    assert all(m["language"] == "bg" for m in ctx.section("campaigns")[0]["messages"])


def test_suppressed_recipients_are_excluded():
    h, *_ = make()
    first = customer_ctx(max_leads=3)
    h.customer_research(first)
    victim = first.section("leads")[0]["contact"]["email"]
    ctx = customer_ctx(max_leads=3)
    ctx.suppressed = {victim}
    summary = make()[0].customer_research(ctx)
    assert victim not in [lead["contact"]["email"] for lead in ctx.section("leads")]
    assert summary["suppressed_skipped"] == 1


def test_customer_research_without_email_channel_skips_campaign():
    h, *_ = make()
    ctx = customer_ctx(channels=[])
    ctx.task.input["channels"] = ["SMS"]
    summary = h.customer_research(ctx)
    assert ctx.section("campaigns") == [] and summary["messages"] == 0 and ctx.section("leads")


def test_customer_research_requires_approved_idea_context():
    h, *_ = make()
    with pytest.raises(InvalidTaskInput):
        h.customer_research(FakeCtx("SAAS_CUSTOMER_RESEARCH", {"software_idea_id": IDEA["id"]}, {}))


def test_cancellation_propagates():
    h, *_ = make()
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "x"}, cancel_at_stage="SCORING")
    with pytest.raises(TaskCancelled):
        h.opportunity_research(ctx)
    assert ctx.section("opportunities") == []


def test_provider_outage_is_retryable_for_the_sdk():
    class Down:
        name = "down"

        def search(self, *a, **k):
            raise ProviderTransientError("429")

    h, *_ = make(search=Down())
    with pytest.raises(RetryableError):
        h.opportunity_research(FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "x"}))
