from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.funding.extract import FundingPageText, extract_funding_page_text
from app.ingest.urlnorm import UrlValidationError, canonical_url


@dataclass
class FundingFetchResult:
    requested_url: str
    final_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    fetched_at: datetime | None = None
    page_text: FundingPageText | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.page_text is not None


def fetch_funding_page_text(
    raw_url: str,
    *,
    timeout_sec: int = 20,
    max_bytes: int = 2_000_000,
    max_chars: int = 60_000,
    allow_private_hosts: bool = False,
) -> FundingFetchResult:
    try:
        url = canonical_url(raw_url)
        _reject_private_host(url, allow_private_hosts=allow_private_hosts)
    except (UrlValidationError, ValueError) as exc:
        return FundingFetchResult(requested_url=raw_url, error=str(exc), fetched_at=datetime.now(timezone.utc))

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SynapseFundingFetcher/1.0 (+https://neurotech-hub.local)",
            "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.2",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_sec), 1.0)) as resp:
            content_type = resp.headers.get("Content-Type")
            body = resp.read(max(int(max_bytes), 1) + 1)
            final_url = resp.geturl()
            status_code = getattr(resp, "status", None) or resp.getcode()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return FundingFetchResult(requested_url=url, error=str(exc), fetched_at=datetime.now(timezone.utc))

    if len(body) > max_bytes:
        return FundingFetchResult(
            requested_url=url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            fetched_at=datetime.now(timezone.utc),
            error=f"Response exceeded maximum size of {max_bytes} bytes.",
        )
    if content_type and _looks_binary(content_type):
        return FundingFetchResult(
            requested_url=url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            fetched_at=datetime.now(timezone.utc),
            error=f"Unsupported content type: {content_type}.",
        )

    page_text = extract_funding_page_text(body, content_type=content_type, max_chars=max_chars)
    return FundingFetchResult(
        requested_url=url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        fetched_at=datetime.now(timezone.utc),
        page_text=page_text,
    )


def _looks_binary(content_type: str) -> bool:
    lowered = content_type.lower()
    allowed = ("text/html", "text/plain", "application/xhtml+xml", "application/xml", "text/xml")
    if any(kind in lowered for kind in allowed):
        return False
    return any(kind in lowered for kind in ("pdf", "zip", "octet-stream", "image/", "audio/", "video/"))


def _reject_private_host(url: str, *, allow_private_hosts: bool) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("URL is missing a host.")
    if allow_private_hosts:
        return
    if host.lower() in {"localhost"}:
        raise ValueError("Private or localhost funding fetch hosts are disabled.")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {host}.") from exc
    for row in addresses:
        ip = ipaddress.ip_address(row[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Private or localhost funding fetch hosts are disabled.")
