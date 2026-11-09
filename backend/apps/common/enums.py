"""Canonical enumerations shared by backend, frontend and agents.

These string values ARE the contract (docs/WORKFLOWS.md, docs/API_CONTRACTS.md).
Never rename a value without a documented breaking-change entry in docs/DECISIONS.md.
"""
from django.db import models


class AgentType(models.TextChoices):
    SAAS_RESEARCH = "SAAS_RESEARCH", "Agent 1 - SaaS Opportunity Research"
    LOCAL_LEADS = "LOCAL_LEADS", "Agent 2 - Local Business Lead Finder"


class SourceType(models.TextChoices):
    """Who produced a record."""
    SAAS_RESEARCH = "SAAS_RESEARCH", "Agent 1"
    LOCAL_LEADS = "LOCAL_LEADS", "Agent 2"
    MANUAL = "MANUAL", "Manual (user)"


class TaskType(models.TextChoices):
    SAAS_OPPORTUNITY_RESEARCH = "SAAS_OPPORTUNITY_RESEARCH", "Agent 1: opportunity research"
    SAAS_CUSTOMER_RESEARCH = "SAAS_CUSTOMER_RESEARCH", "Agent 1: customer research + outreach prep"
    LOCAL_LEAD_DISCOVERY = "LOCAL_LEAD_DISCOVERY", "Agent 2: local lead discovery + brief + outreach prep"


TASK_TYPE_AGENT: dict[str, str] = {
    TaskType.SAAS_OPPORTUNITY_RESEARCH: AgentType.SAAS_RESEARCH,
    TaskType.SAAS_CUSTOMER_RESEARCH: AgentType.SAAS_RESEARCH,
    TaskType.LOCAL_LEAD_DISCOVERY: AgentType.LOCAL_LEADS,
}


class TaskStatus(models.TextChoices):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewStatus(models.TextChoices):
    """Lifecycle for reviewable artifacts: SoftwareIdea, ProjectBrief."""
    DRAFT = "DRAFT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class OpportunityStatus(models.TextChoices):
    NEW = "NEW"
    SHORTLISTED = "SHORTLISTED"
    DISMISSED = "DISMISSED"


class LeadStatus(models.TextChoices):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    WON = "WON"
    LOST = "LOST"
    ARCHIVED = "ARCHIVED"


class CampaignStatus(models.TextChoices):
    DRAFT = "DRAFT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MessageStatus(models.TextChoices):
    DRAFT = "DRAFT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    CANCELLED = "CANCELLED"


class ApprovalDecision(models.TextChoices):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ApprovalTargetType(models.TextChoices):
    SOFTWARE_IDEA = "SOFTWARE_IDEA"
    PROJECT_BRIEF = "PROJECT_BRIEF"
    CAMPAIGN = "CAMPAIGN"


class Channel(models.TextChoices):
    EMAIL = "EMAIL"  # only channel the backend can execute in v1


class LegalBasis(models.TextChoices):
    LEGITIMATE_INTEREST = "LEGITIMATE_INTEREST"
    CONSENT = "CONSENT"
    UNKNOWN = "UNKNOWN"


class ContactEmailType(models.TextChoices):
    GENERIC_BUSINESS = "GENERIC_BUSINESS"  # info@, office@ ...
    PERSONAL_WORK = "PERSONAL_WORK"  # firstname.lastname@ -> personal data under GDPR
    UNKNOWN = "UNKNOWN"


class SuppressionType(models.TextChoices):
    EMAIL = "EMAIL"
    DOMAIN = "DOMAIN"
    PHONE = "PHONE"


class SuppressionReason(models.TextChoices):
    OPT_OUT = "OPT_OUT"
    BOUNCE = "BOUNCE"
    COMPLAINT = "COMPLAINT"
    LEGAL_REQUEST = "LEGAL_REQUEST"
    MANUAL = "MANUAL"


class SuppressionSource(models.TextChoices):
    USER = "USER"
    UNSUBSCRIBE_LINK = "UNSUBSCRIBE_LINK"
    SYSTEM = "SYSTEM"


class Role(models.TextChoices):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"


ROLE_RANK = {Role.VIEWER: 0, Role.DEVELOPER: 1, Role.ADMIN: 2, Role.OWNER: 3}


class ActorType(models.TextChoices):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class EvidenceSourceType(models.TextChoices):
    WEB_PAGE = "WEB_PAGE"
    SEARCH_RESULT = "SEARCH_RESULT"
    REVIEW = "REVIEW"
    FORUM = "FORUM"
    DIRECTORY = "DIRECTORY"
    SOCIAL = "SOCIAL"
    API = "API"
    DOCUMENT = "DOCUMENT"
    WEBSITE_SCAN = "WEBSITE_SCAN"
    OTHER = "OTHER"


class IntegrationKind(models.TextChoices):
    EMAIL = "EMAIL"
    LLM = "LLM"
    SEARCH = "SEARCH"
    MAPS = "MAPS"
    CRM = "CRM"


class IntegrationProvider(models.TextChoices):
    SMTP = "SMTP"
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GOOGLE_PLACES = "GOOGLE_PLACES"
    SERPAPI = "SERPAPI"
    HUBSPOT = "HUBSPOT"
    OTHER = "OTHER"


class IntegrationStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"
