"""TLS certificate check: validity (chain + hostname) and days until expiry.

Uses a direct TLS handshake with full verification. On verification failure the OpenSSL verify code tells
us *why* (10 = expired); other failures (self-signed, unknown issuer, hostname mismatch) are "invalid".
"""
from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone

X509_V_ERR_CERT_HAS_EXPIRED = 10


@dataclass
class TLSInfo:
    checked: bool = False          # False -> could not connect (network); no conclusion
    valid: bool = False
    problem: str = ""              # "" | SSL_EXPIRED | SSL_INVALID_CERTIFICATE
    error: str = ""
    not_after: str = ""            # ISO 8601
    days_left: int | None = None
    issuer: str = ""
    protocol: str = ""

    def facts(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in ("", None)}


def check_certificate(host: str, port: int = 443, *, timeout: float = 5.0,
                      context: ssl.SSLContext | None = None, now: datetime | None = None) -> TLSInfo:
    ctx = context or ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
                info = TLSInfo(checked=True, valid=True, protocol=tls.version() or "")
    except ssl.SSLCertVerificationError as exc:
        expired = exc.verify_code == X509_V_ERR_CERT_HAS_EXPIRED
        return TLSInfo(checked=True, valid=False, problem="SSL_EXPIRED" if expired else "SSL_INVALID_CERTIFICATE",
                       error=f"{exc.verify_message} (verify code {exc.verify_code})")
    except (OSError, ssl.SSLError) as exc:
        return TLSInfo(checked=False, error=str(exc)[:300] or type(exc).__name__)
    if cert.get("notAfter"):
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc)
        info.not_after = expires.isoformat()
        info.days_left = int((expires - (now or datetime.now(timezone.utc))).total_seconds() // 86400)
    issuer = dict(x[0] for x in cert.get("issuer", ()) if x)
    info.issuer = issuer.get("organizationName") or issuer.get("commonName") or ""
    return info
