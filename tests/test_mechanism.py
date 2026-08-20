"""Proves the row_id/locator mechanism (plan.md "Problem 2") without any API call:
build_response_schema excludes the coding sheet's own columns and encodes levels
as enums; validate_response hard-rejects on any ID mismatch rather than trusting
order.
"""

from meta_coder.manual import parse_coding_manual
from meta_coder.mechanism import build_response_schema, validate_response


MANUAL_YAML = """
name: stroop_test
effect_definition: >
  The difference in response times between compatible and incompatible trials.
effects:
  Condition:
    type: string
    required: true
    levels:
      - {value: Color-word Stroop, description: Classic color/word interference.}
      - {value: Spatial Stroop, description: Spatial incongruence variant.}
  ResponseTimeMs:
    type: number
    description: Mean RT in milliseconds for the incompatible condition.
"""


def _manual():
    return parse_coding_manual(MANUAL_YAML)


def test_build_response_schema_excludes_coding_sheet_columns():
    schema = build_response_schema(_manual())
    item_properties = schema["properties"]["effects"]["items"]["properties"]
    assert "authors" not in item_properties
    assert "year" not in item_properties
    assert "locator" not in item_properties
    assert "row_id" in item_properties
    assert "Condition" in item_properties and "ResponseTimeMs" in item_properties


def test_build_response_schema_encodes_levels_as_enum():
    schema = build_response_schema(_manual())
    condition_value_schema = schema["properties"]["effects"]["items"]["properties"]["Condition"][
        "properties"
    ]["value"]
    assert condition_value_schema["enum"] == ["Color-word Stroop", "Spatial Stroop"]


def test_validate_response_accepts_exact_id_match():
    requested = {"row-1", "row-2", "row-3"}
    parsed = {
        "effects": [
            {"row_id": "row-1", "Condition": {"value": "Color-word Stroop", "evidence": "p3"}},
            {"row_id": "row-2", "Condition": {"value": "Spatial Stroop", "evidence": "p4"}},
            {"row_id": "row-3", "Condition": {"value": "Spatial Stroop", "evidence": "p5"}},
        ]
    }
    result = validate_response(parsed, requested)
    assert result.ok
    assert not result.needs_review
    assert set(result.coded_by_row_id) == requested


def test_validate_response_rejects_missing_id_even_if_count_matches():
    # Three conditions requested; model silently drops one and duplicates another.
    # A naive "does the count match" check would pass this. It must not.
    requested = {"row-1", "row-2", "row-3"}
    parsed = {
        "effects": [
            {"row_id": "row-1", "Condition": {"value": "Color-word Stroop", "evidence": "p3"}},
            {"row_id": "row-2", "Condition": {"value": "Spatial Stroop", "evidence": "p4"}},
            {"row_id": "row-2", "Condition": {"value": "Spatial Stroop", "evidence": "p4"}},
        ]
    }
    result = validate_response(parsed, requested)
    assert not result.ok
    assert result.needs_review


def test_validate_response_rejects_scrambled_extra_id():
    # Model invents a row_id that was never requested (e.g. hallucinated or
    # mis-transcribed) — must be flagged, not silently merged/ignored.
    requested = {"row-1", "row-2"}
    parsed = {
        "effects": [
            {"row_id": "row-1", "Condition": {"value": "Color-word Stroop", "evidence": "p3"}},
            {"row_id": "row-99", "Condition": {"value": "Spatial Stroop", "evidence": "p4"}},
        ]
    }
    result = validate_response(parsed, requested)
    assert not result.ok
    assert result.missing_ids == {"row-2"}
    assert result.extra_ids == {"row-99"}


def test_validate_response_never_trusts_position_alignment():
    # Right IDs, but this asserts the mechanism keys results BY id, not by list
    # position — so even if a future refactor iterated positionally, a test like
    # this would need the mapping to still be id-correct.
    requested = {"row-1", "row-2"}
    parsed = {
        "effects": [
            {"row_id": "row-2", "Condition": {"value": "Spatial Stroop", "evidence": "p9"}},
            {"row_id": "row-1", "Condition": {"value": "Color-word Stroop", "evidence": "p1"}},
        ]
    }
    result = validate_response(parsed, requested)
    assert result.ok
    assert result.coded_by_row_id["row-1"]["Condition"]["value"] == "Color-word Stroop"
    assert result.coded_by_row_id["row-2"]["Condition"]["value"] == "Spatial Stroop"
