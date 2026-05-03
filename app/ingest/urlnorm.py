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


def url_origin_group_key(url: str) -> str:
    """Stable ``scheme://host[:port]`` for sorting and grouping URLs from one site.

    Host and optional non-default port follow the same rules as :func:`canonical_url`.
    Malformed URLs map to ``"~other"`` so they sort last.

    Examples:
      ``https://Example.com/rss`` and ``HTTPS://example.com/page`` → ``https://example.com``
    """

    if not url or not isinstance(url, str):
        return "~other"
    raw = url.strip()
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return "~other"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return "~other"

    scheme = parsed.scheme.lower()
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    authority = hostname + ("" if port in (None, default_port) else f":{port}")
    return f"{scheme}://{authority}"


def origin_section_labels(origin_key: str) -> tuple[str, str]:
    """Return ``(title, subtitle)`` for the admin sources list grouped by :func:`url_origin_group_key`."""

    if origin_key == "~other":
        return (
            "Could not detect a site",
            "These rows don’t share a normal hostname — URLs may be incomplete or unusual.",
        )
    parsed = urlparse(origin_key)
    netloc = parsed.netloc or ""
    scheme = (parsed.scheme or "https").lower()
    if not netloc:
        return (origin_key, "")
    title = netloc
    subtitle = f"{scheme}://{netloc}"
    return (title, subtitle)
