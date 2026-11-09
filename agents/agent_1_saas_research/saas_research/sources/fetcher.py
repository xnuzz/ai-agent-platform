"""HTTP page fetcher used to read business websites (contact emails) and enrich evidence excerpts.

Safety: only http(s); refuses hosts resolving to private/loopback/link-local addresses (SSRF guard, checked on every
redirect hop); honours robots.txt (FETCH_RESPECT_ROBOTS); caps body size; HTML/text only.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .base import Page, clean_text, is_http_url, origin_of, utcnow_iso

logger = logging.getLogger("saas_research.sources.fetcher")

EMAIL_RE = re.compile(r"(?<![\w.+-])([a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,24})(?![\w-])")
_OBFUSCATED_AT = re.compile(r"\s*(?:\[at\]|\(at\)|\{at\})\s*", re.I)
_OBFUSCATED_DOT = re.compile(r"\s*(?:\[dot\]|\(dot\)|\{dot\})\s*", re.I)
_ASSET_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def extract_emails(text: str) -> tuple[str, ...]:
    """Emails literally present in `text` (incl. simple [at]/[dot] obfuscation), lower-cased, de-duplicated."""
    text = _OBFUSCATED_DOT.sub(".", _OBFUSCATED_AT.sub("@", text or ""))
    seen: dict[str, None] = {}
    for m in EMAIL_RE.finditer(text):
        email = m.group(1).lower().rstrip(".")
        if email.endswith(_ASSET_SUFFIX):
            continue
        seen.setdefault(email, None)
    return tuple(seen)


class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self.mailtos: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            if href.lower().startswith("mailto:"):
                self.mailtos.append(href[7:].split("?")[0])
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "footer"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        else:
            self.parts.append(data)


def html_to_page_parts(markup: str) -> tuple[str, str, tuple[str, ...]]:
    """-> (title, text, emails)"""
    p = _HTMLText()
    try:
        p.feed(markup)
        p.close()
    except Exception:  # noqa: BLE001 - malformed HTML: keep what was parsed
        pass
    text = "\n".join(line for line in (clean_text(x) for x in "".join(p.parts).split("\n")) if line)
    emails = extract_emails(" ".join(p.mailtos) + "\n" + text)
    return clean_text(p.title, 500), text, emails


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast \
                or ip.is_unspecified:
            return False
    return True


class HttpPageFetcher:
    name = "http"
    MAX_REDIRECTS = 5

    def __init__(self, *, timeout: float = 15.0, max_bytes: int = 1_500_000, respect_robots: bool = True,
                 user_agent: str = "SaaSResearchAgent/1.0", transport: httpx.BaseTransport | None = None,
                 host_check: Callable[[str], bool] = _is_public_host):
        self._http = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False,
                                  headers={"User-Agent": user_agent, "Accept": "text/html,text/plain;q=0.9"})
        self.max_bytes, self.respect_robots, self.user_agent = max_bytes, respect_robots, user_agent
        self._host_check = host_check
        self._robots: dict[str, RobotFileParser | None] = {}

    def close(self) -> None:
        self._http.close()

    def _allowed_by_robots(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        origin = origin_of(url)
        if origin not in self._robots:
            parser: RobotFileParser | None = None
            try:
                resp = self._http.get(origin + "/robots.txt")
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser = RobotFileParser()
                    parser.disallow_all = True
            except httpx.HTTPError:
                parser = None  # unreachable robots.txt -> treat as no restrictions (RFC 9309 §2.3.1.4 = 4xx)
            self._robots[origin] = parser
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(self.user_agent, url)

    def _read_capped(self, resp: httpx.Response) -> bytes:
        chunks, size = [], 0
        for chunk in resp.iter_bytes():
            size += len(chunk)
            if size > self.max_bytes:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def fetch(self, url: str) -> Page | None:
        current = url
        for _ in range(self.MAX_REDIRECTS + 1):
            if not is_http_url(current):
                return None
            host = urlsplit(current).hostname or ""
            if not self._host_check(host):
                logger.info("fetch refused (non-public host): %s", current)
                return None
            if not self._allowed_by_robots(current):
                logger.info("fetch disallowed by robots.txt: %s", current)
                return None
            try:
                with self._http.stream("GET", current) as resp:
                    if resp.is_redirect and resp.headers.get("location"):
                        current = urljoin(current, resp.headers["location"])
                        continue
                    if resp.status_code != 200:
                        return None
                    ctype = resp.headers.get("content-type", "").lower()
                    if ctype and not ("html" in ctype or ctype.startswith("text/")):
                        return None
                    raw = self._read_capped(resp)
                    encoding = resp.encoding or "utf-8"
            except httpx.HTTPError as exc:
                logger.info("fetch failed %s: %s", current, exc)
                return None
            markup = raw.decode(encoding, errors="replace")
            if "html" in ctype or "<html" in markup[:2000].lower():
                title, text, emails = html_to_page_parts(markup)
            else:
                title, text, emails = "", clean_text(markup), extract_emails(markup)
            return Page(url=current, status=200, title=title, text=text, retrieved_at=utcnow_iso(), emails=emails)
        return None
