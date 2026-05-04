"""Presentation helpers for public Latest cards (deterministic + curated overlays)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models import ContentItem

# Short generic page titles that are almost never “news” when paired with nav-heavy snippets.
_GENERIC_UTILITY_TITLES = frozenset(
    {
        "about",
        "about us",
        "contact",
        "contact us",
        "home",
        "privacy",
        "privacy policy",
        "cookie policy",
        "cookies",
        "legal",
        "terms",
        "terms of service",
        "disclaimer",
        "search",
        "faq",
    }
)

_NAV_PREFIX_CHUNK = re.compile(
    r"^(?:(?:skip\s+to\s+(?:content|search|navigation|footer|main))\s*)+",
    re.IGNORECASE,
)


def strip_nav_accessibility_prefixes(text: str) -> str:
    """Remove repeated leading ``skip to …`` accessibility links common in HTML extracts."""

    t = (text or "").strip()
    while True:
        m = _NAV_PREFIX_CHUNK.match(t)
        if not m:
            break
        t = t[m.end() :].lstrip(r" ,.;:·-—|")
    return t.strip()


def _path_lower(link: str | None) -> str:
    raw = (link or "").strip()
    if not raw:
        return ""
    try:
        return (urlparse(raw).path or "").lower()
    except ValueError:
        return ""


def utility_url_path_suppresses_public_latest(ci: ContentItem) -> bool:
    """Utility URLs (about, contact, etc.) — suppressed on the public feed even if the model said ``show``."""

    return _utility_junk_url_path(_path_lower(ci.link))


def _utility_junk_url_path(path_l: str) -> bool:
    """Standalone utility paths that rarely belong in a “what’s new” feed."""

    if not path_l:
        return False
    p = path_l.rstrip("/") or "/"
    if re.search(r"/about-us(?:/|$)", path_l):
        return True
    for tail in ("/contact", "/privacy", "/cookies", "/legal", "/terms", "/disclaimer"):
        if p.endswith(tail):
            return True
    if p == "/about" or p.endswith("/about"):
        return True
    return False


def heuristic_uncurated_hide_from_public_latest(ci: ContentItem) -> bool:
    """Deterministic hide for never-curated rows (LLM batches are capped). Utility URLs use ``utility_url_path_suppresses_public_latest``."""

    if ci.public_feed_verdict is not None:
        return False
    title_l = (ci.title or "").strip().lower()
    snip = (ci.snippet or "").strip()
    if not snip:
        return False
    kind = (ci.source.kind if ci.source is not None else "") or ""
    if kind == "html_page" and title_l in _GENERIC_UTILITY_TITLES and snip.lower().startswith("skip to "):
        return True
    return False


def collapse_obvious_doubled_title(title: str) -> str:
    """If ``title`` is the same substring repeated twice (no separator), return one copy."""

    t = (title or "").strip()
    if len(t) < 4 or len(t) % 2 != 0:
        return t
    half = len(t) // 2
    a, b = t[:half], t[half:]
    if a == b:
        return a
    return t


def effective_public_latest_title(ci: ContentItem) -> str:
    if ci.public_feed_verdict == "show" and (ci.public_feed_display_title or "").strip():
        return (ci.public_feed_display_title or "").strip()
    base = collapse_obvious_doubled_title((ci.title or "").strip())
    return base or "Untitled"


def effective_public_latest_snippet(ci: ContentItem) -> str | None:
    if ci.public_feed_verdict == "show" and ci.public_feed_display_blurb is not None:
        s = (ci.public_feed_display_blurb or "").strip()
        return s if s else None
    raw = (ci.snippet or "").strip()
    if not raw:
        return None
    cleaned = strip_nav_accessibility_prefixes(raw)
    return cleaned if cleaned else None
