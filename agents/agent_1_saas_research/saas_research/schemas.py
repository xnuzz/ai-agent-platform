"""Structured LLM output schemas (pydantic). One model per pipeline step.

Kept free of open-ended dicts so they translate to strict JSON schemas (additionalProperties: false).
`*_id` / `source_ids` fields reference the short ids (S1, O2, L3 ...) the pipeline put into the prompt; the
pipeline drops anything that does not resolve to real retrieved evidence or known entities.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- opportunity research
class CompetitorMention(BaseModel):
    name: str = Field(max_length=200)
    source_id: str = Field("", description="Id of the source that mentions this competitor, or empty.")
    notes: str = Field("", max_length=1000)


class ProblemCandidate(BaseModel):
    title: str = Field(max_length=300)
    problem_statement: str = Field(max_length=4000)
    target_segment: str = Field("", max_length=300)
    pain_severity: int = Field(ge=1, le=5)
    source_ids: list[str] = Field(description="Ids of the sources that support this problem (S1, S2, ...).")
    competitors: list[CompetitorMention] = Field(default_factory=list)


class ProblemExtraction(BaseModel):
    problems: list[ProblemCandidate]


class DimensionRatings(BaseModel):
    pain: int = Field(ge=1, le=5)
    frequency: int = Field(ge=1, le=5)
    willingness_to_pay: int = Field(ge=1, le=5)
    competition_gap: int = Field(ge=1, le=5)
    feasibility: int = Field(ge=1, le=5)


class OpportunityRating(BaseModel):
    opportunity_id: str
    ratings: DimensionRatings
    rationale: str = Field(max_length=2000)


class OpportunityRatings(BaseModel):
    ratings: list[OpportunityRating]


class IdeaDraft(BaseModel):
    opportunity_id: str
    name: str = Field(max_length=200)
    summary: str = Field(max_length=2000)
    problem: str = Field("", max_length=4000)
    solution: str = Field("", max_length=4000)
    target_customers: str = Field("", max_length=1000)
    key_features: list[str] = Field(default_factory=list, max_length=12)
    pricing_model: str = Field("", max_length=500)
    differentiation: str = Field("", max_length=2000)
    risks: list[str] = Field(default_factory=list, max_length=10)
    mvp_scope: str = Field("", max_length=2000)
    idea_score: int = Field(ge=0, le=100, description="Your confidence that this idea is viable, 0-100.")
    source_ids: list[str] = Field(default_factory=list)


class IdeaDrafts(BaseModel):
    ideas: list[IdeaDraft]


# ---------------------------------------------------------------- customer research
class SearchQuery(BaseModel):
    query: str = Field(max_length=200)
    country_code: str = Field("", max_length=2, description="ISO-3166 alpha-2 or empty for global.")


class CustomerSearchPlan(BaseModel):
    queries: list[SearchQuery]


class BusinessAssessment(BaseModel):
    source_id: str
    is_individual_business: bool = Field(
        description="True only if the source is the website/listing of ONE specific business (not a list, "
                    "article, marketplace or directory overview).")
    business_name: str = Field("", max_length=300)
    category: str = Field("", max_length=200)
    city: str = Field("", max_length=120)
    fit_score: int = Field(ge=0, le=100)
    fit_rationale: str = Field("", max_length=1000)


class BusinessAssessments(BaseModel):
    assessments: list[BusinessAssessment]


class OfferDraft(BaseModel):
    headline: str = Field(max_length=300)
    value_proposition: str = Field(max_length=3000)
    pricing: str = Field("", max_length=1000)
    call_to_action: str = Field(max_length=500)


class MessageDraft(BaseModel):
    lead_id: str
    subject: str = Field(max_length=300)
    body: str = Field(max_length=8000)


class MessageDrafts(BaseModel):
    messages: list[MessageDraft]
