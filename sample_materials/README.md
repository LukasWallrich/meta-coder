# Test materials: affordance compatibility meta-analysis (1 paper)

Real materials from your affordance/compatibility-effect meta-analysis, scoped down
to just `Ambrosecchia 2015.pdf` — the other papers in `reanalysis_labeled_checked.xlsx`
are left out for now, per your request.

- `coding_manual.yml` — derived from `coding_manual.docx`, restricted to the
  moderators actually present in `reanalysis_labeled_checked.xlsx` (so there's an
  unambiguous, checkable ground truth — see below), plus the raw effect-size fields
  (`ResponseTimeCompatibleMs`, `SampleSize`, `TStatistic`, etc.) so the run also
  exercises extracting the focal statistic itself, not just study-design moderators.
- `coding_sheet.csv` — the 2 rows for this paper (`Row_ID` 1 and 2 in the xlsx),
  `row_id`s kept as `1_1_A` / `1_2_B` to match your existing `Old_Effect_ID`s, so
  results here join straight back into your existing dataset later. This paper has
  two experiments in one PDF (intact vs. broken objects) — a real instance of the
  multi-condition-per-paper case the coding-sheet mechanism exists for. The coding
  sheet's columns are a fixed schema now (`row_id`, `source_pdf`, `locator`,
  `authors`, `year` — nothing else), so `paper_id`/`sample_number`/`effect_letter`/
  `doi` from the original roster aren't carried as separate columns here; the
  `row_id` naming still encodes that same paper/sample/effect structure.
- `known_values_for_verification.md` — the correct values for both rows, pulled
  from your own checked spreadsheet. Not an app input — for comparing against
  `coded_data.csv`/`evidence.csv` after a run.

## To try it in the app

1. Create a project.
2. In the Coding manual card, open "Import an existing manual.yml" and drop in
   `coding_manual.yml` (the manual is only ever edited afterward through the
   structured field editor, not as raw text — importing just seeds it once).
3. Upload `Ambrosecchia 2015.pdf`.
4. Upload `coding_sheet.csv`.
5. Set a Gemini API key and run.
6. Compare `coded_data.csv` against `known_values_for_verification.md`, and spot-check
   a few `evidence.csv` quotes (or the per-PDF audit YAML under Results — the same
   codes and evidence together, easier to read than scanning CSV columns) against the
   PDF — especially `BrokenObjects`, the one field that must differ between the two
   rows.

The original `coding_manual.docx` and `reanalysis_labeled_checked.xlsx` are
untouched — this directory only adds the two files above plus this note.
