"""HTML snapshot → title + plaintext (stdlib only)."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser

# Cap for semantic fingerprint input so footers / widgets do not dominate hash drift.
_SEMANTIC_FINGERPRINT_MAX_CHARS = 100_000


def _squish_ws(s: str) -> str:
    return " ".join(s.split())


def _attrs_lower(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {str(k).lower(): str(v or "").lower() for k, v in attrs}


def _opens_main_content_region(tag: str, attrs: list[tuple[str, str | None]]) -> dict[str, str] | None:
    """Return a stack record when this start tag opens a main-ish region, else None."""

    t = tag.lower()
    ad = _attrs_lower(attrs)
    if t == "main":
        return {"tag": t, "kind": "main"}
    if t == "article":
        return {"tag": t, "kind": "article"}
    if ad.get("role") == "main":
        return {"tag": t, "kind": "div_rm"}
    idv = ad.get("id", "").strip()
    if idv in ("content", "main", "main-content", "page-content", "primary", "site-content"):
        return {"tag": t, "kind": "div_id"}
    classes = ad.get("class", "").split()
    for marker in ("entry-content", "post-content", "article-body", "main-content", "page-content", "content-area"):
        if marker in classes:
            return {"tag": t, "kind": "div_class"}
    return None


class _ExtractPage(HTMLParser):
    """Collect `<title>` and visible text while skipping scripts/styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._title_parts: list[str] = []
        self._parts: list[str] = []
        self._suppress = 0  # nesting depth inside script/style/noscript/template

    def handle_starttag(self, tag: str, attrs):
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "template"}:
            self._suppress += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "template"}:
            self._suppress = max(0, self._suppress - 1)

    def handle_data(self, data):
        if self._suppress > 0:
            return
        chunk = data.strip()
        if not chunk:
            return
        if self._in_title:
            self._title_parts.append(chunk)
            return
        self._parts.append(chunk)


class _MainPreferredExtract(HTMLParser):
    """Like ``_ExtractPage`` but prefers text inside ``<main>`` / ``<article>`` / ``[role=main]`` / common content ids."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._title_parts: list[str] = []
        self._suppress = 0
        self._main_stack: list[dict[str, str]] = []
        self._main_parts: list[str] = []
        self._all_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "template"}:
            self._suppress += 1
            return
        rec = _opens_main_content_region(tag, attrs)
        if rec is not None:
            self._main_stack.append(rec)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "template"}:
            self._suppress = max(0, self._suppress - 1)
            return
        if not self._main_stack:
            return
        et = tag.lower()
        top = self._main_stack[-1]
        k = top.get("kind")
        if k == "main" and et == "main":
            self._main_stack.pop()
        elif k == "article" and et == "article":
            self._main_stack.pop()
        elif k == "div_rm" and et == "div":
            self._main_stack.pop()
        elif k in ("div_id", "div_class") and et == top.get("tag"):
            self._main_stack.pop()

    def handle_data(self, data):
        if self._suppress > 0:
            return
        chunk = data.strip()
        if not chunk:
            return
        if self._in_title:
            self._title_parts.append(chunk)
            return
        self._all_parts.append(chunk)
        if self._main_stack:
            self._main_parts.append(chunk)


def extract_snapshot_text(html: bytes) -> tuple[str | None, str]:
    """Return (best-effort ``<title>`` string, plaintext body)."""

    try:
        s = html.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        s = html.decode("latin-1", errors="replace")
    p = _ExtractPage()
    try:
        p.feed(s)
        p.close()
    except Exception:  # noqa: BLE001
        title = None
        plain = ""
    else:
        title_raw = "".join(p._title_parts).strip()
        title = title_raw[:512].strip() or None
        plain = _squish_ws(" ".join(p._parts))
    return title, plain


def extract_snapshot_text_main_preferred(html: bytes) -> tuple[str | None, str]:
    """Return (title, plaintext) preferring ``<main>`` / ``<article>`` / role=main regions; fallback to full body."""

    try:
        s = html.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        s = html.decode("latin-1", errors="replace")
    p = _MainPreferredExtract()
    try:
        p.feed(s)
        p.close()
    except Exception:  # noqa: BLE001
        return extract_snapshot_text(html)

    title_raw = "".join(p._title_parts).strip()
    title = title_raw[:512].strip() or None
    main_plain = _squish_ws(" ".join(p._main_parts))
    if len(main_plain) >= 80:
        return title, main_plain
    full_plain = _squish_ws(" ".join(p._all_parts))
    return title, full_plain if full_plain else main_plain


def semantic_main_fingerprint_hex(html: bytes) -> str:
    """Stable SHA-256 hex digest of normalized main-preferred plaintext (for ``mainsha:`` dedupe)."""

    _title, plain = extract_snapshot_text_main_preferred(html)
    norm = _squish_ws(plain).strip()[:_SEMANTIC_FINGERPRINT_MAX_CHARS]
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def html_poll_content_external_id(html: bytes) -> str:
    """``ContentItem.external_id`` for html_page poll rows (semantic body, not raw bytes)."""

    return f"mainsha:{semantic_main_fingerprint_hex(html)}"


def plaintext_excerpt(text: str, max_chars: int) -> str:
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return (t[: max_chars - 1].rsplit(" ", 1)[0] or t[:max_chars]).strip()


def plaintext_from_html_fragment(html: str) -> str:
    """Strip tags from RSS ``content:encoded`` / HTML summaries (stdlib only)."""

    if not html or not html.strip():
        return ""
    p = _ExtractPage()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001
        return ""
    return _squish_ws(" ".join(p._parts))
