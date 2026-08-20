"""The core mechanism under test (plan.md "Problem 2"): compile a coding manual into
a provider structured-output schema, and hard-validate that a parsed response's
coding-sheet row IDs exactly match what was requested.

Both functions here are pure — no network, no filesystem — so the mechanism can be
proven correct with hand-written fake responses before spending a single API call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .manual import CodingManual, FieldSpec


# Two response-schema dialects share this same builder: Gemini's `responseSchema`
# (uppercase type names, e.g. "STRING"/"OBJECT"/"ARRAY") and standard JSON Schema
# (lowercase, "string"/"object"/"array") used for OpenRouter/OpenAI-style
# `response_format.json_schema.schema`. Everything else about the shape — which
# fields are required, evidence-per-field — is identical across both; only the
# type-name casing differs, so one builder parameterized by dialect serves both
# rather than duplicating the whole schema-construction logic per provider.
GEMINI_TYPE = {
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "object": "OBJECT",
    "array": "ARRAY",
}
JSON_SCHEMA_TYPE = {
    "string": "string",
    "number": "number",
    "integer": "integer",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
}
DIALECTS = {"gemini": GEMINI_TYPE, "json_schema": JSON_SCHEMA_TYPE}


def _value_schema(spec: FieldSpec, type_map: dict[str, str]) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": type_map[spec.type]}
    if spec.levels:
        schema["enum"] = [level.value for level in spec.levels]
    return schema


def _coded_field_schema(name: str, spec: FieldSpec, type_map: dict[str, str]) -> dict[str, Any]:
    properties: dict[str, Any] = {"value": _value_schema(spec, type_map)}
    required = ["value"]
    if spec.evidence_required:
        properties["evidence"] = {
            "type": type_map["string"],
            "description": "Page number and/or short quotation supporting this value.",
        }
        required.append("evidence")
    return {
        "type": type_map["object"],
        "description": spec.description or f"Coded value for `{name}`.",
        "properties": properties,
        "required": required,
    }


def build_response_schema(manual: CodingManual, *, dialect: str = "gemini") -> dict[str, Any]:
    """Compile `manual.effects` into a structured-output response schema.

    The coding sheet's own columns (paper identification, effect ID, effect
    location) are deliberately excluded — they are never requested of the model
    and are rejoined from the coding sheet at collation time.

    `required` only ever lists the fields actually marked required in the
    manual — never every property (which OpenAI/OpenRouter's `strict: true`
    json_schema mode demands, forcing optional fields to be modeled as
    nullable instead of absent). Provider adapters using this in "json_schema"
    dialect must NOT set `strict: true`, or a manual with any optional effect
    field will be rejected by the provider.
    """

    if dialect not in DIALECTS:
        raise ValueError(f"Unknown schema dialect: {dialect!r} (use one of {sorted(DIALECTS)}).")
    type_map = DIALECTS[dialect]

    if not manual.effects:
        raise ValueError("The coding manual must define at least one effect field.")

    effect_properties: dict[str, Any] = {
        "row_id": {
            "type": type_map["string"],
            "description": (
                "Must exactly match one of the requested coding-sheet row IDs. "
                "Never invent, rename, or omit this value."
            ),
        }
    }
    required = ["row_id"]
    for name, spec in manual.effects.items():
        effect_properties[name] = _coded_field_schema(name, spec, type_map)
        if spec.required:
            required.append(name)

    return {
        "type": type_map["object"],
        "properties": {
            "effects": {
                "type": type_map["array"],
                "description": "One entry per requested coding-sheet row.",
                "items": {
                    "type": type_map["object"],
                    "properties": effect_properties,
                    "required": required,
                },
            }
        },
        "required": ["effects"],
    }


@dataclass
class ValidationResult:
    ok: bool
    coded_by_row_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_ids: set[str] = field(default_factory=set)
    extra_ids: set[str] = field(default_factory=set)
    error: str | None = None

    @property
    def needs_review(self) -> bool:
        return not self.ok


def validate_response(parsed: object, requested_row_ids: set[str]) -> ValidationResult:
    """Hard-validate a parsed response against the coding-sheet rows that were
    requested for one PDF.

    Deliberately does NOT trust positional alignment: the returned row_id set must
    equal the requested set exactly, or the whole PDF is flagged needs_review. A
    mismatch is never partially accepted — see plan.md "Problem 2" for why.
    """

    if not isinstance(parsed, dict):
        return ValidationResult(ok=False, error="Response is not a JSON object.")
    effects = parsed.get("effects")
    if not isinstance(effects, list):
        return ValidationResult(ok=False, error="Response is missing an `effects` array.")

    coded_by_row_id: dict[str, dict[str, Any]] = {}
    returned_ids: set[str] = set()
    for index, item in enumerate(effects, start=1):
        if not isinstance(item, dict) or not str(item.get("row_id") or "").strip():
            return ValidationResult(
                ok=False, error=f"effects[{index}] is missing a non-empty `row_id`."
            )
        row_id = str(item["row_id"]).strip()
        if row_id in returned_ids:
            return ValidationResult(ok=False, error=f"Duplicate row_id in response: `{row_id}`.")
        returned_ids.add(row_id)
        coded_by_row_id[row_id] = {k: v for k, v in item.items() if k != "row_id"}

    if returned_ids != requested_row_ids:
        return ValidationResult(
            ok=False,
            coded_by_row_id=coded_by_row_id,
            missing_ids=requested_row_ids - returned_ids,
            extra_ids=returned_ids - requested_row_ids,
            error="Returned row_id set does not match the requested set.",
        )

    return ValidationResult(ok=True, coded_by_row_id=coded_by_row_id)
