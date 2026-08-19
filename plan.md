# Meta-Coder: a local browser app for LLM-assisted meta-analysis coding

> Build order and MVP scope live in [`todo.md`](todo.md). This file is the design —
> what to build; `todo.md` is the sequencing — what order, and where the try-it-out
> cutoff is.

## What this is

A local, single-user browser app for coding moderators/effects out of PDF articles for
a systematic review or meta-analysis: given a coding manual and a set of source PDFs,
use an LLM to extract per-effect data with page/quote evidence for every value, then
export a coded dataset that joins back to the user's own effect-size spreadsheet.

It's built by combining two prior projects' decisions:

- A local browser app (Python/FastAPI backend, Jinja templates, no JS build step,
  Pixi-packaged installer, local-only with a token URL) that read PDFs and used an LLM
  to extract statistics for a z-curve analysis. That app's non-domain-specific
  decisions — security model, project management, credential storage, provider/model
  handling, run execution, results storage — are copied wholesale (Part A below) since
  none of that is specific to z-curve analysis.
- A set of Node scripts that used an LLM to code moderators for three real
  meta-analyses. That project had no usable UI, but it already solved the two hardest
  domain problems (how to tell the model which effect to code, and how to link a PDF to
  its list of effects) via one mechanism: a CSV with one row per effect-instance and a
  human-written locator string. This plan formalizes and extends that mechanism (Part B)
  rather than inventing a new one.

Both source projects are being deleted once this plan is written, so everything needed
to build from scratch is captured here — nothing below refers back to either project's
files.

---

# Part A — Baseline application behavior (carried over as-is)

Everything in this part is domain-agnostic local-app plumbing, copied because it
already works and there's no meta-analysis-specific reason to change it.

## A1. Shape, install, and local-only security

- Python backend (FastAPI), server-rendered HTML (Jinja2 templates), a small
  vendored no-build frontend (Alpine.js/htmx-style + a vendored CSS framework — see
  Architecture) instead of a bundled SPA, so the release pipeline never needs a Node
  build step.
- Packaged and installed via [Pixi](https://pixi.sh/) with a locked environment
  (`pixi.lock`) so end users don't install Python/dependencies separately. One-line
  install scripts for macOS/Linux (`curl | sh`) and Windows (`irm | iex`) that download
  a versioned release bundle and add a launcher to `PATH`. Re-running the installer
  updates in place.
- Launching the app: pick a free local TCP port by binding to `127.0.0.1:0` and
  reading back the assigned port; generate a cryptographically random URL token
  (32 bytes, URL-safe); start the server bound to `127.0.0.1` only; open the user's
  browser to `http://127.0.0.1:<port>/<token>/`; print the URL and "press Ctrl+C to
  stop" to the terminal. Every route is namespaced under `/<token>/` — there is no
  unauthenticated route except static assets needed before the token is known.
- Request-level security middleware, applied to every request:
  - Reject any request whose `Host` header isn't `127.0.0.1`, `localhost`, or `[::1]`
    (400).
  - For any non-`GET`/`HEAD`/`OPTIONS` request: reject if `Content-Length` exceeds a
    hard cap (512 MB) before reading the body (413); reject if an `Origin` header is
    present and doesn't match the request's own `Host` (403, blocks cross-origin
    writes); reject if `Sec-Fetch-Site: cross-site` is present (403).
  - No setting to expose the app beyond localhost — this is deliberate; it's local
    software, not a hosted service.
- Uploads and PDF handling get their own validation layer (A3).

## A2. Projects

- A "project" is a self-contained meta-analysis coding job: one coding manual, one
  set of source PDFs, one coding sheet, one set of run settings, one output folder.
- Projects live in the OS's standard per-user application-data directory (overridable
  via an environment variable for testing/portable use):
  - macOS: `~/Library/Application Support/<App Name>/projects`
  - Windows: `%LOCALAPPDATA%\<App Name>\projects`
  - Linux: `${XDG_DATA_HOME:-~/.local/share}/<app-slug>/projects`
- Project ID: 16 lowercase-hex characters (random), used as both the directory name
  and the URL segment; validated with a strict regex before ever touching the
  filesystem, and every resolved path is checked to still live under the projects
  root (containment check) to block path traversal.
- Project metadata (`id`, `name`, `created_at`) stored as JSON in a small hidden
  subdirectory inside the project folder, not inferred from the directory name alone.
- Creating a project: sanitize/collapse whitespace in the name, cap length (100
  chars), create `sources/`, `output/raw/`, copy in the app's default coding manual
  and default instructions as a starting point.
- Listing projects: scan the projects root for valid project-ID-named directories,
  read each one's metadata, sort newest-first; corrupt/unreadable project metadata is
  skipped rather than crashing the list.
- Deleting a project: only allowed on a directory that actually has valid project
  metadata (guards against deleting something unrelated); blocked while a run/job is
  active for that project.
- Resetting a project: clears `output/` (recreating `output/raw/`) while preserving
  `sources/`, the coding manual, and the coding sheet — for re-running from scratch
  without re-uploading PDFs.

## A3. PDF uploads

- One upload endpoint accepts multiple files (streamed, not buffered fully in
  memory first).
- Filename handling: strip any path component (defend against `../` and backslash
  tricks), replace unsafe characters with `_`, strip trailing dots/spaces, reject
  empty or `.`/`..` results, cap length (180 chars, trimming the stem not the
  extension), require a `.pdf` extension (case-insensitive).
- Duplicate filenames in the same project get a numbered suffix (`Name (2).pdf`,
  `Name (3).pdf`, ...) rather than overwriting.
- Streaming write: write to `<destination>.uploading` in 1 MB chunks, tracking bytes
  written; abort with a clear "exceeds the N MB upload limit" error if the
  configurable per-file cap is exceeded mid-stream; after writing, verify the file is
  at least 4 bytes and starts with the `%PDF` magic bytes (reject non-PDF content that
  merely has a `.pdf` name); only then atomically rename off the `.uploading` suffix.
  Any failure cleans up the partial file.
- Default per-file upload cap: 128 MB (app setting, adjustable 1–512 MB). Separately,
  the security middleware in A1 caps the whole HTTP request at 512 MB regardless of
  per-file setting.

## A4. Providers and models

Two providers, kept behind one adapter interface (`extract(...)` returning a common
result shape) so a project's provider choice is just a string:

- **Gemini (primary).** Sends the *original PDF bytes* natively to the model — no
  local PDF-to-text conversion, no "prompt-only JSON" fallback. Requires an exact
  Gemini model ID (from the model catalog below). Uses the provider's native
  structured-output mode so the response is guaranteed to match the requested JSON
  schema (see A8 for what happens when it still doesn't parse).
- **OpenRouter (experimental backup).** Not offered through a curated list — the user
  manually enters an exact OpenRouter model ID, and the app validates it live before
  a run is allowed to start: the model must exist, must not be a batch-only model
  (incompatible with synchronous requests), must support structured output, must
  accept file or text input, and must resolve to a compatible input mode. Requests are
  retried on transient failure (a small bounded number of attempts with backoff before
  giving up), since third-party routing can be flaky.
- **Model catalog / allowlist.** A root config file lists which Gemini model IDs are
  offered in the UI and accepted when a run starts (each entry can also carry
  per-model default parallelism/delay). This file is read fresh both when the catalog
  is requested and again at run start, so editing it doesn't require rebuilding the
  app; if it's absent, the app falls back to querying the provider's live model list
  filtered to models that look document-capable. OpenRouter is intentionally *not*
  gated by this allowlist — its whole value is ad hoc access to unlisted models, gated
  instead by the live validation above.
- **Input mode.** Every resolved model carries an `input_mode`: `native_pdf` (raw PDF
  bytes go straight to the provider) or a parsed/OCR'd mode for providers that can't
  accept files directly. This is what lets the same run pipeline serve both a
  file-native provider and a text-only one without branching logic throughout the
  codebase.

## A5. Credentials

- API keys are stored via the OS's native credential store (through a
  cross-platform Python keyring library), never in a plaintext file, and never
  committed to any project file, log, URL, or downloaded artifact.
- Keys are **not** loaded automatically on app start. The user takes an explicit
  action each session to either paste a fresh key (usable for that session only) or
  unlock a previously-saved one; a "Remember securely" checkbox controls whether a
  freshly entered key is also written to the OS credential store for next time.
- If the OS has no usable credential backend (common on some Linux setups with no
  secret-service daemon), saving is reported back to the user as session-only rather
  than silently failing or falling back to plaintext.
- A small non-secret preferences file (file permissions restricted to the owner)
  tracks *whether* a key has been saved per provider (so the UI can offer "unlock"),
  without ever holding the key value itself.
- Delete-key action removes it from the OS store and clears the "is saved" flag.
- Every outbound error message and log line is scrubbed for the current session's
  key value before being shown or written, in case a provider ever echoes it back in
  an error body.

## A6. Settings

Two tiers:

- **App-level settings** (apply to every project by default): request timeout,
  default parallel-requests count, default delay between request starts, per-file
  upload size cap, PDF input mode preference, a reasoning-effort level (for models
  that support configurable reasoning — off/minimal/low/medium/high/extra-high/max),
  a service tier (standard / flex-lower-cost-variable-latency /
  priority-higher-cost-lower-latency, where the provider supports it). Persisted to a
  small JSON file, validated and clamped to sane ranges on both load and save (e.g.
  parallel requests clamped to 1–32, delay to 0–3600s, timeout to 30–3600s, upload cap
  to 1–512 MB) so a hand-edited or corrupted settings file can't produce a broken
  state.
- **Per-project run settings**: provider, model, and (optionally overridden)
  parallel-requests/delay for that project specifically — because different models
  have very different sane concurrency/pacing defaults (a fast small model can run many
  requests in parallel; a slower or rate-limited one needs pacing). When a project is
  first configured or the model changes, its parallel/delay values default from the
  model's own catalog entry rather than the global app default, but the user can
  override per project.

## A7. Running extraction

- A "run" processes every eligible source PDF concurrently, worker count = 
  `min(configured parallel-requests, number of PDFs to process)`, minimum 1 worker.
- A shared request pacer enforces a minimum interval between request *starts* across
  all workers (not just per-worker), so "1 request every 30 seconds" really means
  that globally, not per worker.
- **Run** (start/resume): reprocesses only PDFs that don't already have a successful
  extraction, *unless* the user forces a full rerun, or the provider/model/PDF input
  mode/reasoning level/service tier changed since the last run for this project — any
  of those changes invalidates all prior results because they can change output
  fundamentally, and the run auto-detects this and reprocesses everything without
  requiring the user to remember to force it.
- **Retry**: reprocesses only PDFs whose latest attempt did *not* succeed, optionally
  narrowed to a user-selected subset of the failed ones. Bookkeeping (below) counts
  each retry as a new attempt for that source rather than overwriting attempt history.
- **Cancel**: sets a cooperative cancellation flag checked between and during
  requests; in-flight work stops at the next safe checkpoint rather than being killed
  mid-write, so partially-written output is never left inconsistent.
- Live progress is streamed to the browser over Server-Sent Events: the client opens
  one `/events` connection per project, the server polls the in-memory job state
  roughly 5 times a second and pushes only new events since the client's last
  position, and closes the stream once the job reaches a terminal state
  (complete/failed/cancelled).
- A run/job's state (queued/running/complete/failed/cancelled), its accumulated
  events, and its final summary live in server memory keyed by project ID — simple
  and sufficient for a single-user local app; a job is looked up by project ID rather
  than needing a separate job-ID handshake from the client.
- Before a run starts, the resolved model is re-validated live (existence, allowed by
  the catalog, structured-output/file-input support for OpenRouter) so a stale or
  since-revoked model choice fails fast with a clear message instead of failing deep
  into a batch of PDFs.
- Per-file size is checked against the upload cap again at run time (not just at
  upload time, in case the setting changed downward) and produces a normal per-file
  error rather than aborting the whole run.

## A8. Extraction results, provenance, and raw response viewing

For every processed PDF, store an extraction record (upserted — a later attempt for
the same source replaces the "latest" view but doesn't destroy history) containing at
minimum:

- status (`ok` / `error`), the structured data returned, error text if any (secrets
  redacted).
- which provider and exact model were actually used, the resolved input mode.
- token usage (input/output/total) and wall-clock duration, when the provider reports
  them.
- if any local PDF parsing/OCR step ran ahead of the model call: parser name/version,
  a hash of the source PDF and of the parsed document (to detect drift), page count, a
  legibility grade and any parser warnings, and how long parsing took — surfaced in the
  UI so a user can tell "the model got bad input" apart from "the model reasoned
  badly."
- the raw response text from the provider, saved to disk regardless of whether it
  parsed cleanly.
- if the raw response wasn't valid JSON: an automatic repair pass attempts to fix
  syntactic issues (not semantic ones) using a JSON-repair library; both the raw and
  repaired text are kept, and a `json_repaired` flag records that repair happened, so
  a user auditing results can see when output needed massaging.
- a per-run log (append-only) recording every attempt — run ID, attempt number for
  that source (derived by counting prior log rows for it, not stored redundantly),
  timestamps, status, effect count, tokens, and all the provenance fields above — so a
  project's full processing history is reconstructable, not just its latest state.
- **Raw response viewing in the UI**: per PDF, a user can view the raw provider
  response text and (if applicable) the auto-repaired version, read from disk on
  demand and truncated at a large-but-bounded size (2,000,000 characters) so a
  pathological response can't hang the page.
- A single PDF's saved extraction/response can be deleted individually (e.g. to force
  a clean re-run of just that one) without resetting the whole project's output.

## A9. Downloads, folder access, and cleanup

- **Open project folder**: a button that opens the project's directory in the native
  file manager (Explorer / Finder / the desktop's file manager on Linux via
  `xdg-open`), platform-detected, with a clear error if the OS refuses.
- **Download results as ZIP**: bundles only result-relevant files — the coding
  manual, the structured output files, the run log, and the per-source raw/repaired
  response artifacts — deliberately *excluding* source PDFs and, always, any
  credential material. Filename is derived from the project name with unsafe
  characters stripped.
- Both actions operate purely on server-local files; nothing is uploaded anywhere
  external by these actions.

---

# Part B — What's new: three meta-analysis-specific problems

The z-curve-style app this is based on always had the model discover every relevant
statistic in a PDF itself — there was no pre-existing list of "here are the N effects
you must find." Meta-analysis coding is different: the analyst typically already knows,
from their systematic review process, exactly which effects/studies/conditions across
however many papers need coding, and that list *cannot* safely be left to the model to
reconstruct — effect inclusion is a human methodological decision (avoiding double
counting, applying inclusion/exclusion criteria, distinguishing near-identical
conditions), not a discovery task.

The Node-script project already solved this well by convention, with one artifact: a
CSV with one row per effect-instance, a `SourceID` column joining rows to a PDF
filename, and a human-written `Notes` column telling the model which experiment/
condition/DV that row refers to. Its system prompt literally said: *"Where an article
contains multiple studies/experiments/conditions, use the data in the 'Notes' metadata
moderator to identify which study/experiment/condition to code."* That mechanism is
formalized and hardened below rather than replaced.

## Problem 1 — Coding manual authoring (the manual *is* the schema)

**Decision:** there is no separate "manual" document that has to be kept in sync with
a machine-readable schema. One YAML file, `coding_manual.yml`, is both — it's what a
human reads to understand the coding scheme, and it's compiled directly into the
provider's structured-output schema for the LLM call.

### Shape

```yaml
name: ingendahl_jol_memory
description: Judgments-of-learning meta-analysis moderator coding

effect_definition: >
  The effect being coded is the difference in recall performance between the
  judgment-of-learning (JOL) condition and a no-JOL control condition on a later
  memory test. Each coding sheet row is one such JOL-vs-control contrast reported
  in the article, for one experiment/condition/test-type combination.

coding_sheet_fields:       # supplied by the effect coding sheet (Problem 3),
                            # never asked of the LLM — excluded from the response
                            # schema entirely and rejoined at collation time
  source_id: {type: string, description: Coding sheet/paper identifier}
  authors:   {type: string}
  year:      {type: integer}
  locator:   {type: string, description: Which experiment/condition/DV this row is}

effects:                   # one object per coding sheet row, LLM-coded
  MemoryTest_Type:
    type: string
    levels:
      - value: Cued recall
        description: Participant given a cue and asked to recall the paired item.
      - value: Free recall
        description: Participant recalls items with no retrieval cue.
      - value: Recognition
        description: Participant selects/judges old vs. new items.
    required: true
    description: >
      The type of memory test administered after the study phase.
  StudyTime:
    type: number
    description: Study time per item in seconds, to 2 decimal places.
    evidence_required: true
```

Field types are constrained to a small fixed set (string, number, integer, boolean,
array-of-scalar — the same restricted set the z-curve app used, since it maps cleanly
onto every major provider's structured-output support), each field can carry a plain-
language `description` the model reads as its instruction, a `required` flag, and an
optional `role` tag for fields the pipeline treats specially (analogous to how the
z-curve app tagged one field as "the reported statistic" — here nothing currently needs
a role, but the mechanism carries over in case a future field like "primary outcome"
needs one).

Three structural additions beyond a flat field list, and why each earns its place:

- **`effect_definition`.** A required, project-level, free-text statement of what
  contrast or comparison *is* "the effect" for this meta-analysis — e.g. "the
  difference in response times between compatible and incompatible trials." Every
  other piece of context in the manual and coding sheet is written *relative to* this:
  a field can be named and described tersely ("Condition: the specific incompatible-
  trial manipulation used, e.g. color-word Stroop, spatial Stroop") because the model
  (and a human reading the manual later) already knows from `effect_definition` what
  role "condition" plays in the comparison. Without it, every field description would
  have to re-explain the whole comparison to stay unambiguous. It's written once when
  the manual is created — normally the first thing a user fills in, before any
  individual fields — and shown at the top of both the structured GUI editor and every
  extraction request (see Problem 2).
- **`coding_sheet_fields` vs. `effects`.** Coding-sheet-supplied fields (id, authors,
  year, locator, whatever else the sheet carries) are *excluded from the LLM response
  schema entirely* and rejoined from the coding sheet row at collation time, rather
  than being sent to the model prefilled with an instruction to "copy unchanged, don't
  alter." The prior project used the copy-unchanged approach and it still leaves room
  for the model to mutate a value it was never supposed to touch, plus it burns
  tokens for no benefit. Making the field structurally non-requestable removes the
  failure mode instead of prompting against it.
- **`levels` with a per-level `description`, not a bare enum.** This *is* the coding
  manual's actual substance — real coding manuals carry prose describing exactly what
  distinguishes each category, which is what disambiguates borderline real-world
  cases. Levels compile to an `enum` constraint in the provider's structured-output
  schema (the model literally cannot emit an off-manual category) and are the natural
  unit for a GUI editor: an "add level" / "edit description" list, not a bare type
  dropdown.
- **`evidence_required`.** Every coded field returns `{value, evidence}`, evidence
  being a page/quote citation — not a logged aside but a first-class part of the
  response schema, because it's what makes the review workflow in Problem 2 possible.
  Default true for effect fields; a coding manual author can turn it off for a field
  where citing evidence doesn't make sense (e.g. a derived/computed field).

### Baseline coding-instruction rules (carried over from the prior system prompt)

The Node project's system prompt encoded good rules worth keeping as the app's
built-in baseline instructions (in addition to whatever project-specific instructions
a user adds):

1. Only use information present in the article; no outside knowledge, no inference or
   best-guessing, unless the coding manual's field description explicitly says
   otherwise for that field.
2. If the article doesn't report a value for a field, code it as "Not Reported" and
   say so in the evidence rather than guessing.
3. Code values must follow the exact formatting the manual specifies for that field
   (units, decimal places, category label text).
4. Evidence should be concise but specific — including a page number and/or a short
   quotation wherever possible, not a vague paraphrase.
5. For a categorical field, report exactly one level unless the field's description
   states that multiple levels are valid.
6. Never invent, rename, or omit the coding-sheet row identifier a response object is
   keyed to (see Problem 2's ID validation) — it must exactly match one of the IDs
   supplied in the request.

### GUI editor — the only user-facing way to edit a manual

**Decision, stated explicitly: users never hand-edit the YAML.** A structured editor
is the sole editing surface — the `effect_definition` statement as its own labeled
textarea at the very top ("What effect is this meta-analysis about?"), required before
any effect fields can be added, followed by a field-list editor: add/remove/reorder
fields; per field set type, description, required flag, and — for categorical fields —
a levels sub-editor (value + description rows, add/remove). A read-only YAML preview
stays available (collapsed by default) purely for transparency — so a user can see
exactly what's being sent to the model — but it is not an input; it can't be edited or
pasted into. Every save goes through the same validation regardless of which field was
touched (structure check, supported types, no duplicate names across sections,
`effect_definition` non-empty, `effects` non-empty).

The one place raw YAML text still enters the app is a one-time **import**: dropping in
an existing `manual.yml` (hand-written, reused from another project, or drafted by the
PDF-import feature below) seeds the structured editor once. From that point on it's
edited exclusively through the fields, same as anything authored in the app from
scratch — import is a starting point, not a parallel editing path.

### PDF/DOCX manual import → LLM-drafted YAML

A user can upload their existing coding manual document (Word, PDF, RTF — whatever
form it's already in; real coding manuals are typically an RTF/Word table of
moderators plus prose describing each category). The app sends it to the configured
LLM provider with a fixed conversion prompt asking for a structured field list (name,
type, levels + descriptions, required-ness) in the schema shape above. The result
populates the structured GUI editor for the user to review, correct, and save — it is
never written to disk unedited; this is drafting assistance, not a trusted one-way
conversion.

The original manual document stays attached to the project as optional reference
context (uploadable alongside the schema, kept after conversion, not deleted) — useful
both for re-drafting later and as extra context the extraction prompt can include for
edge-case wording that the compressed YAML lost.

## Problem 2 — Locating which effect to extract, reliably

**Decision:** batch every coding-sheet row for one PDF into a single request; require
the model to echo back the coding-sheet row ID for every coded object it returns; hard-
validate that the returned ID set exactly matches the requested ID set before accepting
any of it.

- **Request shape per PDF**: the coding manual — including its `effect_definition`
  statement, which grounds every field description and every row's `locator` in what
  "the effect" concretely means for this meta-analysis — sent/cached once per project
  run, not re-sent per PDF (see Caching below), plus one entry per coding-sheet row that
  belongs to this PDF, each carrying its `row_id` and its `locator` (the renamed
  `Notes` field — e.g. "Experiment 1a: category-cued word pairs" or "Study 2, high
  cognitive load condition"). Sending every row for a PDF together, rather than one
  request per effect, lets the model disambiguate similar-looking conditions by
  contrast within the same context, and is cheaper than N separate calls.
- **Response validation**: each coded object must include the `row_id` it corresponds
  to. After parsing, the returned ID set must equal the requested ID set exactly —
  *positional alignment is never trusted*. A paper with three conditions where the
  model returns three well-formed objects in the wrong order is the primary failure
  mode this guards against: it's silent and produces plausible-looking but wrong data
  if you trust order instead of the explicit ID, so this must be a hard rejection/flag,
  not a soft warning.
- Missing or extra IDs mark that PDF `needs_review` (rather than silently dropping
  the extra object or guessing which requested row a missing one was meant for); the
  run continues on to the next PDF rather than aborting the whole batch.

### Evidence-backed review, not blind trust

Because every coded field is `{value, evidence}` (Problem 1), build a per-project
review grid: rows = coding-sheet effect × moderator, cells show the coded value plus
its evidence snippet, with accept/flag/override per cell and a rollup of
low-confidence/missing/flagged cells across the project. This is the primary new
interaction surface of the whole app — there's no equivalent in the z-curve app, where
a bad extracted statistic just drops silently out of a plot. Here a wrong moderator
code can silently bias a published pooled estimate, so it needs a surface built for a
human to actually catch it, not just a log file.

### Caching

Cache the coding manual (and baseline + project instructions) once per project run and
reuse that cached context across every PDF processed in the run, rather than resending
the full manual on every single request. The z-curve app this is based on had no
prompt-caching layer at all; a long coding manual sent unchanged across dozens of PDFs
is a much bigger latency/cost win here than it would have been there.

## Problem 3 — Linking PDFs to the list of effects/studies (the coding sheet)

**Decision:** a project holds a coding sheet — one row per effect-instance, not one row
per paper — and every run is coding-sheet-driven, not PDF-driven. A PDF with zero
coding-sheet rows is uploaded but inert.

This is a direct formalization of the CSV mechanism the Node-script project already
used: a `SourceID`-equivalent column joins rows to a PDF filename, multiple rows share
that join key when a paper reports multiple studies/experiments/conditions, and a
locator column (the old `Notes`) tells both the model and a human skimming the sheet
which specific one each row is.

Coding sheet row shape:

| column | meaning |
|---|---|
| `row_id` | stable unique key for this effect-instance; used to key coded output and to join back to the user's own effect-size spreadsheet later |
| `source_pdf` | filename of the linked PDF; must match an uploaded file before the row is run-eligible |
| `locator` | human-written description of which study/experiment/condition/DV this row is |
| any fields declared under `coding_sheet_fields` in the manual | e.g. authors/year/title, prefilled, never LLM-coded |

**v1 input paths**: GUI grid entry (add/edit/reorder rows, with a filename picker
constrained to already-uploaded PDFs) and CSV import (map an existing systematic-
review spreadsheet's columns onto `row_id`/`source_pdf`/`locator` plus whatever coding
sheet fields the manual declares). No LLM-assisted "propose candidate effects from a
PDF" discovery mode in v1 — deferred (see Later), since it's an inclusion decision that
needs a human review step regardless, and it adds a whole extra review state machine
v1 doesn't need to ship with.

A PDF with zero coding-sheet rows stays visible in the project and excluded from runs,
with the UI surfacing a count ("N PDFs have no coding sheet rows") so it's never
silently skipped without the user noticing.

---

# Divergences from the baseline app, stated explicitly

Two places this plan deliberately doesn't carry the baseline behavior over unchanged,
and why:

1. **No full-project reset on manual edit.** The baseline app deleted all output
   whenever its schema changed, because re-running its extraction was fast and cheap.
   Redoing 80 already-coded PDFs because one moderator was added is not cheap. Instead:
   adding a field marks existing rows `needs_recode` only for that new field (a
   targeted top-up run fills just the gap); removing or retyping a field invalidates
   only that column's prior values, not the whole project. A full reset stays
   available as an explicit user action; it's just never forced by an edit.
2. **No statistical/plot report.** The baseline app's output half was an R/Quarto-
   generated statistical report and plot specific to its own analysis method, which
   has no analogue in coding a moderator dataset. Output here is instead a wide
   `coded_data.csv` (one row per `row_id`, one column per moderator) and a parallel
   `evidence.csv` (same shape, cells = evidence citations) — both keyed by the user's
   own `row_id` so they join directly to the user's effect-size spreadsheet — plus a
   third, narrower artifact for actually reading rather than joining: one readable
   YAML file per PDF (`output/coded/<pdf>.yaml`) with codes and evidence together per
   coding-sheet row, meant for the human audit pass in Problem 2's review workflow —
   scanning 30+ CSV columns side by side is a bad way to actually read a handful of
   coded effects and their supporting quotes.

---

# Architecture (to build)

- FastAPI app, `127.0.0.1`-only bind, random URL token per launch, SSE endpoint per
  project for live run progress — per Part A1/A7.
- Per-project directory: `sources/` (PDFs), `coding_sheet.csv`, `coding_manual.yml`,
  optional `reference/` (uploaded original manual document), `output/{coded_data.csv,
  evidence.csv, raw/*.json, coded/*.yaml}`, plus a small hidden metadata subdirectory —
  per Part A2/A8.
- Provider layer: one adapter module per provider (Gemini, OpenRouter) behind a common
  `extract(...)` interface, model catalog/allowlist file, live model validation for
  OpenRouter — per Part A4.
- Runner: worker pool sized to `min(parallel_requests, pending PDFs)`, shared request
  pacer, cooperative cancellation, append-only run log, per-source extraction record
  upsert — per Part A7/A8, extended with the coding-sheet batching and ID validation
  from Problem 2.
- Credentials module: OS keyring via a cross-platform keyring library, explicit
  save/unlock/delete actions, session-only fallback marking, small chmod-restricted
  preferences file for non-secret flags — per Part A5, unchanged.
- Frontend: **no-build, vendored** — a small reactive no-build library (Alpine.js/
  htmx or equivalent) plus a vendored CSS framework, matching the baseline app's own
  choice to vendor its CSS/JS rather than add a Node build step. This is the packaging
  decision that most affects the three heaviest UI surfaces to build (the coding
  sheet grid, the manual/levels editor, the evidence review grid): more manual JS
  wiring per surface, no framework reactivity, in exchange for zero change to the
  Pixi-based install/release pipeline.

---

# Later (not v1)

- LLM-assisted coding-sheet discovery: propose candidate effect rows per PDF for
  human review/acceptance into the coding sheet, for users without a pre-existing
  effect list. Deferred per the decision in Problem 3.
- Cross-project moderator library: reuse a coding manual/field set across multiple
  meta-analyses without copy-pasting the YAML.
- Inter-rater/inter-model agreement view: run two models (or a model + a human coder)
  and diff their codes — a natural extension of the evidence review grid once it
  exists.
