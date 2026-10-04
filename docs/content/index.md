# Getting started

MetaCoder helps you code meta-analysis studies with an LLM and review the evidence behind each value. Start with a clear effect definition, a coding manual, and a sheet describing the effects you want from each PDF.

[![The MetaCoder Projects page with a demonstration project](assets/screenshots/home.png)](assets/screenshots/home.png)

## Install or update

Install the latest stable [GitHub release](https://github.com/shaheedazaad/meta-coder/releases/latest) using the commands below. Python and dependencies are managed automatically with Pixi.

**macOS / Linux** — run in a terminal:

```bash
curl -fsSL https://github.com/shaheedazaad/meta-coder/releases/latest/download/install.sh | bash
```

**Windows** — run in PowerShell:

```powershell
irm https://github.com/shaheedazaad/meta-coder/releases/latest/download/install.ps1 | iex
```

Then run `meta-coder`. Follow the installer's PATH instructions if the command is not found.

To update, stop MetaCoder, rerun the same installer, and start it again. Your projects, preferences, and saved API keys are kept. Export a project ZIP first if you want a backup. The app checks GitHub for a newer stable release when a page opens, caching the result for six hours. An available update appears as an informational banner; offline checks fail silently. Checks read public release metadata without a GitHub login; no project data or AI provider credentials are sent.

For a specific version, set `META_CODER_VERSION` (for example, `0.1.0`) before running the installer. `META_CODER_RELEASE_BASE_URL` optionally overrides the download location for mirrors and testing.

## Start from source

From a source checkout, use `pixi run start`. If you use a Python environment instead, install with `pip install -e .` and run `python -m meta_coder`. The app opens a local browser window. Keep its terminal running while you work.

Use **Documentation** in the app header to open this guide. Each project section also has a link to the relevant page. Documentation is bundled locally and does not require an internet connection.

## Your first project

1. Enter a name on **Projects** and choose **Create project**.
2. [Connect a provider](settings.md) in global **Settings**.
3. [Define your analysis](analysis.md): state exactly which comparison counts as an effect.
4. [Build your coding manual](manual.md): define the fields and categories to extract.
5. [Add a coding sheet](coding-sheet.md): identify each effect with a unique row ID and locator.
6. [Upload source PDFs](sources.md), then [review PDF matches](matching.md).
7. [Run extraction](run.md) with your selected provider and model.
8. [Review results and export](results.md), checking coded values against their supporting evidence.

> Screenshots throughout this guide show a fictional demonstration project. They do not represent research findings or a live provider run.

## Where your work lives

Projects and non-secret preferences are stored on this computer. API keys are stored separately in the system credential store. AI actions send the relevant documents or extracted text to the provider you choose; local project storage does not make those requests offline.

Use [Project settings](projects.md) to export a ZIP backup. The light, dark, or system theme preference is shared between the app and its bundled guide.
