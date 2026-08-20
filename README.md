# MetaCoder

Local browser app for LLM-assisted meta-analysis moderator coding. See `plan.md` for
the full design and `todo.md` for the build order and current status.

## Run it

From source:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m meta_coder
```

Or via [Pixi](https://pixi.sh) (locked environment, no manual `pip install`):

```sh
pixi run start
```

Either way, this opens your browser to a local, randomly-tokened URL
(`http://127.0.0.1:<port>/<token>/`). The server binds only to `127.0.0.1`.

## Local development

The project has two Pixi environments (`[tool.pixi.environments]` in
`pyproject.toml`): `default` (just the app's runtime dependencies) and `dev`
(`default` plus `pytest`). Both install `meta_coder` itself as an editable
package (`pypi-dependencies = { path = ".", editable = true }`), so code
changes take effect on the next request/restart — no reinstall step.

```sh
pixi install          # materializes .pixi/envs/default from the committed pixi.lock
pixi install -e dev   # same, for the dev environment (only needed once)

pixi run start         # run the app (equivalent to `python -m meta_coder`)
pixi run -e dev test   # run the test suite (equivalent to `pytest -q`)
pixi shell -e dev      # drop into an interactive shell inside the dev environment
```

If you change a dependency in `[project.dependencies]` or `[tool.pixi.*]`,
run `pixi install` (or just `pixi run ...` — it updates the lock automatically
when the manifest changed) and commit the resulting `pixi.lock` so everyone's
environment — and the release bundles built by `scripts/build_release.sh` —
stays reproducible.

Equivalent plain-venv workflow, if you'd rather not use Pixi day-to-day:

```sh
pip install -e ".[dev]"
pytest
```

A few other things worth knowing while developing:

- **Isolating project data.** By default the app stores projects, run
  settings, and non-secret preferences under the OS's standard per-user data
  directory (see `meta_coder/paths.py`). Set `META_CODER_HOME` to point that
  somewhere disposable instead, so testing doesn't touch (or get confused by)
  your real projects:
  ```sh
  META_CODER_HOME=/tmp/meta-coder-dev pixi run start
  ```
- **Frontend changes.** Templates (`meta_coder/templates/`) and
  `meta_coder/static/app.js` are server-rendered/served directly — edits show
  up on the next page load, no build step. `meta_coder/static/app.css` is a
  compiled Tailwind v4/daisyUI bundle checked into the repo; see
  `build-css/README.md` if you change template classes and need to regenerate
  it (that's the one place Node is involved, and only at dev time).
- **Building a release bundle locally**, e.g. to test `scripts/install.sh`
  end-to-end without a real host: `scripts/build_release.sh` archives a git
  ref (default `HEAD`) into `dist/meta-coder-<version>.tar.gz` — see
  "Installing as an end user" below for the full install-script flow.

## Installing as an end user

`scripts/install.sh` (macOS/Linux) and `scripts/install.ps1` (Windows) install a
versioned release bundle's locked Pixi environment and put a `meta-coder` launcher
on your PATH — no separate Python install needed. Point `META_CODER_RELEASE_BASE_URL`
at wherever release bundles are published (there's no hosted release feed for this
project yet — see `scripts/build_release.sh` to build one, and both installers error
out clearly if this isn't set):

```sh
META_CODER_RELEASE_BASE_URL=https://github.com/<org>/<repo>/releases/latest/download \
  sh scripts/install.sh
```

Re-running the installer installs the newest version and removes the old one — see
`todo.md` step 20 for how this was verified (a local HTTP server standing in for a
real release feed, install → upgrade → confirm only the new version remains). The
Windows script mirrors the same logic but hasn't been run on an actual Windows
machine.

## Try it out

1. Create a project.
2. Set an API key in **Settings**: paste a Gemini key (get one at
   [Google AI Studio](https://aistudio.google.com/app/apikey)) or an OpenRouter key
   ([openrouter.ai](https://openrouter.ai/settings/keys)). Held in memory for the
   OS credential store (macOS Keychain / Windows Credential Locker / Linux Secret
   Service). Keys are always saved securely and must be unlocked again after restart;
   there is no session-only or plaintext fallback.
3. Write a coding manual on the project's **Coding manual** tab — a structured
   editor, not raw YAML: `effect_definition` (what comparison counts as "the
   effect"), and `effects` (the fields the model codes, with categories for
   categorical ones). A starter example is pre-filled when you create a project. You
   can also import an existing `manual.yml`, or drop a PDF/DOCX coding manual into
   the automatic generator. Its provider/model are configured globally in Settings,
   independently of extraction. The draft appears in the editor without a page reload
   and is not saved until you explicitly validate and save it.
4. Upload the PDFs you want coded (**Source PDFs** tab).
5. Upload a coding sheet CSV (**Coding sheet** tab): `row_id`, `source_pdf`,
   `locator`, `authors`, `year` — one row per effect/experiment/condition. A row
   whose `source_pdf` doesn't match an uploaded file is flagged as a blocking error,
   not silently skipped.
6. On the **Run** tab, pick a provider/model and parallelism/pacing, then run. Every
   coding-sheet row for one PDF is sent in a single request; the model must echo
   back the exact row IDs it was given, or that PDF is marked `needs_review` rather
   than accepting a best-effort guess. Progress updates live; a run in progress can
   be cancelled (in-flight PDFs finish, queued ones stop). Failed/needs-review PDFs
   can be retried individually or all at once without reprocessing PDFs that already
   succeeded.
7. On the **Results** tab, download `coded_data.csv` and `evidence.csv` — same
   shape, `evidence.csv` has the supporting page/quote for each cell — plus one
   readable `output/coded/<pdf>.yaml` per PDF for actually reading a handful of
   coded effects and quotes rather than scanning CSV columns. Each PDF's raw
   provider response is also viewable from the Run tab. Hand-check a few rows
   against evidence before trusting the results.

## What's here

- Providers: Gemini (native PDF input) and OpenRouter (manual model ID, live
  validated before a run starts).
- Credentials: always persisted in the OS keyring, with no session-only or plaintext
  fallback; saved keys are explicitly unlocked after restart.
- Concurrent, paced runs (worker pool + a globally-shared request pacer), live
  progress, cooperative cancellation, retry of failed/needs-review PDFs.
- Structured coding-manual editor (no hand-edited YAML), including review-first LLM
  drafts from PDF/DOCX manuals; CSV coding-sheet import, per-project run settings,
  and a global settings page (API keys, manual-generator model, upload size cap).
- Downloads: per-file CSV/YAML, or a full project ZIP; open the project folder
  directly.

## What's deliberately not here yet

The evidence-backed review grid (accept/flag/override per coded cell — the
project's primary planned interaction surface, see `plan.md` "Problem 2"),
field-level invalidation on manual edits (a manual change still does a full
`output/` reset), and a coding-sheet GUI grid (CSV import only). Both are ordered
and reasoned about in `todo.md`.

## Tests

```sh
pixi run -e dev test
# or, in a plain venv:
pip install -e ".[dev]"
pytest
```

`tests/test_mechanism.py` is the important one: it proves the row_id/locator
mechanism (build the response schema, hard-reject on any ID mismatch) with
hand-written fake responses, with no API call involved.
`tests/test_runner_concurrency.py` proves concurrent runs attribute results to the
right PDF, the request pacer's delay is global not per-worker, a retry of a subset
of PDFs doesn't blank out other PDFs' prior results, and cancellation stops queued
work without killing an in-flight request.

## Frontend

Server-rendered Jinja templates styled with daisyUI (Tailwind v4 plugin). No Node at
install or launch — `meta_coder/static/app.css` is a compiled bundle checked into the
repo. See `build-css/README.md` if you change templates and need to regenerate it.
