"""Normalize submitted URLs so duplicates map to one row."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


class UrlValidationError(ValueError):
    pass


def canonical_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise UrlValidationError("URL is empty")

    normalized = raw
    if "://" not in normalized:
        normalized = "https://" + normalized.lstrip("/")

    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https"):
        raise UrlValidationError("Only http and https URLs are allowed.")

    netloc = (parsed.hostname or "").lower()
    if not netloc:
        raise UrlValidationError("URL is missing a host.")

    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    authority = netloc + ("" if port in (None, default_port) else f":{port}")

    path = parsed.path or "/"
    cleaned = urlunparse(
        (parsed.scheme, authority, path, "", parsed.query, "")  # drop fragment always
    )
    return cleaned
