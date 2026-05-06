"""Prompt registry and rendering tests."""

import pytest

from app.llm.prompt_registry import (
    PROMPTS,
    effective_prompt_provider,
    get_prompt_spec,
    load_prompt_template,
    prompt_input_fingerprint,
    prompt_placeholders,
    render_prompt,
)


def test_all_registered_prompts_load():
    for name, spec in PROMPTS.items():
        body = load_prompt_template(name)
        assert spec.version
        assert spec.default_provider in {"ollama", "openai"}
        assert spec.output == "json"
        assert "Return valid JSON" in body or name == "json_repair"


def test_render_prompt_replaces_variables_and_requires_missing():
    placeholders = prompt_placeholders("funding_effort_classify")
    assert {"schema", "funding_extraction_json", "heuristic_effort_guess", "heuristic_rationale"} <= placeholders

    rendered = render_prompt(
        "funding_effort_classify",
        {
            "schema": {"effort_index": "mild|moderate|heavy|unknown"},
            "funding_extraction_json": {"title": "Seed grant"},
            "heuristic_effort_guess": "mild",
            "heuristic_rationale": "small seed award",
        },
    )
    assert "{{" not in rendered
    assert "Seed grant" in rendered
    assert "mild" in rendered

    with pytest.raises(KeyError):
        render_prompt("funding_effort_classify", {"schema": {}})


def test_prompt_fingerprint_changes_with_versioned_inputs():
    one = prompt_input_fingerprint("funding_public_card", {"funding_json": {"title": "A"}, "schema": {}})
    two = prompt_input_fingerprint("funding_public_card", {"funding_json": {"title": "B"}, "schema": {}})
    assert len(one) == 64
    assert one != two


def test_provider_override(monkeypatch):
    assert get_prompt_spec("public_entity_summary").default_provider == "ollama"
    monkeypatch.setenv("SYNAPSE_LLM_PUBLIC_ENTITY_SUMMARY_PROVIDER", "openai")
    assert effective_prompt_provider("public_entity_summary") == "openai"
