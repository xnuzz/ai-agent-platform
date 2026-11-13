from django.conf import settings
from django.http import JsonResponse


class MaxRequestSizeMiddleware:
    """Reject oversized bodies by Content-Length before any parser reads them (413)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length > settings.MAX_REQUEST_BYTES:
            return JsonResponse({"error": {"code": "payload_too_large", "message": "Request body too large.",
                                           "details": {"max_bytes": settings.MAX_REQUEST_BYTES}}}, status=413)
        return self.get_response(request)
