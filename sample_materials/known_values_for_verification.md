# Known values, for checking the app's output — not an app input file

Pulled directly from `reanalysis_labeled_checked.xlsx` (rows `Row_ID` 1 and 2, both
`Filename` = "Ambrosecchia et al. (2015)"). This is your own already-checked coding
of this paper, so it's a reasonable ground truth to hand-verify a Gemini run
against — this is exactly the MVP acceptance test in `todo.md`: run this one paper
(2 conditions in the same PDF), then compare `coded_data.csv` to this table and
`evidence.csv`'s quotes to confirm the two rows weren't swapped or blended.

Blank cells mean the value isn't present in the spreadsheet, **not** necessarily
that the article doesn't report it — the spreadsheet may have simply not needed
that field if `d`/`r` were taken directly from the paper. Don't treat a blank here
as proof the model got something wrong.

| Field | row 1_1_A (Experiment 1, intact objects) | row 1_2_B (Experiment 2, broken objects) |
|---|---|---|
| Age | 22.5 | 22.5 |
| Gender | 0.333 | 0.333 |
| Handedness | 1 | 1 |
| SampleSize | 12 | 12 |
| ResponseMode | Between-hand | Between-hand |
| BetweenKeyDistanceMm | 17.1 | 17.1 |
| HandsCrossed | Uncrossed | Uncrossed |
| ViewingDistanceCm | 57 | 57 |
| HandScreenDistance | (blank) | (blank) |
| SpeedInstruction | No | No |
| AccuracyInstruction | No | No |
| OrientationInstruction | No | No |
| FunctionalInstruction | Not mentioned | Not mentioned |
| DecisionType | Upright/inverted | Upright/inverted |
| DecisionTarget | Object | Object |
| Mapping | One | One |
| StimulusType | Photographs | Photographs |
| NumberOfStimuli | 4 | 4 |
| BrokenObjects | No | Yes |
| Presentation | Central | Central |
| PracticeTrials | 16 | 16 |
| Blocks | 2 | 2 |
| TrialsPerBlock | 80 | 80 |
| TotalTrials | 160 | 160 |
| FixationDurationMs | 500 | 500 |
| IntertrialTimeMs | 0 | 0 |
| PresentationTimeMs | 1000 | 1000 |
| ResponseWindowMs | 1000 | 1000 |
| Mask | No | No |
| ResponsePeriod | During presentation | During presentation |
| TrialFeedback | Yes (spreadsheet doesn't distinguish errors-only vs. all-responses — check the PDF) | Yes (same caveat) |
| FeedbackDurationMs | 500 | 500 |
| ResponseTimeCompatibleMs / IncompatibleMs / SDs, TStatistic, FStatistic | (blank in spreadsheet — this paper's checked entry used `d`/`r` directly, so it's a genuine test of whether the model can still find and report any raw RTs/test statistics the article states) | (blank, same note) |

For reference only — **not** fields the app should extract (these are the analyst's
own computed effect sizes, derived from the raw data, not something to read off the
page): `d` = 0.573 (row 1), 0.320 (row 2); `r` = 0.957 (both rows, from the DOI's
correlation-based conversion).

**The one column that should differ between the two rows and is the actual point of
this test**: `BrokenObjects` — `No` for Experiment 1, `Yes` for Experiment 2. If a
run comes back with this swapped or identical across both rows, the row_id/locator
mechanism has a real bug, not just an LLM extraction miss.
