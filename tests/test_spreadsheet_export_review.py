import csv
import io
from meta_coder.coding_sheet import CodingSheet, CodingSheetRow
from meta_coder.extraction import ExtractionResult
from meta_coder.manual import parse_coding_manual
from meta_coder.results import rows_to_csv, rows_to_spreadsheet_csv, rows_to_provenance_csv


def test_spreadsheet_variant_escapes_formulas_but_preserves_numbers_and_canonical_data():
    manual = parse_coding_manual('effect_definition: comparison\neffects:\n  "=formula_header": {type: string}\n  estimate: {type: number}\n')
    rows = [{'row_id': '=SUM(A1:A2)', 'authors': '\t@danger', 'estimate': '-1.25e-3', '=formula_header': '+danger'}]
    canonical = rows_to_csv(rows, manual)
    exported = rows_to_spreadsheet_csv(rows, manual)
    assert exported.startswith(b'\xef\xbb\xbf') and b'\r\r\n' not in exported
    values = list(csv.reader(io.StringIO(exported.decode('utf-8-sig'))))
    assert "'=formula_header" in values[0]
    assert "'=SUM(A1:A2)" in values[1] and "'\t@danger" in values[1]
    assert '-1.25e-3' in values[1]
    assert '=SUM(A1:A2)' in canonical and "'=SUM" not in canonical


def test_provenance_comes_from_each_result_with_unknowns_for_legacy():
    sheet = CodingSheet([CodingSheetRow('r1', 'a.pdf', ''), CodingSheetRow('r2', 'b.pdf', ''), CodingSheetRow('r3', 'legacy.pdf', '')], [])
    results = {'a.pdf': ExtractionResult('a.pdf', 'ok', provider='gemini', model='a', prompt_version='2'),
               'b.pdf': ExtractionResult('b.pdf', 'ok', provider='openrouter', model='b', prompt_version='1')}
    rows = list(csv.DictReader(io.StringIO(rows_to_provenance_csv(sheet, results))))
    assert (rows[0]['provider'], rows[0]['model']) == ('gemini', 'a')
    assert (rows[1]['provider'], rows[1]['model']) == ('openrouter', 'b')
    assert rows[2]['provider'] == rows[2]['model'] == rows[2]['prompt_version'] == ''
