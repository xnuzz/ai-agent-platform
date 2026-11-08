from django.contrib import admin

from .models import AgentToken, ResearchTask


@admin.register(AgentToken)
class AgentTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "agent", "prefix", "is_active", "last_used_at", "created_at")
    readonly_fields = ("prefix", "key_hash", "last_used_at")
    exclude = ()


@admin.register(ResearchTask)
class ResearchTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "task_type", "status", "progress", "attempt", "created_at")
    list_filter = ("status", "agent", "task_type")
