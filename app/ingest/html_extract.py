"""Minimal HTML snapshot → title + plaintext (stdlib only)."""

from __future__ import annotations

from html.parser import HTMLParser


def _squish_ws(s: str) -> str:
    return " ".join(s.split())


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


def extract_snapshot_text(html: bytes) -> tuple[str | None, str]:
    """Return (best-effort `<title>` string, plaintext body)."""
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
