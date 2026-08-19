"""Coding manual = extraction schema, parsed from YAML.

See plan.md "Problem 1". A coding manual is the single source of truth for what
gets coded: an `effect_definition` (what comparison counts as "the effect" for this
meta-analysis), a set of `coding_sheet_fields` (supplied by the coding sheet, never
asked of the LLM), and a set of `effects` fields (LLM-coded, each optionally
categorical via `levels`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_TYPES = {"string", "number", "integer", "boolean"}


class ManualError(ValueError):
    """Raised for any structurally invalid coding manual."""


@dataclass
class Level:
    value: str
    description: str | None = None


@dataclass
class FieldSpec:
    type: str
    description: str | None = None
    required: bool = False
    levels: list[Level] = field(default_factory=list)
    evidence_required: bool = True

    @property
    def is_categorical(self) -> bool:
        return bool(self.levels)


@dataclass
class CodingManual:
    name: str
    description: str | None
    effect_definition: str
    coding_sheet_fields: dict[str, FieldSpec]
    effects: dict[str, FieldSpec]
    raw_text: str = ""


def _require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ManualError(f"`{label}` must be a mapping.")
    return value


def _parse_levels(raw: object, field_name: str) -> list[Level]:
    if raw is None or raw == []:
        # An empty list means "no levels" (the structured editor always sends
        # `levels: []` for non-categorical fields) — only a non-empty non-list
        # value is a real error.
        return []
    if not isinstance(raw, list):
        raise ManualError(f"effects.{field_name}.levels must be a list.")
    levels: list[Level] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict) or "value" not in entry:
            raise ManualError(
                f"effects.{field_name}.levels[{index}] must be a mapping with a `value` key."
            )
        value = str(entry["value"]).strip()
        if not value:
            raise ManualError(f"effects.{field_name}.levels[{index}].value cannot be empty.")
        if value in seen:
            raise ManualError(f"effects.{field_name}.levels has a duplicate value: `{value}`.")
        seen.add(value)
        description = entry.get("description")
        levels.append(Level(value=value, description=str(description) if description else None))
    return levels


def _parse_field(name: str, raw: object, section: str) -> FieldSpec:
    if not isinstance(raw, dict):
        raise ManualError(f"{section}.{name} must be a mapping.")
    field_type = str(raw.get("type") or "string").strip().lower()
    if field_type not in SUPPORTED_TYPES:
        raise ManualError(
            f"{section}.{name}.type `{field_type}` is not supported "
            f"(use one of: {', '.join(sorted(SUPPORTED_TYPES))})."
        )
    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise ManualError(f"{section}.{name}.required must be true or false.")
    evidence_required = raw.get("evidence_required", True)
    if not isinstance(evidence_required, bool):
        raise ManualError(f"{section}.{name}.evidence_required must be true or false.")
    levels = _parse_levels(raw.get("levels"), name) if section == "effects" else []
    if levels and field_type != "string":
        raise ManualError(f"effects.{name} has `levels` but type is not `string`.")
    description = raw.get("description")
    return FieldSpec(
        type=field_type,
        description=str(description).strip() if description else None,
        required=required,
        levels=levels,
        evidence_required=evidence_required,
    )


def _parse_section(raw: object, section: str, *, allow_empty: bool) -> dict[str, FieldSpec]:
    if raw is None:
        if allow_empty:
            return {}
        raise ManualError(f"`{section}` must contain at least one field.")
    mapping = _require_mapping(raw, section)
    if not mapping and not allow_empty:
        raise ManualError(f"`{section}` must contain at least one field.")
    out: dict[str, FieldSpec] = {}
    for name, spec in mapping.items():
        field_name = str(name or "").strip()
        if not field_name:
            raise ManualError(f"Every field in `{section}` must be named.")
        out[field_name] = _parse_field(field_name, spec, section)
    return out


def _build_manual_from_raw(raw: object, *, raw_text: str = "") -> CodingManual:
    """Shared validation core: `raw` is the plain dict/list structure produced by
    either yaml.safe_load (text path) or json.loads (structured-editor path) — both
    parse into the same basic Python types, so one validator serves both.
    """

    if not isinstance(raw, dict):
        raise ManualError("The coding manual must contain a top-level mapping.")

    effect_definition = str(raw.get("effect_definition") or "").strip()
    if not effect_definition:
        raise ManualError(
            "`effect_definition` is required: state what comparison counts as "
            "\"the effect\" for this meta-analysis, e.g. \"the difference in response "
            "times between compatible and incompatible trials.\""
        )

    name = str(raw.get("name") or "untitled_meta_analysis").strip()
    description = raw.get("description")

    coding_sheet_fields = _parse_section(
        raw.get("coding_sheet_fields"), "coding_sheet_fields", allow_empty=True
    )
    effects = _parse_section(raw.get("effects"), "effects", allow_empty=False)

    overlap = set(coding_sheet_fields) & set(effects)
    if overlap:
        raise ManualError(
            "Fields cannot appear in both `coding_sheet_fields` and `effects`: "
            + ", ".join(sorted(overlap))
        )

    return CodingManual(
        name=name,
        description=str(description).strip() if description else None,
        effect_definition=effect_definition,
        coding_sheet_fields=coding_sheet_fields,
        effects=effects,
        raw_text=raw_text,
    )


def parse_coding_manual(text: str) -> CodingManual:
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        problem = str(getattr(exc, "problem", "") or "The YAML could not be parsed.")
        if mark is not None:
            raise ManualError(
                f"Invalid YAML at line {mark.line + 1}, column {mark.column + 1}: {problem}"
            ) from exc
        raise ManualError(f"Invalid YAML: {problem}") from exc
    return _build_manual_from_raw(raw, raw_text=text)


def read_coding_manual(path: Path) -> CodingManual:
    if not path.is_file():
        raise FileNotFoundError(f"Coding manual not found: {path}")
    return parse_coding_manual(path.read_text(encoding="utf-8"))


# --- Structured-editor payload <-> CodingManual -----------------------------
# The GUI editor (project.html) is the only user-facing way to edit a manual — see
# plan.md "Problem 1". It works with a JSON-friendly, list-based shape (arrays are
# natural for add/remove/reorder in JS) rather than the YAML file's dict-keyed
# shape; these functions convert between the two. The YAML file on disk stays the
# storage format (plan.md: "the manual *is* the schema"), just never hand-edited.

def _payload_list_to_mapping(items: object, section: str) -> dict:
    if not isinstance(items, list):
        raise ManualError(f"`{section}` must be a list.")
    out: dict[str, dict] = {}
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ManualError(f"{section}[{index}] must be an object.")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ManualError(f"{section}[{index}] is missing a field name.")
        if name in out:
            raise ManualError(f"`{section}` has a duplicate field name: `{name}`.")
        out[name] = {k: v for k, v in item.items() if k != "name"}
    return out


def manual_from_editor_payload(payload: object) -> CodingManual:
    if not isinstance(payload, dict):
        raise ManualError("Invalid manual data.")
    raw = {
        "name": payload.get("name"),
        "description": payload.get("description"),
        "effect_definition": payload.get("effect_definition"),
        "coding_sheet_fields": _payload_list_to_mapping(
            payload.get("coding_sheet_fields") or [], "coding_sheet_fields"
        ),
        "effects": _payload_list_to_mapping(payload.get("effects") or [], "effects"),
    }
    return _build_manual_from_raw(raw)


def _field_to_payload(name: str, spec: FieldSpec) -> dict[str, Any]:
    return {
        "name": name,
        "type": spec.type,
        "description": spec.description or "",
        "required": spec.required,
        "evidence_required": spec.evidence_required,
        "levels": [{"value": level.value, "description": level.description or ""} for level in spec.levels],
    }


def manual_to_editor_payload(manual: CodingManual) -> dict[str, Any]:
    return {
        "name": manual.name,
        "description": manual.description or "",
        "effect_definition": manual.effect_definition,
        "coding_sheet_fields": [
            _field_to_payload(name, spec) for name, spec in manual.coding_sheet_fields.items()
        ],
        "effects": [_field_to_payload(name, spec) for name, spec in manual.effects.items()],
    }


def manual_to_yaml_text(manual: CodingManual) -> str:
    """Serialize a CodingManual to YAML for on-disk storage, via PyYAML (not a
    hand-rolled emitter) so quoting/escaping is always correct."""

    def field_dict(spec: FieldSpec) -> dict[str, Any]:
        out: dict[str, Any] = {"type": spec.type}
        if spec.description:
            out["description"] = spec.description
        if spec.required:
            out["required"] = True
        if not spec.evidence_required:
            out["evidence_required"] = False
        if spec.levels:
            out["levels"] = [
                ({"value": level.value, "description": level.description} if level.description else {"value": level.value})
                for level in spec.levels
            ]
        return out

    data: dict[str, Any] = {"name": manual.name}
    if manual.description:
        data["description"] = manual.description
    data["effect_definition"] = manual.effect_definition
    if manual.coding_sheet_fields:
        data["coding_sheet_fields"] = {
            name: field_dict(spec) for name, spec in manual.coding_sheet_fields.items()
        }
    data["effects"] = {name: field_dict(spec) for name, spec in manual.effects.items()}

    return yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
