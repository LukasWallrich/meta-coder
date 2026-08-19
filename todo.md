# Meta-Coder: build order (ordered by importance)

See `plan.md` for the full design. This orders the build so the core, novel idea —
"can the model correctly locate and code a specific effect out of a PDF using a
locator string and an ID it echoes back" — gets validated before any UI polish,
provider redundancy, or packaging work.

## What "try it out" means (the MVP acceptance test)

Not "the app runs." The actual test: pick one real paper with **≥3 conditions/
experiments**, write a coding sheet row for each, run it through Gemini, and hand-check
the output against the evidence quotes. Pass means every value is correctly attributed
to the right condition — no silent cross-condition swaps. If evidence isn't in the
output, a mis-aligned run and a correct run look identical, so evidence generation is
part of the MVP, not a later addition.

---

## Build order

### 1. App skeleton with the real launch path
- FastAPI skeleton using the actual launch mechanics from day one: random free port,
  random URL token generated at launch, browser auto-opened, **every route
  namespaced under `/<token>/`** from the start. Do not prototype on a bare
  `uvicorn --reload` without the token prefix — retrofitting it later touches every
  route and every template URL.
- Local-only bind (`127.0.0.1`), basic `Host`-header check middleware.
- Single project concept: create/list, directory layout (`sources/`,
  `coding_manual.yml`, `coding_sheet.csv`, `output/`).

### 2. API key handling (minimum viable)
- Session-only key entry (pasted into a form, held in server memory for the running
  session). No OS keyring yet — that's parity polish, not core-loop validation.

### 3. Coding manual — structured GUI editor, done ✅ (pulled forward from step 14)
- **Amendment to the original plan below**: raw-YAML hand-editing was never shipped
  as a user-facing path. Per explicit instruction, the structured field/levels editor
  (originally step 14, post-MVP) was built as part of the MVP instead — plan.md
  "Problem 1" is updated to match: "users never hand-edit the YAML."
- `effect_definition` textarea pinned at top (required before adding effect fields),
  add/remove/reorder for `coding_sheet_fields` and `effects`, a levels sub-editor
  (value + description) shown only for categorical string fields, `evidence_required`
  toggle per effect field. A collapsed read-only YAML preview stays for transparency —
  not an input.
- One-time **import**: drop in an existing `manual.yml` (hand-written, or later the
  PDF-drafted one from step 16) to seed the editor once; edited only through the
  fields from then on. Needed for real starter manuals (e.g. `sample_materials/`) —
  without it there'd be no way to load a pre-made schema at all once raw editing was
  removed.
- A "reset to a blank manual" recovery action for the rare case the on-disk file is
  invalid outside the app's own writes (e.g. hand-edited externally) and there's
  nothing valid to seed the editor with.
- Full schema support: `effect_definition` (required), `coding_sheet_fields`,
  `effects` with `levels` + per-level descriptions, `evidence_required`.
- Validation on every save regardless of source (structured edit or import):
  structure, supported types, `effect_definition` non-empty, `effects` non-empty, no
  duplicate field names across sections.
- **Manual edit behavior for now: full reset of `output/` on any change, with a
  visible warning before saving.** This is the deliberately simple placeholder for
  what `plan.md` calls Divergence #1 (no full reset) — named here so it's a known
  placeholder to upgrade at step 13, not a shortcut that gets forgotten.

### 4. Coding sheet (CSV import only)
- CSV import mapping columns to `row_id` / `source_pdf` / `locator` + whatever
  `coding_sheet_fields` the manual declares.
- **Loud pre-run validation**: every `source_pdf` must match an uploaded file, every
  `row_id` must be unique. Surfaced as visible errors before a run is allowed to
  start — never a silently dropped row.

### 5. PDF upload
- Multipart upload, `%PDF` signature check, filename sanitization, storage in
  `sources/`.

### 6. Gemini adapter + the core mechanism — highest-risk, most important item
- Native-PDF send to Gemini with structured output compiled from the manual's
  `effects` (`coding_sheet_fields` excluded from the response schema entirely).
- **One request per PDF, batching every coding-sheet row belonging to that PDF**
  (each carrying `row_id` + `locator`, with `effect_definition` as shared context).
  Batching is part of the mechanism under test here, not a later optimization —
  build it now, not sequentially-per-row.
- Response must echo `row_id` per coded object. **Hard-validate the returned ID set
  equals the requested ID set exactly, in this same step** — a mismatch marks that
  PDF `needs_review`. Do not ship a softer "accept partial / best-effort align by
  position" version "for now" — that would validate the wrong thing.
- Every coded field returned as `{value, evidence}`.

### 7. Sequential run execution
- Process PDFs one at a time — no concurrency/pacing infrastructure yet. Sequential
  removes a whole dimension of bugs while the mechanism itself is still being
  validated.
- Simple status polling endpoint ("processing X of N") — no SSE yet.
- Write `output/raw/*.json`, `coded_data.csv`, **and `evidence.csv`** (not optional —
  see the acceptance test above), plus one readable `output/coded/<pdf>.yaml` per PDF
  with codes and evidence together per coding-sheet row — the actual audit artifact;
  the wide CSVs are for joining into a spreadsheet, not for reading.

### 8. Minimal results view
- Per-PDF status list (ok / needs_review / error).
- Download links for `coded_data.csv` and `evidence.csv`. A rendered in-browser table
  is nice-to-have, not required — a spreadsheet app can open the CSV directly.

---
## ⬆ MVP cutoff — everything above is the demo you can try today.
## ⬇ Everything below is hardening, UX, and distribution polish for turning it into a tool other people can use — not steps needed to validate the idea.
---

### 9. Credentials done properly (`plan.md` Part A5)
- **Partially done ✅, pulled forward per explicit instruction**: a global
  `/settings` page now holds the API key (was per-project-tab before, which was
  misleading — the underlying value was already a single session-wide value, not
  per-project). Still session-only in server memory, not the OS keyring — that
  part of this step (save/unlock/delete against the OS credential store,
  session-only fallback marking, chmod-restricted preferences file) is still
  outstanding.

### 10. Concurrency, pacing — done ✅ (live progress/cancel still outstanding)
- **Pulled forward per explicit instruction**: the runner now uses a real worker
  pool (`ThreadPoolExecutor`, sized to `min(parallel_requests, pending PDFs)`) and
  a shared `_RequestPacer` enforcing a minimum interval between request *starts*
  globally across workers, not per-worker — proven in
  `tests/test_runner_concurrency.py` (results stay correctly attributed to the
  right PDF under real concurrent execution; the pacer's delay is global, not
  per-worker). `model`/`parallel_requests`/`request_delay_sec` are now persisted
  per project (`meta_coder/settings.py`) and edited on the project's Setup tab —
  the reason to build real concurrency now rather than leave the setting inert:
  a "parallel requests" field that's silently ignored by a still-sequential
  runner would be actively misleading UI.
- Still outstanding from this step: SSE live progress (still polling +
  `<meta refresh>`) and cooperative cancellation.

### 11. Retry + raw/repaired response viewing (Part A8)
- Retry only failed/`needs_review` PDFs, optionally scoped to a selection.
- Per-PDF raw provider response and repaired-JSON viewing in the UI.

### 12. Evidence-backed review grid (Problem 2's review UI)
- Coding-sheet-effect × moderator grid: value + evidence per cell, accept/flag/
  override, rollup of flagged/low-confidence cells project-wide. This is what turns
  "I hand-checked one paper for the MVP test" into a repeatable trust workflow across
  an entire project.

### 13. Field-level invalidation on manual edit
- Upgrades step 3's placeholder: adding a field marks only that column
  `needs_recode`; removing/retyping a field invalidates only that column's prior
  values. Full reset stays available as an explicit user action.

### 14. ~~Structured GUI editor for the coding manual~~ — done, see step 3
- Built as part of the MVP instead of here — see step 3's note. Left as a stub so
  the numbering below doesn't shift.

### 15. Coding-sheet GUI grid entry (Problem 3)
- Alternative to CSV import: add/edit/reorder rows directly in a grid, with a
  filename picker constrained to already-uploaded PDFs.

### 16. PDF/DOCX manual import → LLM-drafted YAML (Problem 1)
- Upload an existing manual document; the LLM drafts YAML and feeds it through the
  same import path built in step 3, landing in the structured editor for review —
  never auto-saved sight-unseen.

### 17. OpenRouter backup provider (Part A4)
- Manual model-ID entry with live validation (structured-output support, file/text
  input, non-batch-only), bounded retry with backoff.
- Deferred this far deliberately, not an oversight: OpenRouter needs its own PDF-input
  path (`cloudflare_pdf` mode, since most OpenRouter-routed models can't take raw PDF
  bytes the way Gemini can) plus the live model-validation logic above. One working
  provider is enough to prove the row_id/locator mechanism from step 6; a second
  provider multiplies MVP failure surface without testing anything new about that
  mechanism. Revisit earlier only if you don't have a Gemini key, or specifically want
  to test the mechanism against a non-Gemini model.

### 18. Downloads (ZIP) + open-project-folder (Part A9)
- Convenience only — during your own trial, the files are already sitting on disk
  locally.

### 19. App-level settings page (Part A6)
- **The page itself exists now** (step 9) — API key only. Still to add here:
  request timeout, reasoning effort, service tier (currently hardcoded to
  `"flex"` in `gemini.py`), upload size cap — made configurable instead of
  hardcoded defaults.

### 20. Packaging: Pixi installer, install scripts, vendored frontend (Architecture)
- Needed only to hand this to someone else or install it outside your dev
  environment. Running from source is sufficient for your own trial and for
  everything through step 19.

### 21. Later features (explicitly out of scope until 1–20 are solid)
- LLM-assisted coding-sheet discovery mode.
- Cross-project coding-manual library.
- Inter-rater / inter-model agreement view.
