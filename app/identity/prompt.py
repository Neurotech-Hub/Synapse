"""Load bundled person identity prompts."""

from __future__ import annotations

from pathlib import Path


def prompts_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "prompts"


def load_person_identity_prompt() -> str:
    path = prompts_dir() / "person_identity.txt"
    return path.read_text(encoding="utf-8")


def build_person_identity_prompt(
    *,
    person_blob: str,
    content_chunks: str,
    rebuild_mode: str = "full",
    previous_persona_json: str | None = None,
) -> str:
    t = load_person_identity_prompt()
    body = t.replace("{{person_blob}}", person_blob).replace("{{content_chunks}}", content_chunks)
    mode = (rebuild_mode or "full").strip().lower()
    prefix = ""
    if mode == "incremental" and previous_persona_json and previous_persona_json.strip():
        prefix = (
            "INCREMENTAL UPDATE MODE:\n"
            "Revise the persona using the evidence below. Keep stable sections unless new evidence warrants change.\n\n"
            f"CURRENT_PERSONA_JSON:\n{previous_persona_json.strip()}\n\n---\n\n"
        )
    elif mode == "light_refresh":
        prefix = (
            "LIGHT REFRESH MODE:\n"
            "Make small, targeted updates from the newest evidence. Do not discard a sound prior synthesis if not contradicted.\n\n"
        )
    return prefix + body


def load_organization_persona_prompt() -> str:
    path = prompts_dir() / "organization_persona.txt"
    return path.read_text(encoding="utf-8")


def load_place_persona_prompt() -> str:
    path = prompts_dir() / "place_persona.txt"
    return path.read_text(encoding="utf-8")


def build_organization_persona_prompt(
    *,
    organization_blob: str,
    member_personas_json: str,
    source_excerpts: str,
    rebuild_mode: str = "full",
    previous_persona_json: str | None = None,
) -> str:
    t = load_organization_persona_prompt()
    body = (
        t.replace("{{organization_blob}}", organization_blob)
        .replace("{{member_personas_json}}", member_personas_json)
        .replace("{{source_excerpts}}", source_excerpts)
    )
    mode = (rebuild_mode or "full").strip().lower()
    if mode == "incremental" and previous_persona_json and previous_persona_json.strip():
        prefix = (
            "INCREMENTAL ORG PERSONA UPDATE:\n"
            "Current stored organization persona JSON follows. Integrate PRIMARY EVIDENCE; keep mission-level notes stable unless evidence updates scope.\n\n"
            f"CURRENT_ORG_PERSONA_JSON:\n{previous_persona_json.strip()}\n\n---\n\n"
        )
        return prefix + body
    if mode == "light_refresh":
        return (
            "LIGHT REFRESH (organization): Minor synthesis updates only from PRIMARY EVIDENCE.\n\n" + body
        )
    return body


def build_place_persona_prompt(
    *,
    place_blob: str,
    member_personas_json: str,
    source_excerpts: str,
    rebuild_mode: str = "full",
    previous_persona_json: str | None = None,
) -> str:
    t = load_place_persona_prompt()
    body = (
        t.replace("{{place_blob}}", place_blob)
        .replace("{{member_personas_json}}", member_personas_json)
        .replace("{{source_excerpts}}", source_excerpts)
    )
    mode = (rebuild_mode or "full").strip().lower()
    if mode == "incremental" and previous_persona_json and previous_persona_json.strip():
        prefix = (
            "INCREMENTAL PLACE PERSONA UPDATE:\n"
            "Current stored place persona JSON follows. Merge new evidence; preserve stable facility/place framing.\n\n"
            f"CURRENT_PLACE_PERSONA_JSON:\n{previous_persona_json.strip()}\n\n---\n\n"
        )
        return prefix + body
    if mode == "light_refresh":
        return "LIGHT REFRESH (place): Minor updates to place-level synthesis only.\n\n" + body
    return body


def load_html_page_ingest_prompt() -> str:
    path = prompts_dir() / "html_page_ingest.txt"
    return path.read_text(encoding="utf-8")


def build_html_page_ingest_prompt(
    *, page_url: str, page_title_hint: str, plaintext_excerpt: str, target_chars: int
) -> str:
    t = load_html_page_ingest_prompt()
    return (
        t.replace("{{page_url}}", page_url)
        .replace("{{page_title_hint}}", page_title_hint)
        .replace("{{plaintext_excerpt}}", plaintext_excerpt)
        .replace("{{target_chars}}", str(target_chars))
    )
