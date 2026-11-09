"""Problem-code catalog (docs/AGENT_2_CONTRACT.md §Problem codes).

One place that defines, per code: display title, default severity, scoring weight, and the remediation
scope used by the brief builder (scope item, effort hours, tech). Scoring and briefs are therefore
deterministic and explainable: every point and every hour traces back to a row here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProblemSpec:
    code: str
    title: str
    severity: str             # LOW | MEDIUM | HIGH (contract vocabulary)
    weight: int               # points added to the lead score
    scope_item: str           # remediation work item for the project brief
    hours: tuple[int, int]    # effort range for that item
    tech: tuple[str, ...] = ()
    rebuild_covers: bool = True   # True -> a full rebuild already fixes it (no separate scope item)


_SPECS = [
    ProblemSpec("NO_WEBSITE", "No website found", "HIGH", 60,
                "Design and build a mobile-first business website (5-7 pages)", (30, 50),
                ("Static site generator or lightweight CMS", "Managed hosting with TLS")),
    ProblemSpec("WEBSITE_UNREACHABLE", "Listed website does not respond", "HIGH", 45,
                "Restore or relaunch the website on reliable hosting", (8, 20), ("Managed hosting",)),
    ProblemSpec("NO_HTTPS", "Website not served over HTTPS", "HIGH", 30,
                "Enable HTTPS with an automatically renewed certificate and redirect all HTTP traffic",
                (2, 4), ("Let's Encrypt / managed TLS",)),
    ProblemSpec("NO_HTTPS_REDIRECT", "HTTP version does not redirect to HTTPS", "MEDIUM", 8,
                "Redirect HTTP to HTTPS and enable HSTS", (1, 2)),
    ProblemSpec("SSL_EXPIRED", "TLS certificate expired", "HIGH", 35,
                "Renew the TLS certificate and automate renewal", (1, 3), ("Let's Encrypt / managed TLS",)),
    ProblemSpec("SSL_INVALID_CERTIFICATE", "TLS certificate not trusted by browsers", "HIGH", 30,
                "Replace the TLS certificate with a valid, trusted one and automate renewal", (1, 3),
                ("Let's Encrypt / managed TLS",)),
    ProblemSpec("SSL_EXPIRING_SOON", "TLS certificate expires soon", "MEDIUM", 8,
                "Renew the TLS certificate and automate renewal", (1, 2)),
    ProblemSpec("SLOW_PAGE_LOAD", "Slow page load", "MEDIUM", 15,
                "Performance optimisation (caching, image compression, asset minification)", (6, 12),
                ("CDN / caching",)),
    ProblemSpec("NOT_MOBILE_FRIENDLY", "Not optimised for mobile devices", "HIGH", 25,
                "Responsive, mobile-first layout", (12, 24), ("Responsive CSS",)),
    ProblemSpec("BROKEN_LINKS", "Broken internal links", "MEDIUM", 10,
                "Fix broken links and add redirects for moved pages", (2, 4)),
    ProblemSpec("OUTDATED_CMS", "Outdated CMS version", "HIGH", 20,
                "Upgrade the CMS, themes and plugins to supported versions", (6, 16)),
    ProblemSpec("OUTDATED_DESIGN", "Outdated page markup and design", "MEDIUM", 15,
                "Modern visual redesign", (16, 32)),
    ProblemSpec("MIXED_CONTENT", "HTTPS page loads insecure (HTTP) resources", "MEDIUM", 8,
                "Serve all page resources over HTTPS", (1, 3)),
    ProblemSpec("NO_ONLINE_BOOKING", "No online booking or reservation option", "MEDIUM", 12,
                "Integrate online booking / reservations", (8, 16), ("Booking widget or custom form",),
                rebuild_covers=False),
    ProblemSpec("NO_CONTACT_FORM", "No contact form", "MEDIUM", 10,
                "Add a spam-protected contact form", (3, 6), rebuild_covers=False),
    ProblemSpec("POOR_SEO", "Basic on-page SEO gaps", "MEDIUM", 8,
                "On-page SEO: headings, titles, canonical URLs, sitemap", (4, 8)),
    ProblemSpec("MISSING_META", "Missing title or meta description", "LOW", 8,
                "Write page titles and meta descriptions", (2, 4)),
    ProblemSpec("ACCESSIBILITY_ISSUES", "Accessibility issues", "MEDIUM", 8,
                "Accessibility fixes (image alt text, language, form labels)", (4, 8)),
    ProblemSpec("NO_ANALYTICS", "No privacy-friendly visitor analytics", "LOW", 4,
                "Set up privacy-friendly analytics", (1, 3), ("Privacy-friendly analytics",),
                rebuild_covers=False),
    ProblemSpec("SECURITY_HEADERS_MISSING", "Missing HTTP security headers", "LOW", 6,
                "Configure HTTP security headers", (1, 3)),
    ProblemSpec("NO_GOOGLE_BUSINESS_PROFILE", "No Google Business Profile", "MEDIUM", 10,
                "Create and verify a Google Business Profile", (2, 4), rebuild_covers=False),
]

PROBLEMS: dict[str, ProblemSpec] = {s.code: s for s in _SPECS}
ALL_CODES: frozenset[str] = frozenset(PROBLEMS)

# Problems that indicate the site should be rebuilt rather than patched (brief builder).
REBUILD_TRIGGERS = frozenset({"NOT_MOBILE_FRIENDLY", "OUTDATED_DESIGN", "OUTDATED_CMS"})


def spec(code: str) -> ProblemSpec:
    return PROBLEMS[code]
