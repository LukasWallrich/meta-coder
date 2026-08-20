import json

from meta_coder.extraction import parse_json_response


def test_parse_json_response_preserves_repaired_payload():
    parsed, repaired = parse_json_response('{"effects": [{"row_id": "r1",}]}')

    assert parsed == {"effects": [{"row_id": "r1"}]}
    assert repaired is not None
    assert json.loads(repaired) == parsed


def test_parse_json_response_does_not_rewrite_valid_json():
    parsed, repaired = parse_json_response('{"effects": []}')

    assert parsed == {"effects": []}
    assert repaired is None
