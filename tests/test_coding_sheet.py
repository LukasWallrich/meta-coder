import csv
import io

from meta_coder.coding_sheet import coding_sheet_template_csv, parse_coding_sheet_csv


def test_template_has_required_columns_and_three_examples():
    rows = list(csv.DictReader(io.StringIO(coding_sheet_template_csv())))

    assert rows[0].keys() == {"row_id", "source_pdf", "locator", "authors", "year"}
    assert [row["row_id"] for row in rows] == ["effect-1", "effect-2", "effect-3"]


def test_unmatched_source_pdf_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,missing.pdf,Exp 1,Smith,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"other.pdf"})
    assert not sheet.is_valid
    assert not sheet.rows
    assert "missing.pdf" in sheet.issues[0].message
    # Unmatched/missing source_pdf is a "pdf" issue (the PDF identification
    # tab's concern) — everything else is a "sheet" issue.
    assert sheet.issues[0].kind == "pdf"
    assert sheet.pdf_issues == sheet.issues
    assert sheet.sheet_issues == []


def test_blank_source_pdf_is_a_pdf_kind_issue():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,,Exp 1,Smith,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames=set())
    assert sheet.issues[0].kind == "pdf"


def test_duplicate_row_id_is_a_loud_blocking_issue():
    csv_text = (
        "row_id,source_pdf,locator,authors,year\n"
        "r1,paper.pdf,Exp 1,Smith,2020\n"
        "r1,paper.pdf,Exp 2,Smith,2020\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert any("duplicate" in issue.message for issue in sheet.issues)
    # A duplicate row_id isn't a PDF-matching problem — stays a "sheet" issue.
    assert sheet.sheet_issues == sheet.issues
    assert sheet.pdf_issues == []


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


def test_blank_locator_is_allowed_for_a_single_effect_manuscript():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,paper.pdf,,Smith,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert sheet.is_valid
    assert sheet.rows[0].locator == ""


def test_missing_required_column_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors\nr1,paper.pdf,Exp 1,Smith\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "year" in sheet.issues[0].message


def test_extra_column_is_rejected_not_silently_ignored():
    # The coding sheet is a fixed schema (plus title/doi, optional and used
    # only for PDF-matching suggestions) — anything else is a hard error, not
    # a warning.
    csv_text = "row_id,source_pdf,locator,authors,year,notes\nr1,paper.pdf,Exp 1,Smith,2020,irrelevant\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "notes" in sheet.issues[0].message


def test_optional_title_and_doi_columns_are_accepted_and_carried_through():
    csv_text = (
        "row_id,source_pdf,locator,authors,year,title,doi\n"
        "r1,paper.pdf,Exp 1,Smith,2020,A Great Paper,10.1/x\n"
    )
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert sheet.is_valid
    assert sheet.rows[0].title == "A Great Paper"
    assert sheet.rows[0].doi == "10.1/x"


def test_missing_authors_or_year_is_a_loud_blocking_issue():
    csv_text = "row_id,source_pdf,locator,authors,year\nr1,paper.pdf,Exp 1,,2020\n"
    sheet = parse_coding_sheet_csv(csv_text, uploaded_filenames={"paper.pdf"})
    assert not sheet.is_valid
    assert "authors" in sheet.issues[0].message
