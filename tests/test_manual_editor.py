from meta_coder.manual import (
    NOTES_FIELD_NAME,
    manual_from_editor_payload,
    manual_to_editor_payload,
    manual_to_yaml_text,
    parse_coding_manual,
)


MANUAL_YAML = """
name: stroop_test
effect_definition: The difference in RT between compatible and incompatible trials.
effects:
  Condition:
    type: string
    required: true
    levels:
      - {value: "No", description: Not incompatible.}
      - {value: "Yes", description: Incompatible.}
  ResponseTimeMs:
    type: number
    evidence_required: false
"""


def test_manual_to_editor_payload_is_json_safe_round_trip():
    manual = parse_coding_manual(MANUAL_YAML)
    payload = manual_to_editor_payload(manual)
    # Must survive an actual JSON round-trip, since this is exactly what the
    # browser does (JSON.stringify -> POST -> json.loads server-side).
    import json

    round_tripped = json.loads(json.dumps(payload))
    rebuilt = manual_from_editor_payload(round_tripped)

    assert rebuilt.effect_definition == manual.effect_definition
    assert set(rebuilt.effects) == {"Condition", "ResponseTimeMs", "notes"}
    assert [level.value for level in rebuilt.effects["Condition"].levels] == ["No", "Yes"]
    assert rebuilt.effects["ResponseTimeMs"].evidence_required is False


def test_manual_from_editor_payload_rejects_duplicate_field_names():
    payload = {
        "effect_definition": "x",
        "effects": [
            {"name": "Age", "type": "string"},
            {"name": "Age", "type": "number"},
        ],
    }
    try:
        manual_from_editor_payload(payload)
        assert False, "expected ManualError"
    except Exception as exc:
        assert "duplicate" in str(exc).lower()


def test_notes_field_is_always_added_and_required():
    manual = parse_coding_manual(MANUAL_YAML)
    notes = manual.effects[NOTES_FIELD_NAME]
    assert notes.required is True
    assert notes.evidence_required is False


def test_notes_field_cannot_be_redefined_or_removed():
    # An attempt to redefine `notes` (wrong type, not required, with levels) is
    # silently overridden back to the canonical spec rather than honored — the
    # field's whole point is that it's always present in the same shape.
    payload = {
        "effect_definition": "x",
        "effects": [
            {"name": "Age", "type": "string"},
            {"name": NOTES_FIELD_NAME, "type": "boolean", "required": False},
        ],
    }
    manual = manual_from_editor_payload(payload)
    notes = manual.effects[NOTES_FIELD_NAME]
    assert notes.type == "string"
    assert notes.required is True
    assert notes.evidence_required is False

    # Omitting it entirely still results in it being present.
    payload_without_notes = {
        "effect_definition": "x",
        "effects": [{"name": "Age", "type": "string"}],
    }
    manual = manual_from_editor_payload(payload_without_notes)
    assert NOTES_FIELD_NAME in manual.effects


def test_manual_to_yaml_text_produces_reparseable_yaml_with_yes_no_levels():
    # "No"/"Yes" are YAML 1.1 boolean words — this is the exact case that broke a
    # hand-rolled emitter would need to get right; PyYAML's dump handles it.
    manual = parse_coding_manual(MANUAL_YAML)
    text = manual_to_yaml_text(manual)
    reparsed = parse_coding_manual(text)
    assert [level.value for level in reparsed.effects["Condition"].levels] == ["No", "Yes"]
    assert reparsed.effect_definition == manual.effect_definition
