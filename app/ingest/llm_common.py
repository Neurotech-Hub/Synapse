"""Shared JSON parsing for LLM outputs (Ollama, OpenAI, etc.)."""

from __future__ import annotations

import json
from typing import Any


def unwrap_json_root_dict(val: Any) -> dict[str, Any] | None:
    """Use a JSON object, or the first object inside a JSON array (common model quirk)."""

    if isinstance(val, dict):
        return val
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                return item
    return None


def parse_model_json_object(text: str) -> dict[str, Any] | None:
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
        return unwrap_json_root_dict(parsed)

    for i, ch in enumerate(t):
        if ch in "{[":
            got = _try_segment(t, i)
            if got is not None:
                return got
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(t[start : end + 1])
            return unwrap_json_root_dict(data)
        except json.JSONDecodeError:
            pass
    return None
