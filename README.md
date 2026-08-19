# Meta-Coder (MVP)

Local browser app for LLM-assisted meta-analysis moderator coding. See `plan.md` for
the full design and `todo.md` for the build order — this is everything through the
MVP cutoff in `todo.md` (steps 1–8).

## Run it

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m meta_coder
```

This opens your browser to a local, randomly-tokened URL
(`http://127.0.0.1:<port>/<token>/`). The server binds only to `127.0.0.1`.

## Try it out

1. Create a project.
2. Set a Gemini API key (session-only — held in memory, never written to disk; get
   one at [Google AI Studio](https://aistudio.google.com/app/apikey)).
3. Write a coding manual: `effect_definition` (what comparison counts as "the
   effect"), any `coding_sheet_fields` your coding sheet will supply, and `effects`
   (the fields the model codes, with `levels` for categorical ones). A starter
   example is pre-filled when you create a project.
4. Upload the PDFs you want coded.
5. Upload a coding sheet CSV: `row_id`, `source_pdf`, `locator`, plus whatever
   `coding_sheet_fields` your manual declares — one row per effect/experiment/
   condition. A row whose `source_pdf` doesn't match an uploaded file is flagged as
   a blocking error, not silently skipped.
6. Run. Every coding-sheet row for one PDF is sent in a single request; the model
   must echo back the exact row IDs it was given, or that PDF is marked
   `needs_review` rather than accepting a best-effort guess.
7. Download `coded_data.csv` and `evidence.csv` — same shape, `evidence.csv` has the
   supporting page/quote for each cell. Hand-check a few rows against evidence before
   trusting the results.

## What's deliberately not here yet

OS keyring credential storage, concurrent/paced runs with live progress, retry,
raw-response viewing, the evidence review grid, a structured manual editor (raw YAML
only for now), a coding-sheet GUI grid, OpenRouter, downloads/folder-open, an
app-level settings page, and the Pixi installer. All ordered and reasoned about in
`todo.md`.

## Tests

```sh
pip install -e ".[dev]"
pytest
```

`tests/test_mechanism.py` is the important one: it proves the row_id/locator
mechanism (build the response schema, hard-reject on any ID mismatch) with
hand-written fake responses, with no API call involved.

## Frontend

Server-rendered Jinja templates styled with daisyUI (Tailwind v4 plugin). No Node at
install or launch — `meta_coder/static/app.css` is a compiled bundle checked into the
repo. See `build-css/README.md` if you change templates and need to regenerate it.
