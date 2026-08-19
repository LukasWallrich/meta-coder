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


GEMINI_TYPE = {
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
}


def _value_schema(spec: FieldSpec) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": GEMINI_TYPE[spec.type]}
    if spec.levels:
        schema["enum"] = [level.value for level in spec.levels]
    return schema


def _coded_field_schema(name: str, spec: FieldSpec) -> dict[str, Any]:
    properties: dict[str, Any] = {"value": _value_schema(spec)}
    required = ["value"]
    if spec.evidence_required:
        properties["evidence"] = {
            "type": "STRING",
            "description": "Page number and/or short quotation supporting this value.",
        }
        required.append("evidence")
    return {
        "type": "OBJECT",
        "description": spec.description or f"Coded value for `{name}`.",
        "properties": properties,
        "required": required,
    }


def build_response_schema(manual: CodingManual) -> dict[str, Any]:
    """Compile `manual.effects` into a Gemini structured-output response schema.

    `coding_sheet_fields` are deliberately excluded — they are never requested of
    the model and are rejoined from the coding sheet at collation time.
    """

    if not manual.effects:
        raise ValueError("The coding manual must define at least one effect field.")

    effect_properties: dict[str, Any] = {
        "row_id": {
            "type": "STRING",
            "description": (
                "Must exactly match one of the requested coding-sheet row IDs. "
                "Never invent, rename, or omit this value."
            ),
        }
    }
    required = ["row_id"]
    for name, spec in manual.effects.items():
        effect_properties[name] = _coded_field_schema(name, spec)
        if spec.required:
            required.append(name)

    return {
        "type": "OBJECT",
        "properties": {
            "effects": {
                "type": "ARRAY",
                "description": "One entry per requested coding-sheet row.",
                "items": {
                    "type": "OBJECT",
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
