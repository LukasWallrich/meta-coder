"""Coding sheet: one row per effect-instance, joining a PDF to the effects/
conditions it contains via `row_id` / `source_pdf` / `locator` (plan.md "Problem 3").

CSV import only for the MVP (todo.md step 4) — no GUI grid yet. Validation here is
deliberately loud: a `source_pdf` that doesn't match an uploaded file, or a
duplicate `row_id`, must be a visible pre-run error, never a silently dropped row.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from .manual import CodingManual


@dataclass
class CodingSheetRow:
    row_id: str
    source_pdf: str
    locator: str
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class CodingSheetIssue:
    row_number: int | None
    message: str


@dataclass
class CodingSheet:
    rows: list[CodingSheetRow]
    issues: list[CodingSheetIssue]
    warnings: list[CodingSheetIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def rows_for_pdf(self, source_pdf: str) -> list[CodingSheetRow]:
        return [row for row in self.rows if row.source_pdf == source_pdf]

    def pdfs_with_no_rows(self, uploaded_filenames: set[str]) -> set[str]:
        covered = {row.source_pdf for row in self.rows}
        return uploaded_filenames - covered


REQUIRED_COLUMNS = ("row_id", "source_pdf", "locator")


def parse_coding_sheet_csv(
    text: str,
    *,
    manual: CodingManual,
    uploaded_filenames: set[str],
) -> CodingSheet:
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

    declared_fields = set(manual.coding_sheet_fields)
    unknown_columns = [
        col for col in fieldnames if col not in REQUIRED_COLUMNS and col not in declared_fields
    ]

    rows: list[CodingSheetRow] = []
    seen_ids: dict[str, int] = {}
    for line_number, record in enumerate(reader, start=2):  # header is line 1
        row_id = (record.get("row_id") or "").strip()
        source_pdf = (record.get("source_pdf") or "").strip()
        locator = (record.get("locator") or "").strip()

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

        fields = {
            name: (record.get(name) or "").strip()
            for name in declared_fields
            if name in fieldnames
        }
        rows.append(
            CodingSheetRow(row_id=row_id, source_pdf=source_pdf, locator=locator, fields=fields)
        )

    warnings = [
        CodingSheetIssue(
            row_number=None,
            message=(
                f"Column `{col}` is not declared in the coding manual's "
                "`coding_sheet_fields` and will be ignored."
            ),
        )
        for col in unknown_columns
    ]

    return CodingSheet(rows=rows, issues=issues, warnings=warnings)


def read_coding_sheet(
    path: Path, *, manual: CodingManual, uploaded_filenames: set[str]
) -> CodingSheet:
    if not path.is_file():
        return CodingSheet(rows=[], issues=[])
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return CodingSheet(rows=[], issues=[])
    return parse_coding_sheet_csv(text, manual=manual, uploaded_filenames=uploaded_filenames)
