import re

import pytest
from django.conf import settings
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from support.factories import make_user

pytestmark = pytest.mark.django_db
PW, NEW_PW = "S3cure-pass-123", "Brand-new-pass-456"
COOKIE = settings.AUTH_REFRESH_COOKIE


@pytest.fixture
def user():
    return make_user(email="auth@example.com", password=PW)


def login(c=None):
    c = c or APIClient()
    r = c.post("/api/v1/auth/token/", {"email": "auth@example.com", "password": PW}, format="json")
    return c, r


def test_login_sets_httponly_cookie_and_hides_refresh(user):
    c, r = login()
    assert r.status_code == 200 and set(r.json()) == {"access"}
    ck = r.cookies[COOKIE]
    assert ck["httponly"] and ck["path"] == "/api/v1/auth/" and ck["samesite"] == "Lax"


def test_bad_credentials(user):
    r = APIClient().post("/api/v1/auth/token/", {"email": "auth@example.com", "password": "nope"}, format="json")
    assert r.status_code == 401 and COOKIE not in r.cookies


def test_refresh_uses_cookie_and_rotates(user):
    c, r = login()
    old = r.cookies[COOKIE].value
    r2 = c.post("/api/v1/auth/token/refresh/")
    assert r2.status_code == 200 and "access" in r2.json()
    assert r2.cookies[COOKIE].value != old  # rotated
    stale = APIClient()
    stale.cookies[COOKIE] = old
    assert stale.post("/api/v1/auth/token/refresh/").status_code == 401  # old token blacklisted after rotation


def test_refresh_without_cookie(db):
    assert APIClient().post("/api/v1/auth/token/refresh/").status_code == 401


def test_logout_revokes(user):
    c, r = login()
    token = r.cookies[COOKIE].value
    assert c.post("/api/v1/auth/logout/").status_code == 204
    replay = APIClient()
    replay.cookies[COOKIE] = token
    assert replay.post("/api/v1/auth/token/refresh/").status_code == 401


def test_password_reset_flow(user):
    c, r = login()
    session_token = r.cookies[COOKIE].value
    assert APIClient().post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"},
                            format="json").status_code == 202  # no enumeration
    assert mail.outbox == []
    assert APIClient().post("/api/v1/auth/password-reset/", {"email": "AUTH@example.com"},
                            format="json").status_code == 202
    link = re.search(r"reset-password\?uid=(\S+)&token=(\S+)", mail.outbox[0].body)
    uid, token = link.group(1), link.group(2)
    pub = APIClient()
    assert pub.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": "bad", "new_password": NEW_PW},
                    format="json").status_code == 400
    assert pub.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "123"},
                    format="json").status_code == 400  # validators apply
    assert pub.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": NEW_PW},
                    format="json").status_code == 204
    assert pub.post("/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": NEW_PW},
                    format="json").status_code == 400  # single use
    old = APIClient()
    old.cookies[COOKIE] = session_token
    assert old.post("/api/v1/auth/token/refresh/").status_code == 401  # other sessions signed out
    assert APIClient().post("/api/v1/auth/token/", {"email": "auth@example.com", "password": NEW_PW},
                            format="json").status_code == 200
    assert AuditEvent.objects.filter(action="user.password_reset").exists()


def test_password_reset_confirm_garbage_uid(db):
    r = APIClient().post("/api/v1/auth/password-reset/confirm/", {"uid": "!!!", "token": "x", "new_password": NEW_PW},
                         format="json")
    assert r.status_code == 400


def test_password_change(user):
    c, r = login()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
    assert c.post("/api/v1/auth/password/change/", {"current_password": "wrong", "new_password": NEW_PW},
                  format="json").status_code == 400
    r2 = c.post("/api/v1/auth/password/change/", {"current_password": PW, "new_password": NEW_PW}, format="json")
    assert r2.status_code == 204
    assert c.post("/api/v1/auth/token/refresh/").status_code == 401  # must sign in again
