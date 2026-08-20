from meta_coder.coding_sheet import parse_coding_sheet_csv


def test_unmatched_source_pdf_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,missing.pdf,Exp 1,Smith,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"other.pdf"})
    assert not sheet.is_valid
    assert not sheet.rows
    assert "missing.pdf" in sheet.issues[0].message


def test_duplicate_row_id_is_a_loud_blocking_issue():
    csv_text = (
        "row_id,source_pdf,locator,authors,year\n"
        "r1,paper.pdf,Exp 1,Smith,2020\n"
        "r1,paper.pdf,Exp 2,Smith,2020\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert any("duplicate" in issue.message for issue in sheet.issues)


def test_valid_sheet_groups_rows_by_pdf():
    csv_text = (
        "row_id,source_pdf,locator,authors,year\n"
        "r1,paper.pdf,Exp 1,Smith,2020\n"
        "r2,paper.pdf,Exp 2,Smith,2020\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert sheet.is_valid
    assert len(sheet.rows_for_pdf("paper.pdf")) == 2
    assert sheet.pdfs_with_no_rows({"paper.pdf", "other.pdf"}) == {"other.pdf"}


def test_missing_required_column_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors\nr1,paper.pdf,Exp 1,Smith\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "year" in sheet.issues[0].message


def test_extra_column_is_rejected_not_silently_ignored():
    # The coding sheet is a fixed schema — it may have exactly the required
    # columns and nothing else, so an extra one is a hard error, not a warning.
    csv_text = "row_id,source_pdf,locator,authors,year,doi\nr1,paper.pdf,Exp 1,Smith,2020,10.1/x\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "doi" in sheet.issues[0].message


def test_missing_authors_or_year_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,paper.pdf,Exp 1,,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "authors" in sheet.issues[0].message
