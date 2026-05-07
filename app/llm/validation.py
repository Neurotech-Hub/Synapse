from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ingest.llm_common import parse_model_json_object

COMMON_REQUIRED = ("schema_version", "confidence")

PROMPT_SCHEMAS: dict[str, dict[str, Any]] = {
    "funding_extract": {
        "required": COMMON_REQUIRED + ("title", "public_summary", "topic_tags", "method_tags"),
        "list_fields": ("topic_tags", "method_tags", "missing_information", "warnings"),
        "scores": ("confidence",),
    },
    "funding_effort_classify": {
        "required": COMMON_REQUIRED + ("effort_index", "effort_rationale"),
        "enums": {"effort_index": {"mild", "moderate", "heavy", "unknown"}},
        "scores": ("confidence", "effort_score"),
        "list_fields": ("missing_information", "warnings"),
    },
    "funding_public_card": {
        "required": COMMON_REQUIRED + ("display_title", "short_summary", "effort_label", "not_enough_information"),
        "enums": {"effort_label": {"mild", "moderate", "heavy", "unknown"}},
        "scores": ("confidence",),
        "list_fields": ("best_for", "tags", "topic_tags", "method_tags", "missing_information", "warnings"),
    },
    "public_entity_summary": {
        "required": COMMON_REQUIRED + ("display_summary",),
        "scores": ("confidence",),
        "list_fields": ("research_themes", "methods", "public_caveats", "warnings"),
    },
    "public_place_summary": {
        "required": COMMON_REQUIRED + ("display_summary",),
        "scores": ("confidence",),
        "list_fields": ("research_themes", "organizations", "public_caveats", "warnings"),
    },
}


@dataclass
class StructuredOutputValidation:
    data: dict[str, Any] | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.errors


def parse_and_validate_prompt_json(prompt_name: str, raw_text: str, *, clamp_scores: bool = True) -> StructuredOutputValidation:
    data = parse_model_json_object(raw_text)
    if data is None:
        return StructuredOutputValidation(data=None, errors=["Could not parse JSON object from model output."])
    return validate_prompt_json(prompt_name, data, clamp_scores=clamp_scores)


def validate_prompt_json(prompt_name: str, data: dict[str, Any], *, clamp_scores: bool = True) -> StructuredOutputValidation:
    schema = PROMPT_SCHEMAS.get(prompt_name)
    if schema is None:
        return StructuredOutputValidation(data=data, errors=[f"No validation schema registered for prompt: {prompt_name}."])

    errors: list[str] = []
    warnings: list[str] = []
    normalized = dict(data)

    for field_name in schema.get("required", ()):
        if field_name not in normalized:
            errors.append(f"Missing required field: {field_name}.")

    for field_name, allowed in (schema.get("enums") or {}).items():
        if field_name in normalized and normalized[field_name] not in allowed:
            errors.append(f"Invalid {field_name}: {normalized[field_name]}.")

    for field_name in schema.get("list_fields", ()):
        if field_name in normalized and normalized[field_name] is not None and not isinstance(normalized[field_name], list):
            errors.append(f"Field must be a list: {field_name}.")

    for field_name in schema.get("scores", ()):
        if field_name not in normalized or normalized[field_name] is None:
            continue
        try:
            value = float(normalized[field_name])
        except (TypeError, ValueError):
            errors.append(f"Field must be numeric 0.0-1.0: {field_name}.")
            continue
        if value < 0.0 or value > 1.0:
            if clamp_scores:
                normalized[field_name] = min(max(value, 0.0), 1.0)
                warnings.append(f"Clamped {field_name} to 0.0-1.0.")
            else:
                errors.append(f"Field outside 0.0-1.0: {field_name}.")

    return StructuredOutputValidation(data=normalized, errors=errors, warnings=warnings)
