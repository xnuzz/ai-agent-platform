"""Website technical analysis -> measured facts + problem findings (contract problem codes).

Each check records the facts it measured; findings carry those facts so every problem in the bundle cites
evidence. Only checks needed for the requested problem codes are run (`wanted`), so a narrow `checks`
input also means fewer requests to the business's site.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

from ..config import CrawlerSettings
from ..models import Finding
from ..problems import ALL_CODES, spec
from .fetcher import FetchResult, PoliteFetcher, classify_tls_error
from .htmlparse import PageInfo, parse_html
from .tls import TLSInfo, check_certificate

logger = logging.getLogger("local_leads.analyzer")

CONTACT_LINK_RE = re.compile(r"contact|kontakt|контакт|contacto|contatti|impressum|get-in-touch|reach-us", re.I)
BOOKING_RE = re.compile(
    r"book(ing)?[\s-]*(online|now|an? appointment|a table)|online[\s-]*booking|reserv(e|ation)|appointment|"
    r"termin|calendly|booksy|fresha|treatwell|opentable|resy\.com|doctolib|setmore|simplybook|acuityscheduling|"
    r"zocdoc|thefork|quandoo|reservio|planity|square\.site/book|youcanbook\.me", re.I)
ANALYTICS_RE = re.compile(
    r"googletagmanager\.com|google-analytics\.com|gtag\(|plausible\.io|matomo|piwik|usefathom|"
    r"cloudflareinsights|clarity\.ms|umami|simpleanalytics|statcounter|hotjar|posthog", re.I)
BOOKING_CATEGORIES = re.compile(
    r"dent|doctor|clinic|medical|physio|therap|salon|hair|barber|beauty|spa|nail|massage|restaurant|bistro|"
    r"hotel|guest ?house|yoga|gym|fitness|vet|tattoo|driving school|photograph|optic|cosmetic|wellness", re.I)
# (name pattern, minimum major.minor considered supported) - versions below are past vendor end-of-life.
CMS_MINIMUMS = [
    ("WordPress", re.compile(r"wordpress\s*(\d+)\.(\d+)", re.I), (6, 0)),
    ("Joomla", re.compile(r"joomla!?\s*(\d+)\.(\d+)", re.I), (4, 0)),
    ("Drupal", re.compile(r"drupal\s*(\d+)(?:\.(\d+))?", re.I), (10, 0)),
    ("TYPO3", re.compile(r"typo3\s*(?:cms\s*)?(\d+)\.(\d+)", re.I), (12, 0)),
    ("PrestaShop", re.compile(r"prestashop\s*(\d+)\.(\d+)", re.I), (8, 0)),
]
CMS_HINTS = [("WordPress", "/wp-content/"), ("Wix", "wix.com"), ("Squarespace", "squarespace"),
             ("Shopify", "cdn.shopify.com"), ("Webflow", "webflow"), ("Drupal", "/sites/default/files"),
             ("Joomla", "/media/jui/"), ("Jimdo", "jimdo")]
SECURITY_HEADERS = ["content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy",
                    "strict-transport-security"]
SKIP_LINK_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip", ".mp4", ".mp3", ".doc", ".docx")


@dataclass
class ScanResult:
    url: str
    final_url: str = ""
    scanned: bool = False             # homepage fetched and analysed
    skipped_reason: str = ""          # why the site was not analysed (robots, access denied ...)
    facts: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    retrieved_at: str = ""

    def summary(self) -> str:
        if not self.scanned:
            return f"Website scan of {self.url} not completed: {self.skipped_reason or 'unreachable'}."
        f = self.facts
        parts = [f"Scanned {self.final_url} ({f.get('status')}, {f.get('html_seconds', 0):.2f}s, "
                 f"{f.get('html_bytes', 0)} bytes)"]
        parts.append("HTTPS" if f.get("https") else "no HTTPS")
        if f.get("cms"):
            parts.append(f"CMS: {f['cms']}{' ' + f['cms_version'] if f.get('cms_version') else ''}")
        parts.append(f"{len(self.findings)} issue(s): " + ", ".join(x.code for x in self.findings) if self.findings
                     else "no issues found")
        return "; ".join(parts) + "."


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and "://" not in url:
        url = "http://" + url
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def _swap_scheme(url: str, scheme: str) -> str:
    p = urlsplit(url)
    return urlunsplit((scheme, p.netloc, "/", "", ""))


def _same_site(a: str, b: str) -> bool:
    ha, hb = (urlsplit(a).hostname or "").lower(), (urlsplit(b).hostname or "").lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return bool(ha) and strip(ha) == strip(hb)


class WebsiteAnalyzer:
    def __init__(self, settings: CrawlerSettings, fetcher: PoliteFetcher | None = None):
        self.settings = settings
        self.fetcher = fetcher or PoliteFetcher(settings)

    def close(self):
        self.fetcher.close()

    # ================================================================== entry point
    def analyze(self, website: str, *, category: str = "", wanted: set[str] | frozenset[str] = ALL_CODES
                ) -> ScanResult:
        url = normalize_url(website)
        res = ScanResult(url=url, retrieved_at=datetime.now(timezone.utc).isoformat())
        wanted = set(wanted)
        add = lambda code, desc, page="", severity=None, **facts: (  # noqa: E731
            res.findings.append(Finding(code=code, severity=severity or spec(code).severity, title=spec(code).title,
                                        description=desc, url=page or res.final_url or url, facts=facts))
            if code in wanted else None)

        # ---- TLS (before fetching, so a broken certificate does not hide the page content)
        verify = True
        tls: TLSInfo | None = None
        if urlsplit(url).scheme == "https":
            tls = self._tls(url)
            res.facts["tls"] = tls.facts()
            if tls.checked and not tls.valid:
                verify = False
                add(tls.problem, f"The TLS certificate of {urlsplit(url).hostname} fails browser verification: "
                                 f"{tls.error}.", page=url, tls_error=tls.error)
            elif tls.valid and tls.days_left is not None and tls.days_left < self.settings.ssl_expiry_warning_days:
                add("SSL_EXPIRING_SOON", f"The TLS certificate of {urlsplit(url).hostname} expires in "
                                         f"{tls.days_left} day(s) ({tls.not_after}).", page=url,
                    days_left=tls.days_left, not_after=tls.not_after)

        home = self.fetcher.get(url, verify=verify)
        if home.error_kind == "tls" and verify:
            code = classify_tls_error(home.error)
            res.facts["tls"] = {"valid": False, "error": home.error}
            add(code, f"The TLS certificate of {urlsplit(url).hostname} fails browser verification.", page=url,
                tls_error=home.error)
            verify = False
            home = self.fetcher.get(url, verify=False)
        res.final_url = home.final_url or url
        res.facts.update(self._fetch_facts(home))
        if home.error_kind == "robots_disallowed":
            robots = self.fetcher.robots(home.final_url or url)
            if robots.network_error:  # host down: robots.txt itself could not be fetched
                res.skipped_reason = f"unreachable: {robots.network_error}"
                add("WEBSITE_UNREACHABLE", f"The listed website {url} could not be reached "
                                           f"({robots.network_error}).", page=url, error=robots.network_error)
            else:
                res.skipped_reason = f"not analysed: robots.txt disallows crawling ({robots.reason})"
            return res
        if not home.ok or home.status in (404, 410) or (home.status or 0) >= 500:
            res.skipped_reason = home.error or f"HTTP {home.status}"
            add("WEBSITE_UNREACHABLE", f"The listed website {url} could not be loaded "
                                       f"({home.error or f'HTTP {home.status}'}).", page=url,
                error=home.error, status=home.status)
            return res
        if home.status in (401, 403, 429) or home.status >= 400:
            res.skipped_reason = f"access denied (HTTP {home.status}); not analysed"
            return res
        res.scanned = True
        res.pages.append(res.final_url)
        page = parse_html(home.text()) if home.is_html else PageInfo()
        final_https = urlsplit(res.final_url).scheme == "https"
        res.facts["https"] = final_https

        self._check_transport(res, home, final_https, wanted, add)
        self._check_performance(res, home, add)
        if home.is_html:
            self._check_markup(res, page, home, final_https, category, add)
        limited = self.fetcher.crawl_limited(res.final_url)
        res.facts["crawl_limited"] = limited

        contact_page = None
        if not limited:  # one extra page: contact form, booking widget and published e-mail address
            contact_page = self._contact_page(res, page, verify)
        if home.is_html:
            self._check_conversion(res, page, contact_page, category, add)
        if "BROKEN_LINKS" in wanted and not limited:
            self._check_links(res, page, verify, add)

        emails = page.emails() + (contact_page.emails() if contact_page else [])
        res.emails = list(dict.fromkeys(emails))[:10]
        return res

    # ================================================================== checks
    def _tls(self, url: str) -> TLSInfo:
        p = urlsplit(url)
        return check_certificate(p.hostname or "", p.port or 443, timeout=self.settings.connect_timeout,
                                 context=self.fetcher.ssl_context())

    @staticmethod
    def _fetch_facts(r: FetchResult) -> dict:
        return {"status": r.status, "final_url": r.final_url, "redirects": r.redirects,
                "html_seconds": round(r.elapsed, 3), "html_bytes": len(r.body), "truncated": r.truncated,
                "content_type": r.content_type, "server": r.headers.get("server", "")}

    def _check_transport(self, res, home: FetchResult, final_https: bool, wanted, add):
        if not wanted & {"NO_HTTPS", "NO_HTTPS_REDIRECT", "SECURITY_HEADERS_MISSING"}:
            return
        if not final_https:
            probe = self.fetcher.get(_swap_scheme(res.final_url, "https"), max_bytes=0)
            res.facts["https_probe"] = {"url": probe.url, "status": probe.status, "error": probe.error}
            if probe.ok and probe.status < 500:
                add("NO_HTTPS_REDIRECT", f"{res.final_url} is served over plain HTTP although an HTTPS version "
                                         f"responds; visitors are not redirected to HTTPS.", https_status=probe.status)
            else:
                why = "presents an invalid certificate" if probe.error_kind == "tls" else "does not respond"
                add("NO_HTTPS", f"The site is served over plain HTTP ({res.final_url}); the HTTPS version {why}. "
                                f"Browsers mark such pages as 'Not secure'.", https_error=probe.error)
        elif urlsplit(res.url).scheme == "https":
            probe = self.fetcher.get(_swap_scheme(res.final_url, "http"), max_bytes=0)
            res.facts["http_probe"] = {"url": probe.url, "status": probe.status,
                                       "redirects_to_https": urlsplit(probe.final_url).scheme == "https"}
            if probe.ok and probe.status < 400 and urlsplit(probe.final_url).scheme == "http":
                add("NO_HTTPS_REDIRECT", f"{probe.url} answers over plain HTTP (HTTP {probe.status}) instead of "
                                         f"redirecting to HTTPS.", page=probe.url, http_status=probe.status)
        headers = home.headers
        expected = SECURITY_HEADERS if final_https else SECURITY_HEADERS[:-1]
        csp = headers.get("content-security-policy", "")
        missing = [h for h in expected if h not in headers
                   and not (h == "x-frame-options" and "frame-ancestors" in csp)]
        res.facts["security_headers_missing"] = missing
        if len(missing) >= 3:
            add("SECURITY_HEADERS_MISSING", f"{len(missing)} of {len(expected)} recommended HTTP security headers "
                                            f"are missing: {', '.join(missing)}.", missing=missing)

    def _check_performance(self, res, home: FetchResult, add):
        secs, limit = home.elapsed, self.settings.slow_page_seconds
        if secs > limit:
            add("SLOW_PAGE_LOAD", f"The homepage HTML took {secs:.1f}s to download "
                                  f"(threshold {limit:.1f}s, {len(home.body)} bytes"
                                  f"{', truncated at size limit' if home.truncated else ''}).",
                severity="HIGH" if secs > 2 * limit else "MEDIUM", seconds=round(secs, 2), bytes=len(home.body))

    def _check_markup(self, res, page: PageInfo, home: FetchResult, final_https: bool, category: str, add):
        f = res.facts
        f.update({"title": page.title[:200], "meta_description": page.metas.get("description", "")[:300],
                  "viewport": page.viewport, "generator": page.generator, "html_lang": page.html_lang,
                  "h1_count": page.h1_count, "images": page.images_total,
                  "images_missing_alt": page.images_missing_alt, "forms": len(page.forms)})
        # -- mobile
        vp = page.viewport.lower().replace(" ", "")
        if "width=device-width" not in vp:
            add("NOT_MOBILE_FRIENDLY", "The homepage has no responsive viewport meta tag "
                                       f"({'missing' if not vp else repr(page.viewport)}); on phones it renders as a "
                                       "zoomed-out desktop page.", viewport=page.viewport)
        # -- meta
        missing_meta = [n for n, v in (("title", page.title), ("meta description", page.metas.get("description")))
                        if not v]
        if missing_meta:
            add("MISSING_META", f"The homepage is missing: {', '.join(missing_meta)}.", missing=missing_meta)
        # -- SEO
        robots_meta = page.metas.get("robots", "").lower()
        seo = []
        if "noindex" in robots_meta:
            seo.append("homepage is marked noindex")
        if page.h1_count == 0:
            seo.append("no <h1> heading")
        if page.title and not 10 <= len(page.title) <= 70:
            seo.append(f"title length {len(page.title)} characters (recommended 10-70)")
        if not page.canonical:
            seo.append("no canonical URL")
        f["seo_issues"] = seo
        if "noindex" in robots_meta or page.h1_count == 0 or len(seo) >= 2:
            add("POOR_SEO", "On-page SEO gaps on the homepage: " + "; ".join(seo) + ".", issues=seo)
        # -- accessibility
        a11y = []
        if page.images_total >= 3 and page.images_missing_alt / page.images_total >= 0.2:
            a11y.append(f"{page.images_missing_alt} of {page.images_total} images have no alt text")
        if not page.html_lang:
            a11y.append("page language not declared (<html lang>)")
        if page.unlabelled_controls:
            a11y.append(f"{page.unlabelled_controls} form field(s) without a label")
        if "user-scalable=no" in vp or "maximum-scale=1" in vp:
            a11y.append("zooming is disabled in the viewport settings")
        f["accessibility_issues"] = a11y
        if len(a11y) >= 2 or (page.images_total >= 3 and page.images_missing_alt / page.images_total >= 0.5):
            add("ACCESSIBILITY_ISSUES", "Accessibility issues: " + "; ".join(a11y) + ".", issues=a11y)
        # -- CMS
        self._check_cms(res, page, home, add)
        # -- legacy design
        signals = [f"<{t}> elements ({n})" for t, n in page.legacy_tags.items()]
        if page.flash_embeds:
            signals.append(f"Flash content ({page.flash_embeds})")
        if page.max_table_depth >= 2 or page.tables >= 4:
            signals.append(f"table-based layout ({page.tables} tables, nesting depth {page.max_table_depth})")
        strong = bool(page.flash_embeds or {"marquee", "blink", "frameset", "frame"} & set(page.legacy_tags))
        f["legacy_markup"] = signals
        if strong or len(signals) >= 2:
            add("OUTDATED_DESIGN", "The homepage uses legacy markup: " + "; ".join(signals) + ".", signals=signals)
        # -- mixed content
        if final_https:
            insecure = sorted({u for u in page.resource_urls if u.lower().startswith("http://")})[:10]
            f["insecure_resources"] = insecure
            if insecure:
                add("MIXED_CONTENT", f"The HTTPS page loads {len(insecure)} resource(s) over plain HTTP, e.g. "
                                     f"{insecure[0]}.", resources=insecure)
        # -- analytics
        haystack = " ".join(page.script_srcs) + " " + page.script_text
        has_analytics = bool(ANALYTICS_RE.search(haystack))
        f["analytics_detected"] = has_analytics
        if not has_analytics:
            add("NO_ANALYTICS", "No visitor analytics script was detected on the homepage, so the business cannot "
                                "measure how visitors find and use the site.", severity="LOW")

    def _check_cms(self, res, page: PageInfo, home: FetchResult, add):
        gen = page.generator
        body_sample = home.text()[:200_000].lower()
        cms, version = "", ""
        for name, rx, minimum in CMS_MINIMUMS:
            m = rx.search(gen)
            if m:
                cms = name
                major, minor = int(m.group(1)), int(m.group(2) or 0)
                version = f"{major}.{minor}"
                if (major, minor) < minimum:
                    add("OUTDATED_CMS", f"The site reports {gen!r} in its generator tag; {name} versions below "
                                        f"{minimum[0]}.{minimum[1]} no longer receive regular security updates.",
                        cms=name, version=version, generator=gen)
                break
        if not cms:
            for name, needle in CMS_HINTS:
                if needle in gen.lower() or needle in body_sample:
                    cms = name
                    break
        res.facts["cms"], res.facts["cms_version"] = cms, version

    def _contact_page(self, res, page: PageInfo, verify: bool) -> PageInfo | None:
        for href, text in page.links:
            if CONTACT_LINK_RE.search(href) or CONTACT_LINK_RE.search(text):
                target = urljoin(res.final_url, href).split("#")[0]
                if target.rstrip("/") == res.final_url.rstrip("/") or not _same_site(target, res.final_url):
                    continue
                r = self.fetcher.get(target, verify=verify)
                res.facts["contact_page"] = {"url": target, "status": r.status, "error": r.error}
                if r.ok and r.status < 400 and r.is_html:
                    res.pages.append(r.final_url)
                    return parse_html(r.text())
                return None
        res.facts["contact_page"] = None
        return None

    def _check_conversion(self, res, page: PageInfo, contact: PageInfo | None, category: str, add):
        pages = [page] + ([contact] if contact else [])
        has_form = any(f.looks_like_contact_form for p in pages for f in p.forms)
        res.facts["contact_form"] = has_form
        if not has_form:
            where = "the homepage or contact page" if contact else "the homepage (no contact page link found)"
            add("NO_CONTACT_FORM", f"No contact form was found on {where}; visitors must call or e-mail.")
        if BOOKING_CATEGORIES.search(category or ""):
            hay = " ".join(" ".join([p.text[:50_000], " ".join(h for h, _ in p.links), " ".join(p.iframe_srcs),
                                     " ".join(p.script_srcs)]) for p in pages)
            booking = bool(BOOKING_RE.search(hay))
            res.facts["online_booking"] = booking
            if not booking:
                add("NO_ONLINE_BOOKING", f"No online booking or reservation option was found, which customers "
                                         f"commonly expect from a {category.lower()}.")

    def _check_links(self, res, page: PageInfo, verify: bool, add):
        seen, candidates = {res.final_url.rstrip("/")}, []
        for href, _ in page.links:
            if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
                continue
            target = urljoin(res.final_url, href).split("#")[0]
            if (not _same_site(target, res.final_url) or target.rstrip("/") in seen
                    or urlsplit(target).path.lower().endswith(SKIP_LINK_EXT)):
                continue
            seen.add(target.rstrip("/"))
            candidates.append(target)
        checked, broken, skipped = 0, [], 0
        for target in candidates:
            if checked >= self.settings.max_link_checks:
                break
            if not self.fetcher.allowed(target):
                skipped += 1
                continue
            r = self.fetcher.check_link(target, verify=verify)
            checked += 1
            if r.error_kind in ("connect", "timeout") or (r.status or 0) >= 400:
                broken.append({"url": target, "status": r.status, "error": r.error[:200]})
        res.facts["links"] = {"internal_found": len(candidates), "checked": checked, "broken": broken,
                              "skipped_by_robots": skipped}
        if broken:
            add("BROKEN_LINKS", f"{len(broken)} of {checked} sampled internal links are broken, e.g. "
                                f"{broken[0]['url']} ({broken[0]['status'] or broken[0]['error']}).",
                severity="MEDIUM" if len(broken) >= 2 else "LOW", broken=broken)
