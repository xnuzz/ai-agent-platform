"""Browser auth (ADR-014): access token in the response body (kept in memory by the SPA), refresh token only
in an httpOnly cookie scoped to /api/v1/auth/. Refresh tokens rotate and are blacklisted after use/logout."""
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record
from apps.common.actor import Actor

from .models import User

AccessResponse = inline_serializer("AccessToken", {"access": serializers.CharField()})


def _set_refresh_cookie(response, refresh: str):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE, refresh, max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_REFRESH_COOKIE_PATH, httponly=True, secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE)


def _clear_refresh_cookie(response):
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_REFRESH_COOKIE_PATH,
                           samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE)


def revoke_all_refresh_tokens(user) -> None:
    for t in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=t)


class _PublicAuthView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'  # failed login/refresh -> 401, not 403


class LoginView(_PublicAuthView):
    @extend_schema(request=TokenObtainPairSerializer, responses=AccessResponse, tags=["auth"])
    def post(self, request):
        ser = TokenObtainPairSerializer(data=request.data)
        try:
            ser.is_valid(raise_exception=True)
        except TokenError as exc:
            raise AuthenticationFailed(str(exc))
        resp = Response({"access": ser.validated_data["access"]})
        _set_refresh_cookie(resp, ser.validated_data["refresh"])
        return resp


class RefreshView(_PublicAuthView):
    @extend_schema(request=None, responses=AccessResponse, tags=["auth"],
                   description="Uses the httpOnly refresh cookie; rotates it.")
    def post(self, request):
        token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if not token:
            raise AuthenticationFailed("No refresh session.")
        ser = TokenRefreshSerializer(data={"refresh": token})
        try:
            ser.is_valid(raise_exception=True)
        except (TokenError, ValidationError) as exc:
            resp = Response({"error": {"code": "authentication_failed", "message": "Session expired.",
                                       "details": {}}}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(resp)
            return resp
        resp = Response({"access": ser.validated_data["access"]})
        if "refresh" in ser.validated_data:
            _set_refresh_cookie(resp, ser.validated_data["refresh"])
        return resp


class LogoutView(_PublicAuthView):
    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request):
        token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass  # already invalid: logout is idempotent
        resp = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(resp)
        return resp


class PasswordResetRequestView(_PublicAuthView):
    @extend_schema(request=inline_serializer("PasswordResetRequest", {"email": serializers.EmailField()}),
                   responses={202: None}, tags=["auth"],
                   description="Always 202 (never reveals whether the account exists).")
    def post(self, request):
        email = serializers.EmailField().run_validation(request.data.get("email"))
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.PUBLIC_APP_URL}/reset-password?uid={uid}&token={token}"
            minutes = settings.PASSWORD_RESET_TIMEOUT // 60
            send_mail("Reset your password",
                      f"Someone asked to reset the password for {user.email}.\n\nReset it here (valid {minutes} "
                      f"minutes):\n{link}\n\nIf this wasn't you, ignore this email.",
                      settings.DEFAULT_FROM_EMAIL, [user.email])
            record("user.password_reset_requested", workspace=None, actor=Actor.for_user(user), target=user)
        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(_PublicAuthView):
    @extend_schema(request=inline_serializer("PasswordResetConfirm", {
        "uid": serializers.CharField(), "token": serializers.CharField(), "new_password": serializers.CharField()}),
        responses={204: None}, tags=["auth"])
    def post(self, request):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(request.data.get("uid", ""))), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError, DjangoValidationError):
            user = None  # malformed uid / not a UUID
        if user is None or not default_token_generator.check_token(user, request.data.get("token", "")):
            raise ValidationError({"token": ["This reset link is invalid or has expired."]})
        password = request.data.get("new_password") or ""
        validate_password_or_400(password, user)
        user.set_password(password)
        user.save(update_fields=["password"])
        revoke_all_refresh_tokens(user)  # sign out every other session
        record("user.password_reset", workspace=None, actor=Actor.for_user(user), target=user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=inline_serializer("PasswordChange", {
        "current_password": serializers.CharField(), "new_password": serializers.CharField()}),
        responses={204: None}, tags=["auth"])
    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get("current_password") or ""):
            raise ValidationError({"current_password": ["Incorrect password."]})
        password = request.data.get("new_password") or ""
        validate_password_or_400(password, user)
        user.set_password(password)
        user.save(update_fields=["password"])
        revoke_all_refresh_tokens(user)
        record("user.password_changed", workspace=None, actor=Actor.for_user(user), target=user)
        resp = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(resp)  # client must sign in again
        return resp


def validate_password_or_400(password: str, user) -> None:
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})
