# Remaining bug fixes from the latest Claude thread

The source handoff is Claude session `2f2dbccb-dd0e-4d02-b31b-420413277bb4`, ending with six upstream PRs and a next-wave queue. This integration branch combines the six existing PRs and the verified fixes below (follow-up PRs #20–#23 are listed separately and not merged here), with merge conflicts resolved. It has no PR of its own.

## Verified fixes

| Upstream PR | Result |
|---|---|
| [#5](https://github.com/shaheedazaad/meta-coder/pull/5) — updated | Bulk retry works after restart and includes older failures after a subset retry, restricted to PDFs in the current sheet. |
| [#9](https://github.com/shaheedazaad/meta-coder/pull/9) | Equivalent manual saves preserve results, including formatting-only imports and incomplete starter manuals. |
| [#10](https://github.com/shaheedazaad/meta-coder/pull/10) | Malformed model fields marked for review cannot crash CSV/YAML rendering. |
| [#11](https://github.com/shaheedazaad/meta-coder/pull/11) | Bounded BOM-aware UTF-8 sheet imports validate headers, quotes and widths before atomic replacement; changed sheets invalidate old output. |
| [#12](https://github.com/shaheedazaad/meta-coder/pull/12) | Missing/invalid project lookups produce 404 across routes, including polling after deletion. |
| [#13](https://github.com/shaheedazaad/meta-coder/pull/13) | New PDF uploads preserve safe Unicode and punctuation, handle Windows device names, and fit a portable byte limit. |
| [#14](https://github.com/shaheedazaad/meta-coder/pull/14) | Rejected manual edits remain unsaved; delayed manual/sheet drafts ask before replacing current edits. |
| [#15](https://github.com/shaheedazaad/meta-coder/pull/15) | Storage errors preserve extracted data; raw, YAML and each CSV publish atomically. |
| [#16](https://github.com/shaheedazaad/meta-coder/pull/16) | Cover the existing seven-line gap and run both coverage tasks in CI. |
| [#17](https://github.com/shaheedazaad/meta-coder/pull/17) | Model checks and ZIP compression run off the event loop; failed ZIPs are removed and incomplete uploads excluded. |
| [#18](https://github.com/shaheedazaad/meta-coder/pull/18) | Polling failures are visible and recoverable; status payloads are checked and progress is announced accessibly. |
| [#19](https://github.com/shaheedazaad/meta-coder/pull/19) | Manual imports enforce the upload limit and reject invalid encoding without replacing saved inputs. |

Each new behavior has a regression that reproduced the failure before its fix. Full suites passed on each PR branch. Additional coverage checking removed obsolete HTTP handlers and covered a provider failure followed by failed error-record persistence.

Integrated validation:
- Python: **642 passed**, **100% statement and branch coverage**.
- JavaScript: **71 passed**, **100% statements, branches, functions and lines**.
- `mkdocs build --strict`: passed; combined manual documentation rebuilt.
- Main checkout and the earlier Claude worktrees were preserved. PR #5's existing worktree received its tested follow-up commit.

Upstream GitHub Actions currently report `action_required` for fork contributions. The maintainer must approve those workflow runs; these results are local Linux verification, not completed Windows/macOS CI. Claude's original #4 still has only static PowerShell validation.

## Follow-up PRs from the review branches

The four former `review/*` branches were rebuilt as standalone PRs on upstream `main`, reviewed, fixed and opened. The `review/*` branches are superseded and kept only for history. None of these PRs depends on another open PR.

| Upstream PR | Result |
|---|---|
| [#20](https://github.com/shaheedazaad/meta-coder/pull/20) | Gemini retries HTTP 429/500/502/503/504 at most three times (2 s, then 4 s), honoring Retry-After in seconds or HTTP-date form up to 30 s; cancellable, audited per attempt, redacted. Open: retry/cost policy, global pacer integration. Overlaps #2 in the Gemini transport. |
| [#21](https://github.com/shaheedazaad/meta-coder/pull/21) | PDF matching counts short and Unicode surnames but not initials or short title words, ignores year-only evidence, caps contradictory years at 0.4, flags near-ties (0.1) as low, preselects only high confidence, reads "2020a" as 2020. Open: thresholds need a realistic corpus. |
| [#22](https://github.com/shaheedazaad/meta-coder/pull/22) | Optional OWASP-escaped BOM/CRLF spreadsheet copies of the canonical CSVs and a per-row `provenance.csv` (provider, model, audit operation id), with UI links and docs. Also fixes doubled CSV line endings on Windows. Open: manual Excel/LibreOffice check. May conflict with #17 in download routes. |
| [#23](https://github.com/shaheedazaad/meta-coder/pull/23) | Results carry an input fingerprint (canonical manual, row IDs and locators, PDF SHA-256, provider/model settings); mismatches show as outdated and are recoded, legacy results stay usable. Failed retries never replace a saved success. Merges mechanically with #5, #9, #11 and #15 (combined suite passes). |

Each passes the full Python and JavaScript suites on its own branch (local venv; pixi unavailable). Local coverage is 99.7% on each, from the same seven pre-existing lines that #16 covers.

Configurable OpenAI-compatible temperature and seeds remain enhancements; no forced temperature change was made.

## Merge notes

Overlapping PRs need conflict resolutions, especially #2/#6 in Gemini transport, #3/#7 in manual docs, #5/#11/#19 in import guards, and #2/#15 in runner error redaction. This branch contains the tested combined resolutions: retain both response review and credential redaction, bounded imports with the post-await busy checks, and storage-error preservation with sanitized errors. Appended test-file conflicts retain both sets of regressions.
