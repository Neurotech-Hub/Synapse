"""Structured prompt output validation tests."""

from app.llm.validation import parse_and_validate_prompt_json, validate_prompt_json


def test_validate_effort_output_accepts_valid_json():
    result = validate_prompt_json(
        "funding_effort_classify",
        {
            "schema_version": "1.0",
            "effort_index": "moderate",
            "effort_score": 0.55,
            "effort_rationale": "Standard proposal burden.",
            "confidence": 0.7,
            "missing_information": [],
            "warnings": [],
        },
    )

    assert result.ok
    assert result.data["effort_index"] == "moderate"


def test_validate_effort_output_rejects_invalid_enum():
    result = validate_prompt_json(
        "funding_effort_classify",
        {
            "schema_version": "1.0",
            "effort_index": "none",
            "effort_rationale": "No burden.",
            "confidence": 0.7,
            "missing_information": [],
            "warnings": [],
        },
    )

    assert not result.ok
    assert any("Invalid effort_index" in err for err in result.errors)


def test_validate_clamps_scores_and_records_warning():
    result = validate_prompt_json(
        "match_funding_to_entity",
        {
            "schema_version": "1.0",
            "match_score": 1.4,
            "rationale": "Strong fit.",
            "recommended_next_step": "review",
            "confidence": -0.2,
            "supporting_points": [],
            "concerns": [],
            "missing_information": [],
            "warnings": [],
        },
    )

    assert result.ok
    assert result.data["match_score"] == 1.0
    assert result.data["confidence"] == 0.0
    assert len(result.warnings) == 2


def test_parse_and_validate_tolerates_fenced_json():
    raw = """```json
{"schema_version":"1.0","display_title":"Pilot","short_summary":"Short","effort_label":"mild","confidence":0.9,"best_for":[],"tags":[],"warnings":[]}
```"""
    result = parse_and_validate_prompt_json("funding_public_card", raw)

    assert result.ok
    assert result.data["display_title"] == "Pilot"


def test_validation_reports_missing_fields():
    result = validate_prompt_json("collaboration_hypothesis", {"schema_version": "1.0", "confidence": 0.5})

    assert not result.ok
    assert "Missing required field: title." in result.errors
    assert "Missing required field: recommended_action." in result.errors
