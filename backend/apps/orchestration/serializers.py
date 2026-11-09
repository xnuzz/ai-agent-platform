from rest_framework import serializers

from apps.common.enums import TaskType
from apps.research.serializers import OpportunitySerializer, SoftwareIdeaSerializer

from .bundle import ResultBundle  # noqa: F401  (re-exported for schema generation)
from .models import ResearchTask

TASK_FIELDS = ("id", "agent", "task_type", "status", "input", "priority", "parent_task", "software_idea",
               "progress", "stage", "progress_message", "attempt", "max_attempts", "cancel_requested",
               "error", "result_summary", "started_at", "finished_at", "heartbeat_at", "created_by",
               "created_at", "updated_at")


class ResearchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchTask
        fields = TASK_FIELDS
        read_only_fields = TASK_FIELDS


class ResearchTaskDetailSerializer(ResearchTaskSerializer):
    result_counts = serializers.SerializerMethodField()

    class Meta(ResearchTaskSerializer.Meta):
        fields = TASK_FIELDS + ("result_counts",)
        read_only_fields = fields

    def get_result_counts(self, obj) -> dict:
        return {
            "evidence": obj.evidence.count(), "opportunities": obj.opportunities.count(),
            "software_ideas": obj.software_ideas.count(), "leads": obj.leads.count(),
            "project_briefs": obj.project_briefs.count(), "campaigns": obj.campaigns.count(),
            "approvals": obj.approvals.count(),
        }


class ResearchTaskCreateSerializer(serializers.Serializer):
    task_type = serializers.ChoiceField(choices=TaskType.choices)
    input = serializers.DictField()
    priority = serializers.IntegerField(min_value=-10, max_value=10, default=0)


# ---------------------------------------------------------------- agent-facing

class AgentTaskSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    context = serializers.SerializerMethodField()

    class Meta:
        model = ResearchTask
        fields = ("id", "workspace_id", "agent", "task_type", "status", "input", "attempt", "max_attempts",
                  "lease_id", "lease_expires_at", "cancel_requested", "context", "created_at")
        read_only_fields = fields

    def get_context(self, obj) -> dict:
        """Read-only data the agent needs that lives in the backend (approved idea for customer research)."""
        ctx: dict = {}
        if obj.task_type == TaskType.SAAS_CUSTOMER_RESEARCH and obj.software_idea_id:
            idea = obj.software_idea
            ctx["software_idea"] = SoftwareIdeaSerializer(idea).data
            if idea.opportunity_id:
                ctx["opportunity"] = OpportunitySerializer(idea.opportunity).data
        return ctx


class ClaimRequestSerializer(serializers.Serializer):
    worker_id = serializers.CharField(max_length=200)
    task_types = serializers.ListField(child=serializers.ChoiceField(choices=TaskType.choices), required=False)


class ClaimResponseSerializer(serializers.Serializer):
    task = AgentTaskSerializer(allow_null=True)


class HeartbeatRequestSerializer(serializers.Serializer):
    progress = serializers.IntegerField(min_value=0, max_value=100, required=False)
    stage = serializers.CharField(max_length=60, required=False)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)


class HeartbeatResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    cancel_requested = serializers.BooleanField()
    lease_expires_at = serializers.DateTimeField()


class CompleteRequestSerializer(serializers.Serializer):
    summary = serializers.DictField(required=False, default=dict)


class FailRequestSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    retryable = serializers.BooleanField(default=False)


class SuppressionCheckSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    emails = serializers.ListField(child=serializers.EmailField(), required=False, default=list, max_length=500)
    phones = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list,
                                   max_length=500)


class ResultReportSerializer(serializers.Serializer):
    created = serializers.DictField(child=serializers.IntegerField())
    updated = serializers.DictField(child=serializers.IntegerField())
    skipped = serializers.ListField(child=serializers.DictField())
    refs = serializers.DictField(child=serializers.DictField(child=serializers.UUIDField()))
    approvals_requested = serializers.ListField(child=serializers.DictField())
