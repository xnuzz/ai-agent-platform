"""Agent 2 test helpers: local HTTP(S) websites, a throw-away test CA, an in-memory TaskContext.

Every website the analyzer scans in tests is served from 127.0.0.x by these servers - tests never touch
the internet. Distinct loopback IPs (127.0.0.2, .3, ...) give distinct hostnames, which matters because
the backend dedupes businesses by website hostname (ports are ignored).
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import ssl
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


@dataclass
class Route:
    body: str | bytes = ""
    status: int = 200
    headers: dict = field(default_factory=lambda: {"Content-Type": "text/html; charset=utf-8"})
    delay: float = 0.0


class SiteServer:
    def __init__(self, routes: dict, host: str = "127.0.0.2", tls: ssl.SSLContext | None = None):
        self.routes, self.host, self.tls = routes, host, tls
        self.requests: list[dict] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _serve(self, head=False):
                path = self.path.split("?")[0]
                server.requests.append({"method": self.command, "path": path, "t": time.monotonic(),
                                        "ua": self.headers.get("User-Agent", "")})
                route = server.routes.get(path)
                if callable(route):
                    route = route()
                route = route or Route("not found", 404, {"Content-Type": "text/plain"})
                if route.delay:
                    time.sleep(route.delay)
                body = route.body.encode() if isinstance(route.body, str) else route.body
                self.send_response(route.status)
                for k, v in route.headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if not head:
                    try:
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

            def do_GET(self):  # noqa: N802
                self._serve()

            def do_HEAD(self):  # noqa: N802
                self._serve(head=True)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer((host, 0), Handler)
        self.httpd.daemon_threads = True
        self.httpd.handle_error = lambda *a: None  # TLS probes with plain HTTP etc. are expected in tests
        if tls is not None:
            self.httpd.socket = tls.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"{'https' if self.tls else 'http'}://{self.host}:{self.port}/"

    def start(self) -> "SiteServer":
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def paths(self, method=None) -> list[str]:
        return [r["path"] for r in self.requests if method is None or r["method"] == method]


class TestPKI:
    """A test CA that can issue leaf certificates for loopback IPs (valid, expired, expiring soon)."""
    __test__ = False

    def __init__(self, directory: Path):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        self._x509, self._hashes, self._ser, self._ec, self._oid = x509, hashes, serialization, ec, NameOID
        self.dir = directory
        self.ca_key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local Leads Test CA")])
        now = dt.datetime.now(dt.timezone.utc)
        self.ca_cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                        .public_key(self.ca_key.public_key()).serial_number(x509.random_serial_number())
                        .not_valid_before(now - dt.timedelta(days=30)).not_valid_after(now + dt.timedelta(days=3650))
                        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                                     content_commitment=False, key_encipherment=False,
                                                     data_encipherment=False, key_agreement=False,
                                                     encipher_only=False, decipher_only=False), critical=True)
                        .add_extension(x509.SubjectKeyIdentifier.from_public_key(self.ca_key.public_key()),
                                       critical=False)
                        .sign(self.ca_key, hashes.SHA256()))
        self.ca_file = directory / "ca.pem"
        self.ca_file.write_bytes(self.ca_cert.public_bytes(serialization.Encoding.PEM))

    def server_context(self, ip: str, *, days_valid: float = 90, expired: bool = False,
                       self_signed: bool = False) -> ssl.SSLContext:
        x509, hashes, ser = self._x509, self._hashes, self._ser
        key = self._ec.generate_private_key(self._ec.SECP256R1())
        now = dt.datetime.now(dt.timezone.utc)
        start, end = ((now - dt.timedelta(days=60), now - dt.timedelta(days=1)) if expired
                      else (now - dt.timedelta(days=1), now + dt.timedelta(days=days_valid)))
        subject = x509.Name([x509.NameAttribute(self._oid.COMMON_NAME, ip)])
        issuer_key, issuer_name = (key, subject) if self_signed else (self.ca_key, self.ca_cert.subject)
        builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer_name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(start).not_valid_after(end)
                   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
                                  critical=False)
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True))
        if not self_signed:
            builder = builder.add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()), critical=False)
        cert = builder.sign(issuer_key, hashes.SHA256())
        tag = f"{ip}-{time.monotonic_ns()}"
        cert_file, key_file = self.dir / f"{tag}.crt", self.dir / f"{tag}.key"
        cert_file.write_bytes(cert.public_bytes(ser.Encoding.PEM))
        key_file.write_bytes(key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        return ctx


class FakeContext:
    """In-memory stand-in for platform_sdk.TaskContext (unit tests of the handler without a backend)."""

    def __init__(self, task_input: dict, *, suppressed_emails=(), suppressed_phones=()):
        self.task = SimpleNamespace(id="task-1", input=task_input)
        self.cancel_requested = False
        self.progress_calls: list[tuple] = []
        self.bundles: list[dict] = []
        self.suppression_calls: list[tuple] = []
        self._supp_e, self._supp_p = set(suppressed_emails), set(suppressed_phones)

    @property
    def input(self):
        return self.task.input

    def progress(self, progress=None, stage=None, message=None):
        self.progress_calls.append((progress, stage, message))

    def check_cancelled(self):
        pass

    def submit(self, bundle):
        self.bundles.append(bundle)
        approvals = [{"target_type": t} for sec, t in (("project_briefs", "PROJECT_BRIEF"), ("campaigns", "CAMPAIGN"))
                     for item in bundle.get(sec, []) if item.get("submit_for_approval")]
        return {"created": {}, "updated": {}, "skipped": [], "refs": {}, "approvals_requested": approvals}

    def check_suppression(self, emails=(), phones=()):
        self.suppression_calls.append((list(emails), list(phones), len(self.bundles)))
        return {"suppressed_emails": [e for e in emails if e in self._supp_e],
                "suppressed_phones": [p for p in phones if p in self._supp_p]}


# --------------------------------------------------------------------------- canned websites
POOR_HOME = """<html><head><title>Bakery</title>
<meta name="generator" content="WordPress 4.9.8">
<link rel="stylesheet" href="/wp-content/themes/old/style.css"></head>
<body><table><tr><td><table><tr><td><font size="5"><center>Welcome to Corner Bakery</center></font>
<img src="/a.jpg"><img src="/b.jpg"><img src="/c.jpg">
<a href="/about">About</a> <a href="/old-menu">Menu</a> <a href="/private/secret">Staff</a>
<a href="mailto:info@cornerbakery.test">Write to us</a> <a href="https://elsewhere.test/x">Partner</a>
</td></tr></table></td></tr></table></body></html>"""

GOOD_HOME = """<!doctype html><html lang="en"><head><title>Modern Dental Studio - Plovdiv</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Family dentistry in Plovdiv.">
<link rel="canonical" href="/"><script async src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>
</head><body><h1>Modern Dental Studio</h1><img src="/team.jpg" alt="Our team">
<a href="/contact">Contact</a> <a href="/booking">Book an appointment online</a></body></html>"""

GOOD_CONTACT = """<!doctype html><html lang="en"><head><title>Contact - Modern Dental Studio</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head><body><h1>Contact</h1>
<form action="/send" method="post"><label for="n">Name</label><input id="n" name="name">
<label for="e">E-mail</label><input id="e" type="email" name="email">
<label for="m">Message</label><textarea id="m" name="message"></textarea><button>Send</button></form>
<p>Reception: office@moderndental.test</p></body></html>"""

SECURITY_HEADERS = {"Content-Type": "text/html; charset=utf-8", "Content-Security-Policy": "default-src 'self'",
                    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                    "Referrer-Policy": "strict-origin-when-cross-origin"}


def poor_site_routes() -> dict:
    return {"/": Route(POOR_HOME), "/robots.txt": Route("User-agent: *\nDisallow: /private\n",
                                                        headers={"Content-Type": "text/plain"}),
            "/about": Route("<html><body>About us</body></html>"),
            "/private/secret": Route("<html>secret</html>")}


def good_site_routes() -> dict:
    return {"/": Route(GOOD_HOME, headers=SECURITY_HEADERS), "/contact": Route(GOOD_CONTACT, headers=SECURITY_HEADERS),
            "/booking": Route("<html><body>Booking</body></html>", headers=SECURITY_HEADERS),
            "/robots.txt": Route("User-agent: *\nAllow: /\n", headers={"Content-Type": "text/plain"})}
