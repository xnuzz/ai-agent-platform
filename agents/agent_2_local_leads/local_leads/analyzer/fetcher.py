"""Polite HTTP fetching for website scans.

Crawler ethics (docs/AGENT_2_CONTRACT.md §Compliance notes, README §Crawler ethics):
- robots.txt is fetched once per origin and obeyed for every request (RFC 9309 semantics:
  4xx -> no restrictions, 5xx / unreachable -> treat as fully disallowed). Crawl-delay is honoured.
- At most one request per `min_host_interval` seconds to the same host (thread-safe).
- Every request has connect/read timeouts AND a wall-clock deadline; bodies are read up to `max_page_bytes`.
- The User-Agent names the bot and links to an info page (no personal e-mail address).
"""
from __future__ import annotations

import logging
import re
import ssl
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from ..config import CrawlerSettings

logger = logging.getLogger("local_leads.fetcher")
ROBOTS_TOKEN = "LocalLeadsBot"
MAX_REDIRECTS = 5
ROBOTS_MAX_BYTES = 500_000


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    elapsed: float = 0.0                 # seconds spent on the wire (all hops, excluding politeness waits)
    truncated: bool = False
    redirects: list[str] = field(default_factory=list)
    error: str = ""                      # human-readable error, "" on success
    error_kind: str = ""                 # robots_disallowed | timeout | connect | tls | too_many_redirects

    @property
    def ok(self) -> bool:
        return not self.error_kind and self.status is not None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml", "")

    def text(self) -> str:
        charset = ""
        for part in self.headers.get("content-type", "").split(";")[1:]:
            k, _, v = part.strip().partition("=")
            if k.lower() == "charset" and v:
                charset = v.strip("\"' ")
        if not charset:  # old sites (e.g. windows-1251) often declare it only in <meta>
            m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", self.body[:4096], re.I)
            charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class _Robots:
    def __init__(self, parser: RobotFileParser | None = None, allow_all: bool = False, reason: str = "",
                 network_error: str = ""):
        self.parser, self.allow_all, self.reason = parser, allow_all, reason
        self.network_error = network_error   # set when the host could not be reached at all

    def can_fetch(self, url: str) -> bool:
        if self.parser is None:
            return self.allow_all
        return self.parser.can_fetch(ROBOTS_TOKEN, url)

    def crawl_delay(self) -> float:
        if self.parser is None:
            return 0.0
        delay = self.parser.crawl_delay(ROBOTS_TOKEN)
        return float(delay) if delay else 0.0


def origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


def classify_tls_error(message: str) -> str:
    """Map an OpenSSL verification message to a problem code."""
    return "SSL_EXPIRED" if "expired" in message.lower() else "SSL_INVALID_CERTIFICATE"


class PoliteFetcher:
    def __init__(self, settings: CrawlerSettings, *, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, clock=time.perf_counter):
        self.settings = settings
        self._transport = transport
        self._sleep, self._clock = sleep, clock
        self._clients: dict[bool, httpx.Client] = {}
        self._robots: dict[str, _Robots] = {}
        self._robots_lock = threading.Lock()
        self._origin_locks: dict[str, threading.Lock] = {}
        self._host_next: dict[str, float] = {}
        self._host_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self.request_count = 0

    # ------------------------------------------------------------ clients
    def ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=self.settings.ca_bundle or None)

    def _client(self, verify: bool) -> httpx.Client:
        with self._lock:
            if verify not in self._clients:
                s = self.settings
                self._clients[verify] = httpx.Client(
                    transport=self._transport, follow_redirects=False, trust_env=s.trust_env,
                    verify=self.ssl_context() if verify else False,
                    timeout=httpx.Timeout(s.read_timeout, connect=s.connect_timeout),
                    headers={"User-Agent": s.user_agent, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                             "Accept-Language": "*"},
                )
            return self._clients[verify]

    def close(self) -> None:
        for c in self._clients.values():
            c.close()
        self._clients.clear()

    # ------------------------------------------------------------ politeness
    def _host_lock(self, host: str) -> threading.Lock:
        with self._lock:
            return self._host_locks.setdefault(host, threading.Lock())

    def _wait_turn(self, url: str, interval: float) -> None:
        host = (urlsplit(url).hostname or "").lower()
        with self._host_lock(host):
            slot = self._host_next.get(host, 0.0)
            wait = slot - self._clock()
            if wait > 0:
                self._sleep(wait)
            # Schedule from the reserved slot, not a re-read clock: a coarse or lagging clock
            # (time.monotonic is ~15.6 ms on Windows) would otherwise let the next request in early.
            self._host_next[host] = max(slot, self._clock()) + interval

    def robots(self, url: str) -> _Robots:
        origin = origin_of(url)
        with self._robots_lock:
            if origin in self._robots:
                return self._robots[origin]
            lock = self._origin_locks.setdefault(origin, threading.Lock())
        with lock:  # one robots.txt download per origin even with concurrent callers
            if origin not in self._robots:
                self._robots[origin] = self._load_robots(origin)
            return self._robots[origin]

    def _load_robots(self, origin: str) -> _Robots:
        res = self._request("GET", origin + "/robots.txt", max_bytes=ROBOTS_MAX_BYTES, check_robots=False,
                            verify=False, interval=self.settings.min_host_interval)
        # verify=False: robots.txt must be honoured even when the site's certificate is broken.
        if res.error_kind or res.status is None:
            return _Robots(allow_all=False, reason=f"robots.txt unreachable ({res.error or res.error_kind})",
                           network_error=res.error or res.error_kind)
        if res.status >= 500:
            return _Robots(allow_all=False, reason=f"robots.txt returned HTTP {res.status}")
        if res.status >= 400:
            return _Robots(allow_all=True, reason=f"no robots.txt (HTTP {res.status})")
        parser = RobotFileParser()
        parser.parse(res.text().splitlines())
        return _Robots(parser=parser, reason="robots.txt parsed")

    def host_interval(self, url: str) -> float:
        """Seconds between requests to this host: robots Crawl-delay, capped at `max_crawl_delay` (sites asking
        for more are crawl-limited: the analyzer then fetches only the homepage and one HTTPS probe)."""
        delay = min(self.robots(url).crawl_delay(), self.settings.max_crawl_delay)
        return max(self.settings.min_host_interval, delay)

    def crawl_limited(self, url: str) -> bool:
        """True when robots Crawl-delay is so large that we only fetch the homepage."""
        return self.robots(url).crawl_delay() > self.settings.max_crawl_delay

    def allowed(self, url: str) -> bool:
        return self.robots(url).can_fetch(url)

    # ------------------------------------------------------------ requests
    def get(self, url: str, *, verify: bool = True, max_bytes: int | None = None) -> FetchResult:
        return self._request("GET", url, verify=verify, max_bytes=max_bytes)

    def check_link(self, url: str, *, verify: bool = True) -> FetchResult:
        """HEAD (fallback GET without reading the body) for broken-link checks."""
        res = self._request("HEAD", url, verify=verify, max_bytes=0)
        if res.status in (405, 501):
            res = self._request("GET", url, verify=verify, max_bytes=0)
        return res

    def _request(self, method: str, url: str, *, verify: bool = True, max_bytes: int | None = None,
                 check_robots: bool = True, interval: float | None = None) -> FetchResult:
        s = self.settings
        limit = s.max_page_bytes if max_bytes is None else max_bytes
        result = FetchResult(url=url)
        current = url
        for _hop in range(MAX_REDIRECTS + 1):
            if urlsplit(current).scheme not in ("http", "https"):
                result.error, result.error_kind = f"unsupported URL scheme: {current}", "connect"
                return result
            if check_robots and not self.allowed(current):
                result.final_url = current
                result.error, result.error_kind = f"disallowed by robots.txt: {current}", "robots_disallowed"
                return result
            client = self._client(verify)  # build (TLS context load) before taking the slot, not inside it
            self._wait_turn(current, interval if interval is not None else self.host_interval(current))
            started = self._clock()
            deadline = started + s.connect_timeout + 2 * s.read_timeout
            try:
                with self._lock:
                    self.request_count += 1
                with client.stream(method, current) as resp:
                    body, truncated = bytearray(), False
                    if method != "HEAD" and limit > 0 and not resp.is_redirect:
                        for chunk in resp.iter_bytes():
                            body.extend(chunk)
                            if len(body) >= limit:
                                truncated = True
                                del body[limit:]
                                break
                            if self._clock() > deadline:
                                truncated = True
                                break
                    result.elapsed += self._clock() - started
                    status, headers = resp.status_code, {k.lower(): v for k, v in resp.headers.items()}
            except httpx.TimeoutException as exc:
                result.elapsed += self._clock() - started
                result.final_url, result.error, result.error_kind = current, f"timeout: {exc}", "timeout"
                return result
            except (httpx.HTTPError, ssl.SSLError, OSError, ValueError) as exc:
                result.elapsed += self._clock() - started
                msg = str(exc) or type(exc).__name__
                kind = "tls" if "CERTIFICATE_VERIFY_FAILED" in msg else "connect"
                result.final_url, result.error, result.error_kind = current, msg[:500], kind
                return result
            location = headers.get("location")
            if 300 <= status < 400 and location:
                result.redirects.append(current)
                current = urljoin(current, location)
                continue
            result.final_url, result.status, result.headers = current, status, headers
            result.body, result.truncated = bytes(body), truncated
            return result
        result.final_url, result.error, result.error_kind = current, "too many redirects", "too_many_redirects"
        return result
