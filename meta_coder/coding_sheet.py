"""Coding sheet: one row per effect-instance, joining a PDF to the effects/
conditions it contains (plan.md "Problem 3").

Deliberately a fixed schema, not manual-configurable: exactly the minimal fields
needed for paper identification (`authors`, `year`), effect ID (`row_id`), and
effect location (`source_pdf`, `locator`) — nothing else. An open-ended per-manual
column set was confusing (users couldn't tell what the sheet was supposed to
contain), so the CSV may have this info and only this info.

CSV import only for the MVP (todo.md step 4) — no GUI grid yet. Validation here is
deliberately loud: a `source_pdf` that doesn't match an uploaded file, a duplicate
`row_id`, a missing identification field, or an unexpected extra column must be a
visible pre-run error, never a silently dropped/ignored row or column.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path


REQUIRED_COLUMNS = ("row_id", "source_pdf", "locator", "authors", "year")

COLUMN_DESCRIPTIONS = {
    "row_id": "Effect ID — a short, unique identifier you invent for this effect/row.",
    "source_pdf": "Which uploaded PDF this effect comes from — must match a filename exactly.",
    "locator": "Effect location within the paper, e.g. \"Table 2, Experiment 1, DV: accuracy\".",
    "authors": "Paper identification — the study's author(s).",
    "year": "Paper identification — the study's publication year.",
}


@dataclass
class CodingSheetRow:
    row_id: str
    source_pdf: str
    locator: str
    authors: str = ""
    year: str = ""


@dataclass
class CodingSheetIssue:
    row_number: int | None
    message: str


@dataclass
class CodingSheet:
    rows: list[CodingSheetRow]
    issues: list[CodingSheetIssue]

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def rows_for_pdf(self, source_pdf: str) -> list[CodingSheetRow]:
        return [row for row in self.rows if row.source_pdf == source_pdf]

    def pdfs_with_no_rows(self, uploaded_filenames: set[str]) -> set[str]:
        covered = {row.source_pdf for row in self.rows}
        return uploaded_filenames - covered


def parse_coding_sheet_csv(text: str, *, uploaded_filenames: set[str]) -> CodingSheet:
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [name.strip() for name in (reader.fieldnames or [])]
    issues: list[CodingSheetIssue] = []

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing_columns:
        issues.append(
            CodingSheetIssue(
                row_number=None,
                message=f"Missing required column(s): {', '.join(missing_columns)}.",
            )
        )
        return CodingSheet(rows=[], issues=issues)

    extra_columns = [col for col in fieldnames if col not in REQUIRED_COLUMNS]
    if extra_columns:
        issues.append(
            CodingSheetIssue(
                row_number=None,
                message=(
                    f"Unexpected column(s): {', '.join(extra_columns)}. The coding sheet "
                    f"only accepts {', '.join(REQUIRED_COLUMNS)} — remove the rest."
                ),
            )
        )
        return CodingSheet(rows=[], issues=issues)

    rows: list[CodingSheetRow] = []
    seen_ids: dict[str, int] = {}
    for line_number, record in enumerate(reader, start=2):  # header is line 1
        row_id = (record.get("row_id") or "").strip()
        source_pdf = (record.get("source_pdf") or "").strip()
        locator = (record.get("locator") or "").strip()
        authors = (record.get("authors") or "").strip()
        year = (record.get("year") or "").strip()

        if not row_id:
            issues.append(CodingSheetIssue(line_number, "row_id is required."))
            continue
        if row_id in seen_ids:
            issues.append(
                CodingSheetIssue(
                    line_number,
                    f"row_id `{row_id}` is a duplicate (first used on row {seen_ids[row_id]}).",
                )
            )
            continue
        seen_ids[row_id] = line_number

        if not source_pdf:
            issues.append(CodingSheetIssue(line_number, f"row_id `{row_id}` has no source_pdf."))
            continue
        if source_pdf not in uploaded_filenames:
            issues.append(
                CodingSheetIssue(
                    line_number,
                    f"row_id `{row_id}` references `{source_pdf}`, which has not been uploaded.",
                )
            )
            continue

        if not locator:
            issues.append(
                CodingSheetIssue(
                    line_number,
                    f"row_id `{row_id}` has no locator (describe which experiment/condition/DV "
                    "this row is).",
                )
            )
            continue

        if not authors:
            issues.append(
                CodingSheetIssue(line_number, f"row_id `{row_id}` has no authors.")
            )
            continue

        if not year:
            issues.append(CodingSheetIssue(line_number, f"row_id `{row_id}` has no year."))
            continue

        rows.append(
            CodingSheetRow(
                row_id=row_id, source_pdf=source_pdf, locator=locator, authors=authors, year=year
            )
        )

    return CodingSheet(rows=rows, issues=issues)


def read_coding_sheet(path: Path, *, uploaded_filenames: set[str]) -> CodingSheet:
    if not path.is_file():
        return CodingSheet(rows=[], issues=[])
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return CodingSheet(rows=[], issues=[])
    return parse_coding_sheet_csv(text, uploaded_filenames=uploaded_filenames)
