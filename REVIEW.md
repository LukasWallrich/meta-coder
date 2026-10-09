# Conservative PDF matching — review only

Candidate policy preserves Unicode and short surnames, requires identity beyond a year, caps confidence for contradictory publication years, and downgrades nearly tied candidates. Low/medium suggestions remain unselected for bulk application. Both score and signal cache identities are bumped.

No PR: the 0.4 contradiction cap and 0.1 ambiguity margin are policy choices that need a realistic PDF/citation corpus. First-page citation text can still resemble the target article, and a wrong extracted publication year can penalize a correct match. Candidate assignment remains greedy, including competition between different papers for one PDF. Those behaviors need review before relying on the heuristics.

The four new regressions cover short/Unicode surnames, year-only evidence, contradictory years and equal candidates. Run the complete suite to inspect changed cache/scoring expectations before promotion.
