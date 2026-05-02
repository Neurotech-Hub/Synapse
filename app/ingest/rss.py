"""Fetch and normalize RSS entries."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen
import ssl

import feedparser


@dataclass
class ParsedEntry:
    external_id: str
    title: str
    link: str
    published_parsed: Any | None
    snippet: str


UNSAFE_SSL = ssl.create_default_context()


def fetch_feed(feed_url: str, timeout: float = 30.0):
    """Fetch feed and return parsed feedparser dict."""
    req = Request(feed_url, headers={"User-Agent": "SynapseIngest/1.0"})
    with urlopen(req, timeout=timeout, context=UNSAFE_SSL) as resp:
        raw = resp.read()
    return feedparser.parse(raw)


def _entry_id(entry) -> str:
    if getattr(entry, "id", None):
        return str(entry.id)
    if getattr(entry, "link", None) and getattr(entry, "title", None):
        h = hashlib.sha256()
        h.update(str(entry.link).encode())
        h.update(b"\0")
        h.update(str(entry.title).encode())
        return h.hexdigest()
    if getattr(entry, "link", None):
        return str(entry.link)
    raise ValueError("RSS entry missing link and id")


def iter_entries(parsed) -> list[ParsedEntry]:
    out: list[ParsedEntry] = []
    for entry in parsed.entries or []:
        try:
            eid = _entry_id(entry)
        except ValueError:
            continue
        title = (getattr(entry, "title", None) or "").strip() or "(no title)"
        link = (getattr(entry, "link", None) or "").strip() or ""
        summary = (
            getattr(entry, "summary", None)
            or getattr(entry, "description", None)
            or ""
        )
        out.append(
            ParsedEntry(
                external_id=eid[:512],
                title=title,
                link=link,
                published_parsed=getattr(entry, "published_parsed", None),
                snippet=summary[:4000] if summary else "",
            )
        )
    return out
