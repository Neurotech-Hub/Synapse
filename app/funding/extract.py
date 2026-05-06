from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class FundingPageText:
    title: str | None
    text: str
    content_hash: str


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "nav", "footer"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "div"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "nav", "footer"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_data(self, data: str):
        if not data or self._skip_depth:
            return
        if self._in_title:
            self._title_parts.append(data)
        self._parts.append(data)

    @property
    def title(self) -> str | None:
        title = _normalize_text(" ".join(self._title_parts))
        return title or None

    @property
    def text(self) -> str:
        return _normalize_text(" ".join(self._parts))


def extract_funding_page_text(
    body: bytes | str,
    *,
    content_type: str | None = None,
    max_chars: int = 60_000,
) -> FundingPageText:
    if isinstance(body, bytes):
        text = body.decode("utf-8", errors="replace")
    else:
        text = str(body)
    is_html = "html" in (content_type or "").lower() or bool(re.search(r"<\s*html|<\s*body|<\s*p[\s>]", text[:2000], re.I))
    if is_html:
        parser = _ReadableHTMLParser()
        parser.feed(text)
        extracted = parser.text
        title = parser.title
    else:
        extracted = _normalize_text(text)
        title = None
    extracted = extracted[: max(int(max_chars), 1)].strip()
    return FundingPageText(title=title, text=extracted, content_hash=hash_text(extracted))


def hash_text(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in re.split(r"[\r\n]+", text or "")]
    cleaned = [line for line in lines if line]
    return "\n".join(cleaned).strip()
