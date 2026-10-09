# Remaining bug fixes from the latest Claude thread

The source handoff is Claude session `2f2dbccb-dd0e-4d02-b31b-420413277bb4`, ending with six upstream PRs and a next-wave queue. This integration branch combines the six existing PRs and the verified fixes below, with merge conflicts resolved. It has no PR of its own.

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

## Review branches without PRs

Each branch contains code, focused regressions and `REVIEW.md` explaining policy decisions and remaining gaps. They are based on this integration's verified fixes, rather than intended as independent upstream PRs.

| Branch | Candidate work | Validation / reason withheld |
|---|---|---|
| [review/result-freshness-and-retries](https://github.com/LukasWallrich/meta-coder/tree/review/result-freshness-and-retries) | Input fingerprints across reuse, collation, UI completion and CSV download; preserve a verified success while recording failed retry attempts; discard cleared progress. | 12 new tests plus six concurrency tests pass; full suite 649 passed / 4 failed. Legacy-result and terminal-state policy needs agreement; ZIP/YAML freshness, hashing cost and multi-file durability remain gaps. |
| [review/conservative-pdf-matching](https://github.com/LukasWallrich/meta-coder/tree/review/conservative-pdf-matching) | Unicode/short surname identity, contradictory-year caps, ambiguity margins, cautious bulk selection and cache version bumps. | Four new tests and all 645 Python tests pass. Thresholds and first-page citation noise need a realistic corpus. |
| [review/spreadsheet-export-and-provenance](https://github.com/LukasWallrich/meta-coder/tree/review/spreadsheet-export-and-provenance) | Explicit formula-protected BOM CSV variant preserving negative numbers; separately joinable per-result provenance CSV. | Two new tests and all 644 Python tests pass. Needs real spreadsheet validation, UI/docs and freshness integration; metadata layout is a review decision. |
| [review/gemini-transient-retries](https://github.com/LukasWallrich/meta-coder/tree/review/gemini-transient-retries) | Bounded transient HTTP retries with numeric Retry-After and interruptible backoff. | Five new tests and all 647 Python tests pass. Needs pacing/total-timeout integration, HTTP-date Retry-After and cost policy review. |

Do not merge the review-only branches as production fixes yet. In particular, the freshness branch intentionally has unresolved inherited test contracts. Configurable OpenAI-compatible temperature and seeds remain enhancements; no forced temperature change was made.

## Merge notes

Overlapping PRs need conflict resolutions, especially #2/#6 in Gemini transport, #3/#7 in manual docs, #5/#11/#19 in import guards, and #2/#15 in runner error redaction. This branch contains the tested combined resolutions: retain both response review and credential redaction, bounded imports with the post-await busy checks, and storage-error preservation with sanitized errors. Appended test-file conflicts retain both sets of regressions.
