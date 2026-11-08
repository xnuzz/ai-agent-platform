"""Unified error envelope: {"error": {"code", "message", "details"}} (docs/API_CONTRACTS.md §Errors)."""
import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class PlatformAPIException(exceptions.APIException):
    def __init__(self, message=None, *, details=None, code=None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        self.details = details or {}
        self.error_code = code or self.default_code


class InvalidStateTransition(PlatformAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "invalid_state"
    default_detail = "The requested operation is not allowed in the current state."


class Conflict(PlatformAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "Conflict."


class ComplianceBlocked(PlatformAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "compliance_blocked"
    default_detail = "Blocked by outreach compliance rules."


class WorkspaceRequired(PlatformAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "workspace_required"
    default_detail = "X-Workspace-ID header is required and must reference a workspace you belong to."


_CODE_MAP = {
    exceptions.ValidationError: "validation_error",
    exceptions.ParseError: "parse_error",
    exceptions.AuthenticationFailed: "authentication_failed",
    exceptions.NotAuthenticated: "not_authenticated",
    exceptions.PermissionDenied: "permission_denied",
    exceptions.NotFound: "not_found",
    exceptions.MethodNotAllowed: "method_not_allowed",
    exceptions.Throttled: "throttled",
}


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Internal server error.", "details": {}}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, PlatformAPIException):
        code, message, details = exc.error_code, str(exc.detail), exc.details
    elif isinstance(exc, exceptions.ValidationError):
        code, message, details = "validation_error", "Invalid input.", response.data
    else:
        code = next((c for cls, c in _CODE_MAP.items() if isinstance(exc, cls)), "error")
        data = response.data
        message = str(data.get("detail", exc)) if isinstance(data, dict) else str(exc)
        details = {}
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
