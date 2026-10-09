# Result freshness and failed-retry selection — review only

Based on `review/remaining-bug-fixes`, the integration of the verified PRs. No PR is intended for this branch yet.

Candidate behavior:
- Hash the effective manual, prompt version, exact requested rows, PDF bytes, provider/model and semantic endpoint/reasoning settings.
- Treat a legacy or changed-input result as `stale`: preserve its raw record but exclude its values from current collation, UI completion and CSV downloads.
- Save the latest attempt separately; preserve an earlier verified `ok` selection when a retry fails, is cancelled or needs review. Show the latest attempt in the retry table.
- Equivalent manual saves are handled by PR #9.

Validation: the 12 new freshness/selection/state regressions pass; together with the six inherited runner-concurrency tests, 18 tests pass. The full branch suite reports 649 passed and four failed. The resume fixture now supplies real source PDF bytes rather than relying on mocked extraction of missing files. The inherited full suite currently has four failures because its legacy fixtures assume unverified successful records remain reusable, CSV downloads return previously written bytes, and terminal in-memory state overrides disk results. Those contracts must be explicitly decided and their tests revised before opening a PR.

Open review decisions and gaps:
1. Confirm that changing provider/model requests fresh extraction, while timeout/pacing/service tier do not.
2. Confirm that all legacy results should be unverified, rather than recovering fingerprints from historical audit blobs.
3. Decide whether a later `needs_review` attempt should replace an earlier verified success.
4. Hashing every PDF during page rendering needs caching or offloading to avoid blocking the event loop.
5. Full project ZIPs and per-PDF YAML still contain the saved working artifacts, so freshness warnings/regeneration must cover those export paths.
6. Clear/reset now discards terminal progress; review the interaction between terminal storage errors and selected persisted results.
7. Latest-attempt persistence is atomic per file, but selection and attempt files are not a multi-file transaction.
8. Split this branch into freshness and retry-selection PRs once the policy and integration gaps are resolved.
