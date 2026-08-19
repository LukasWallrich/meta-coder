from meta_coder.coding_sheet import parse_coding_sheet_csv
from meta_coder.manual import parse_coding_manual


MANUAL_YAML = """
name: t
effect_definition: x
coding_sheet_fields:
  authors: {type: string}
effects:
  Condition: {type: string, required: true}
"""


def _manual():
    return parse_coding_manual(MANUAL_YAML)


def test_unmatched_source_pdf_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors\nr1,missing.pdf,Exp 1,Smith\n"
    sheet = parse_coding_sheet_csv(csv_text, manual=_manual(), uploaded_filenames={"other.pdf"})
    assert not sheet.is_valid
    assert not sheet.rows
    assert "missing.pdf" in sheet.issues[0].message


def test_duplicate_row_id_is_a_loud_blocking_issue():
    csv_text = (
        "row_id,source_pdf,locator,authors\n"
        "r1,paper.pdf,Exp 1,Smith\n"
        "r1,paper.pdf,Exp 2,Smith\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, manual=_manual(), uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert any("duplicate" in issue.message for issue in sheet.issues)


def test_valid_sheet_groups_rows_by_pdf():
    csv_text = (
        "row_id,source_pdf,locator,authors\n"
        "r1,paper.pdf,Exp 1,Smith\n"
        "r2,paper.pdf,Exp 2,Smith\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, manual=_manual(), uploaded_filenames={"paper.pdf"})
    assert sheet.is_valid
    assert len(sheet.rows_for_pdf("paper.pdf")) == 2
    assert sheet.pdfs_with_no_rows({"paper.pdf", "other.pdf"}) == {"other.pdf"}
