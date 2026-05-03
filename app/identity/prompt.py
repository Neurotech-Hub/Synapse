"""Load bundled person identity prompts."""

from __future__ import annotations

from pathlib import Path


def prompts_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "prompts"


def load_person_identity_prompt() -> str:
    path = prompts_dir() / "person_identity.txt"
    return path.read_text(encoding="utf-8")


def build_person_identity_prompt(*, person_blob: str, content_chunks: str) -> str:
    t = load_person_identity_prompt()
    return t.replace("{{person_blob}}", person_blob).replace("{{content_chunks}}", content_chunks)


def load_organization_persona_prompt() -> str:
    path = prompts_dir() / "organization_persona.txt"
    return path.read_text(encoding="utf-8")


def load_place_persona_prompt() -> str:
    path = prompts_dir() / "place_persona.txt"
    return path.read_text(encoding="utf-8")


def build_organization_persona_prompt(
    *, organization_blob: str, member_personas_json: str, source_excerpts: str
) -> str:
    t = load_organization_persona_prompt()
    return (
        t.replace("{{organization_blob}}", organization_blob)
        .replace("{{member_personas_json}}", member_personas_json)
        .replace("{{source_excerpts}}", source_excerpts)
    )


def build_place_persona_prompt(
    *, place_blob: str, member_personas_json: str, source_excerpts: str
) -> str:
    t = load_place_persona_prompt()
    return (
        t.replace("{{place_blob}}", place_blob)
        .replace("{{member_personas_json}}", member_personas_json)
        .replace("{{source_excerpts}}", source_excerpts)
    )
