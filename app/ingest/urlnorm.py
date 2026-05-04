"""Normalize submitted URLs so duplicates map to one row."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Dropped from stored / catalog links (PubMed RSS, newsletters, etc.).
_CATALOG_TRACKING_KEYS = frozenset(
    k.lower()
    for k in (
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "utm_id",
        "gclid",
        "fbclid",
        "mc_eid",
        "fc",
        "ff",
        "v",
    )
)


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


def stable_catalog_url(raw: str | None) -> str | None:
    """Canonical href for dedupe and public display: PubMed/DOI identity, strip tracking elsewhere.

    Returns ``None`` when input is empty or unusable. Never raises for bad URLs (falls back to stripped string).
    """

    if raw is None or not str(raw).strip():
        return None
    raw = str(raw).strip()
    try:
        cu = canonical_url(raw)
    except UrlValidationError:
        s = raw.split("#", 1)[0].strip()
        return s or None

    p = urlparse(cu)
    host = (p.hostname or "").lower()
    parts = [x for x in (p.path or "").split("/") if x]

    if host in ("pubmed.ncbi.nlm.nih.gov", "www.pubmed.ncbi.nlm.nih.gov") or (
        host.endswith(".ncbi.nlm.nih.gov") and "pubmed" in host
    ):
        if parts and parts[0].isdigit() and 5 <= len(parts[0]) <= 12:
            return f"https://pubmed.ncbi.nlm.nih.gov/{parts[0]}/"

    if host in ("doi.org", "dx.doi.org") and parts:
        return f"https://doi.org/{'/'.join(parts)}"

    pairs = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in _CATALOG_TRACKING_KEYS
    ]
    pairs.sort(key=lambda kv: kv[0].lower())
    q = urlencode(pairs)
    scheme = (p.scheme or "https").lower()
    netloc = host
    if p.port and not ((scheme == "https" and p.port == 443) or (scheme == "http" and p.port == 80)):
        netloc = f"{host}:{p.port}"
    path = p.path or "/"
    clean = urlunparse((scheme, netloc, path, "", q, ""))
    return clean.rstrip("/") or None


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
