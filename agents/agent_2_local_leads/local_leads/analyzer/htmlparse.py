"""Single-pass HTML fact extraction (stdlib html.parser; tolerant of broken markup)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

MAX_TEXT = 100_000
MAX_SCRIPT_TEXT = 64_000
MAX_LINKS = 500
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}")
LEGACY_TAGS = ("font", "center", "marquee", "blink", "frameset", "frame")
FORM_CONTROLS = ("input", "select", "textarea")
NON_LABELLED_INPUTS = ("hidden", "submit", "button", "reset", "image")


@dataclass
class FormInfo:
    action: str = ""
    method: str = "get"
    input_types: list[str] = field(default_factory=list)
    input_names: list[str] = field(default_factory=list)
    has_textarea: bool = False

    @property
    def looks_like_contact_form(self) -> bool:
        """A form that lets a visitor send a message (excludes search / newsletter-only forms)."""
        names = " ".join(self.input_names).lower()
        if self.has_textarea:
            return True
        return "email" in self.input_types and any(k in names for k in ("message", "name", "phone", "subject"))


@dataclass
class PageInfo:
    title: str = ""
    metas: dict[str, str] = field(default_factory=dict)
    html_lang: str = ""
    h1_count: int = 0
    canonical: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)       # (href, anchor text)
    forms: list[FormInfo] = field(default_factory=list)
    images_total: int = 0
    images_missing_alt: int = 0
    script_srcs: list[str] = field(default_factory=list)
    iframe_srcs: list[str] = field(default_factory=list)
    resource_urls: list[str] = field(default_factory=list)           # src/href of embedded resources
    legacy_tags: dict[str, int] = field(default_factory=dict)
    flash_embeds: int = 0
    tables: int = 0
    max_table_depth: int = 0
    form_controls: int = 0
    unlabelled_controls: int = 0
    mailto: list[str] = field(default_factory=list)
    text: str = ""
    script_text: str = ""

    @property
    def viewport(self) -> str:
        return self.metas.get("viewport", "")

    @property
    def generator(self) -> str:
        return self.metas.get("generator", "")

    def emails(self) -> list[str]:
        found = list(self.mailto) + EMAIL_RE.findall(self.text)
        out: list[str] = []
        for e in found:
            e = e.strip().strip(".").lower()
            if e and e not in out and not e.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
                out.append(e)
        return out


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.info = PageInfo()
        self._in_title = False
        self._skip_depth = 0          # inside <script>/<style>
        self._in_script = False
        self._text: list[str] = []
        self._text_len = 0
        self._script: list[str] = []
        self._script_len = 0
        self._form: FormInfo | None = None
        self._table_depth = 0
        self._label_depth = 0
        self._label_for: set[str] = set()
        self._control_ids: list[tuple[str, bool]] = []   # (id, labelled_otherwise)
        self._anchor: list[str] | None = None
        self._anchor_href = ""

    # -------------------------------------------------------------- tags
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        info = self.info
        if tag == "html":
            info.html_lang = a.get("lang", "") or a.get("xml:lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key and key not in info.metas:
                info.metas[key] = a.get("content", "").strip()
        elif tag == "h1":
            info.h1_count += 1
        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel and not info.canonical:
                info.canonical = a.get("href", "")
            if a.get("href") and ("stylesheet" in rel or "icon" in rel):
                info.resource_urls.append(a["href"])
        elif tag == "a":
            href = a.get("href", "").strip()
            if href.lower().startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr:
                    info.mailto.append(addr)
            self._anchor, self._anchor_href = [], href
        elif tag == "form":
            self._form = FormInfo(action=a.get("action", ""), method=a.get("method", "get").lower())
            info.forms.append(self._form)
        elif tag in FORM_CONTROLS:
            itype = a.get("type", "text").lower() if tag == "input" else tag
            if self._form is not None:
                if tag == "textarea":
                    self._form.has_textarea = True
                self._form.input_types.append(itype)
                self._form.input_names.append(" ".join(filter(None, (a.get("name"), a.get("id"),
                                                                      a.get("placeholder")))))
            if itype not in NON_LABELLED_INPUTS:
                info.form_controls += 1
                labelled = bool(self._label_depth or a.get("aria-label") or a.get("aria-labelledby")
                                or a.get("title"))
                self._control_ids.append((a.get("id", ""), labelled))
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self._label_for.add(a["for"])
        elif tag == "img":
            info.images_total += 1
            if "alt" not in a:
                info.images_missing_alt += 1
            if a.get("src"):
                info.resource_urls.append(a["src"])
        elif tag == "script":
            self._skip_depth += 1
            self._in_script = True
            if a.get("src"):
                info.script_srcs.append(a["src"])
                info.resource_urls.append(a["src"])
        elif tag == "style":
            self._skip_depth += 1
        elif tag == "iframe":
            if a.get("src"):
                info.iframe_srcs.append(a["src"])
                info.resource_urls.append(a["src"])
        elif tag in ("embed", "object"):
            src = (a.get("src") or a.get("data") or "").lower()
            if ".swf" in src or "shockwave" in a.get("type", "").lower():
                info.flash_embeds += 1
        elif tag == "table":
            info.tables += 1
            self._table_depth += 1
            info.max_table_depth = max(info.max_table_depth, self._table_depth)
        if tag in LEGACY_TAGS:
            info.legacy_tags[tag] = info.legacy_tags.get(tag, 0) + 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ("script", "style", "label", "a", "table", "form", "title"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            self._in_script = False
        elif tag == "form":
            self._form = None
        elif tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        elif tag == "table":
            self._table_depth = max(0, self._table_depth - 1)
        elif tag == "a" and self._anchor is not None:
            if len(self.info.links) < MAX_LINKS and self._anchor_href:
                self.info.links.append((self._anchor_href, " ".join("".join(self._anchor).split())[:200]))
            self._anchor = None

    def handle_data(self, data):
        if self._in_title:
            self.info.title += data
        if self._skip_depth:
            if self._in_script and self._script_len < MAX_SCRIPT_TEXT:
                self._script.append(data)
                self._script_len += len(data)
            return
        if self._anchor is not None:
            self._anchor.append(data)
        if self._text_len < MAX_TEXT:
            self._text.append(data)
            self._text_len += len(data)

    def finish(self) -> PageInfo:
        info = self.info
        info.title = " ".join(info.title.split())
        info.text = " ".join(" ".join(self._text).split())[:MAX_TEXT]
        info.script_text = "".join(self._script)[:MAX_SCRIPT_TEXT]
        info.unlabelled_controls = sum(1 for cid, ok in self._control_ids
                                       if not ok and not (cid and cid in self._label_for))
        return info


def parse_html(html: str) -> PageInfo:
    p = _Parser()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - html.parser is lenient, but never let one page kill a scan
        pass
    return p.finish()
