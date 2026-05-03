"""Fetch and normalize RSS feeds.

Mirrors fetching patterns used by Neurotech Connection-maker for NIH RSS (browser-like headers + curl):
https://github.com/Neurotech-Hub/Connection-maker/blob/master/api/agents/ingestion.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl

import feedparser

from app.ingest.html_extract import plaintext_from_html_fragment


@dataclass
class ParsedEntry:
    external_id: str
    title: str
    link: str
    published_parsed: Any | None
    snippet: str


UNSAFE_SSL = ssl.create_default_context()

_PUBMED_RSS_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://pubmed.ncbi.nlm.nih.gov/",
}

_BROWSERISH_ACCEPT = "application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5"


def pubmed_feed_url(feed_url: str) -> bool:
    try:
        host = (urlparse(feed_url).hostname or "").lower()
    except ValueError:
        return False
    return host == "pubmed.ncbi.nlm.nih.gov"


def rss_request_headers(feed_url: str) -> dict[str, str]:
    if pubmed_feed_url(feed_url):
        return dict(_PUBMED_RSS_HEADERS)
    return {
        "User-Agent": "SynapseIngest/1.0",
        "Accept": _BROWSERISH_ACCEPT,
    }


def _curl_exe() -> str | None:
    return shutil.which("curl") or shutil.which("curl.exe")


def _curl_get(url: str, headers: dict[str, str], timeout_sec: int) -> tuple[int, bytes]:
    exe = _curl_exe()
    if not exe:
        raise FileNotFoundError("curl")

    tout = max(5, timeout_sec)
    with tempfile.TemporaryDirectory() as tmp:
        body_path = os.path.join(tmp, "body")
        cmd: list[str] = [
            exe,
            "-sS",
            "--compressed",
            "-L",
            "--max-time",
            str(tout),
            "-w",
            "%{http_code}",
            "-o",
            body_path,
        ]
        for key, val in headers.items():
            cmd.extend(["-H", f"{key}: {val}"])
        cmd.append(url)

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=tout + 20,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(stderr or f"curl exit {proc.returncode}")

        code_txt = (proc.stdout or "").strip()
        if not code_txt.isdigit():
            raise RuntimeError(f"unexpected curl status {code_txt!r}")

        with open(body_path, "rb") as fh:
            body = fh.read()

        return int(code_txt), body


def _pubmed_curl_enabled() -> bool:
    return (os.environ.get("SYNAPSE_RSS_PUBMED_CURL") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def fetch_feed(feed_url: str, timeout: float = 30.0):
    """Fetch feed and return parsed feedparser dict."""

    headers = rss_request_headers(feed_url)
    tsec = max(5, int(timeout))

    if pubmed_feed_url(feed_url) and _pubmed_curl_enabled() and _curl_exe():
        try:
            status, raw = _curl_get(feed_url, headers, tsec)
            if status == 200 and raw:
                return feedparser.parse(raw)
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
            pass

    req = Request(feed_url, headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=UNSAFE_SSL) as resp:
            raw = resp.read()
    except HTTPError as e:
        if (
            pubmed_feed_url(feed_url)
            and e.code == 403
            and _pubmed_curl_enabled()
            and _curl_exe()
        ):
            status, raw = _curl_get(feed_url, headers, tsec)
            if status == 200 and raw:
                return feedparser.parse(raw)
        raise

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


def _entry_rich_snippet(entry) -> str:
    """Prefer full ``content:encoded`` (e.g. PubMed abstracts); fall back to summary HTML/text."""

    parts: list[str] = []
    for c in getattr(entry, "content", None) or []:
        val = getattr(c, "value", None) if not isinstance(c, dict) else c.get("value")
        if val:
            parts.append(str(val))
    merged = "".join(parts).strip()
    if merged:
        plain = plaintext_from_html_fragment(merged)
        if plain.strip():
            return plain
    raw = (
        (getattr(entry, "summary", None) or getattr(entry, "description", None) or "").strip()
    )
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        plain = plaintext_from_html_fragment(raw)
        if plain.strip():
            return plain
    return raw


def iter_entries(parsed) -> list[ParsedEntry]:
    out: list[ParsedEntry] = []
    for entry in parsed.entries or []:
        try:
            eid = _entry_id(entry)
        except ValueError:
            continue
        title = (getattr(entry, "title", None) or "").strip() or "(no title)"
        link = (getattr(entry, "link", None) or "").strip() or ""
        body = _entry_rich_snippet(entry)
        out.append(
            ParsedEntry(
                external_id=eid[:512],
                title=title,
                link=link,
                published_parsed=getattr(entry, "published_parsed", None),
                snippet=body[:12000] if body else "",
            )
        )
    return out
