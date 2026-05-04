"""Thin Ollama HTTP client (stdlib). Failures propagate to callers for graceful fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
GENERATE_TIMEOUT = 120.0
LEAD_REPORT_GENERATE_TIMEOUT = float(os.environ.get("SYNAPSE_LEAD_REPORT_OLLAMA_TIMEOUT", "900") or "900")
PUBLIC_DIGEST_GENERATE_TIMEOUT = float(os.environ.get("SYNAPSE_PUBLIC_DIGEST_OLLAMA_TIMEOUT", "300") or "300")
PUBLIC_FEED_CURATE_GENERATE_TIMEOUT = float(
    os.environ.get("SYNAPSE_PUBLIC_FEED_CURATE_OLLAMA_TIMEOUT", "180") or "180"
)
TAGS_TIMEOUT_SEC = 3.0


def fetch_ollama_tags(*, timeout: float | None = None) -> dict[str, Any] | None:
    """Parse JSON from GET /api/tags, or None if unreachable / invalid."""
    t = TAGS_TIMEOUT_SEC if timeout is None else timeout
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=t) as resp:
            body = resp.read().decode()
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError):
        return None


def _tag_base_name(ollama_name: str) -> str:
    return ollama_name.split(":", 1)[0].strip()


def _tags_include_model(tags: dict[str, Any], want: str) -> bool:
    want_base = _tag_base_name(want)
    for m in tags.get("models") or []:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "")
        if _tag_base_name(name) == want_base:
            return True
    return False


def ollama_available() -> bool:
    return fetch_ollama_tags() is not None


def ollama_admin_status() -> dict[str, Any]:
    """Snapshot for admin UI: API reachability and whether OLLAMA_MODEL is pulled."""
    tags = fetch_ollama_tags()
    if tags is None:
        return {
            "reachable": False,
            "model_ok": False,
            "host": OLLAMA_HOST,
            "model": OLLAMA_MODEL,
        }
    return {
        "reachable": True,
        "model_ok": _tags_include_model(tags, OLLAMA_MODEL),
        "host": OLLAMA_HOST,
        "model": OLLAMA_MODEL,
    }


def generate_non_stream(
    prompt: str,
    *,
    model: str | None = None,
    json_format: bool = False,
    options: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> str:
    m = model or OLLAMA_MODEL
    payload: dict[str, Any] = {"model": m, "prompt": prompt, "stream": False}
    if json_format:
        # Ollama API: constrains output to JSON (reduces prose-only replies for structured tasks).
        payload["format"] = "json"
    if options:
        payload["options"] = options
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    deadline = GENERATE_TIMEOUT if timeout is None else float(timeout)
    with urllib.request.urlopen(req, timeout=deadline) as resp:
        body = json.loads(resp.read().decode())
    return (body.get("response") or "").strip()


def _unwrap_json_root_dict(val: Any) -> dict[str, Any] | None:
    """Use a JSON object, or the first object inside a JSON array (common model quirk)."""

    if isinstance(val, dict):
        return val
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                return item
    return None


def _parse_model_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output; tolerate fences, chatter, trailing text, array wrappers."""

    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("```"):
        rest = t[3:].lstrip()
        if rest.lower().startswith("json"):
            rest = rest[4:].lstrip("\n ")
        fence = rest.rfind("```")
        if fence != -1:
            rest = rest[:fence]
        t = rest.strip()
    decoder = json.JSONDecoder()

    def _try_segment(s: str, start_idx: int) -> dict[str, Any] | None:
        head = start_idx
        while head < len(s) and s[head].isspace():
            head += 1
        if head >= len(s) or s[head] not in "{[":
            return None
        try:
            parsed, _end = decoder.raw_decode(s, head)
        except json.JSONDecodeError:
            return None
        return _unwrap_json_root_dict(parsed)

    # Scan each `{`/`[` in case the model added a preamble or trailing explanation
    for i, ch in enumerate(t):
        if ch in "{[":
            got = _try_segment(t, i)
            if got is not None:
                return got
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(t[start : end + 1])
            return _unwrap_json_root_dict(data)
        except json.JSONDecodeError:
            pass
    return None


def html_page_llm_prompt_char_budget() -> int:
    """Max characters of plaintext from the page appended to the summarization prompt (env override)."""

    raw = (os.environ.get("SYNAPSE_HTML_PAGE_LLM_PROMPT_CHARS") or "").strip()
    default = 56_000
    if not raw:
        return default
    try:
        return max(16_000, int(raw))
    except ValueError:
        return default


def html_page_llm_snippet_target_chars() -> int:
    """Guidance-only target length communicated to the model for `snippet` richness (env override)."""

    raw = (os.environ.get("SYNAPSE_HTML_PAGE_LLM_SNIPPET_TARGET_CHARS") or "").strip()
    default = 14_000
    if not raw:
        return default
    try:
        return max(4_096, int(raw))
    except ValueError:
        return default


def try_summarize_html_page(
    *,
    url: str,
    page_title_guess: str | None,
    plaintext_excerpt: str,
    max_prompt_chars: int | None = None,
) -> dict[str, Any] | None:
    """LLM condensation for html_page ingestion. Expected keys: title, snippet (paragraphs OK).

    Larger pages need more excerpt + a longer instructed snippet target so downstream lead reports
    and personas see concrete technical language, not brochure-level fluff.
    """
    budget = html_page_llm_prompt_char_budget() if max_prompt_chars is None else max(8_192, max_prompt_chars)
    excerpt = (plaintext_excerpt or "")[:budget].strip()
    title_hint = (page_title_guess or "").strip()[:400]
    target_snip = html_page_llm_snippet_target_chars()
    hard_snip_ceiling = target_snip + max(2400, target_snip // 4)
    prompt = (
        "You distill public web pages into a structured record for downstream research ingest and analytics. "
        "Return ONLY compact JSON without markdown fences. Keys exactly: "
        "title (short factual headline grounded in page content); "
        f"snippet (dense prose preserving technical specificity: numbered lists, capacities, tooling, specs, units, named programs, memberships, timelines. "
        f"Aim for roughly up to ~{target_snip} Unicode characters—use as much of that budget as warranted by the excerpt; "
        f"prefer staying under ~{hard_snip_ceiling} characters. Omit marketing fluff, generic mission statements-only if more concrete detail exists; merge duplicates). "
        "If the excerpt is sparse, faithfully summarize everything usable.\n"
        f"Page URL: {url}\nHTML title hint: {title_hint or '(none)'}\n"
        "Visible text excerpt (may be truncated):\n"
        f"{excerpt}"
    )
    try:
        text = generate_non_stream(prompt)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)


def _identity_uses_ollama_json_format() -> bool:
    v = (os.environ.get("SYNAPSE_OLLAMA_IDENTITY_JSON_FORMAT") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _identity_ollama_options() -> dict[str, Any] | None:
    """Larger prompts (PubMed backlogs) exceed default llama ``num_ctx`` — raise for identity-only calls."""

    raw_json = (os.environ.get("SYNAPSE_OLLAMA_IDENTITY_OPTIONS") or "").strip()
    if raw_json:
        try:
            extra = json.loads(raw_json)
        except json.JSONDecodeError:
            extra = {}
        if isinstance(extra, dict) and extra:
            opts: dict[str, Any] = {}
            for key, val in extra.items():
                if isinstance(key, str):
                    opts[key] = val
            return opts or None

    raw_ctx = (os.environ.get("SYNAPSE_OLLAMA_IDENTITY_NUM_CTX") or "32768").strip()
    if raw_ctx.lower() in ("0", "none", "off", "false"):
        return None
    try:
        n = int(raw_ctx)
    except ValueError:
        n = 32768
    if n <= 0:
        return None
    capped = max(4096, min(n, 262144))
    return {"num_ctx": capped}


def _generate_prompt_text(
    prompt: str,
    *,
    json_format: bool = False,
    options: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """Returns (trimmed_response, fetch_ok). On transport error, fetch_ok False and text ''."""

    try:
        text = generate_non_stream(prompt, json_format=json_format, options=options)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return "", False
    return text.strip(), True


def run_identity_llm(prompt: str) -> tuple[dict[str, Any] | None, str]:
    """Person persona JSON prompt → ``(dict|None, raw_model_text_if_any)``."""

    text, ok = _generate_prompt_text(
        prompt,
        json_format=_identity_uses_ollama_json_format(),
        options=_identity_ollama_options(),
    )
    if not ok:
        return None, ""
    parsed = _parse_model_json_object(text)
    return parsed, text


def _lead_report_num_ctx() -> int:
    raw = (os.environ.get("SYNAPSE_LEAD_REPORT_NUM_CTX") or "65536").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 65536
    return max(8192, min(n, 262144))


def run_lead_report_llm(prompt: str, *, json_format: bool = True) -> dict[str, Any] | None:
    """Long-context structured calls for Hub-centric lead reports (larger ``num_ctx`` + timeout)."""

    opts = {"num_ctx": _lead_report_num_ctx()}
    try:
        text = generate_non_stream(
            prompt,
            json_format=json_format,
            options=opts,
            timeout=LEAD_REPORT_GENERATE_TIMEOUT,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)


def _public_digest_num_ctx() -> int:
    raw = (os.environ.get("SYNAPSE_PUBLIC_DIGEST_NUM_CTX") or "32768").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 32768
    return max(8192, min(n, 131072))


def run_public_digest_llm(prompt: str) -> dict[str, Any] | None:
    """JSON-shaped public digest summaries (separate from lead reports)."""

    opts = {"num_ctx": _public_digest_num_ctx()}
    try:
        text = generate_non_stream(
            prompt,
            json_format=True,
            options=opts,
            timeout=PUBLIC_DIGEST_GENERATE_TIMEOUT,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)


def _public_feed_curate_num_ctx() -> int:
    raw = (os.environ.get("SYNAPSE_PUBLIC_FEED_CURATE_NUM_CTX") or "16384").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 16384
    return max(8192, min(n, 65536))


def run_public_feed_curate_llm(prompt: str) -> dict[str, Any] | None:
    """JSON object with ``results`` array for public Latest curation."""

    opts = {"num_ctx": _public_feed_curate_num_ctx()}
    try:
        text = generate_non_stream(
            prompt,
            json_format=True,
            options=opts,
            timeout=PUBLIC_FEED_CURATE_GENERATE_TIMEOUT,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)


def try_enrich_lead(title: str, link: str, snippet: str) -> dict[str, Any] | None:
    prompt = (
        "Return ONLY compact JSON without markdown fences. Keys exactly: "
        'headline, angle, outreach_snippet, hub_tags (comma-separated string).\n'
        f"Title: {title}\nURL: {link}\nSnippet: {snippet}"
    )
    try:
        text = generate_non_stream(prompt)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return _parse_model_json_object(text)
