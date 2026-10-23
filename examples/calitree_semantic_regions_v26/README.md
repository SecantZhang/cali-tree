# Opt-in semantic region gates

Restore with `critical.core.calibration.semantic_regions_v26.SemanticRegionGate`.
`shortlist(program)` selects task-compatible candidates but never authorizes a
verdict. `select_bound(...)` requires observed evidence and retains the frozen
full-bank veto. Use with the existing `CachedEvidenceCoveredJudge`.

All 144 local predictions are retained. Three development cases newly defer;
total development accuracy falls 116→115/150. Many exact task/path regions have
one supporting example; inspect `support` counts through `definition(ref)`.
No default deployment or confidence calibration is implied. See
`docs/calitree_semantic_regions.md` for details and reproduction.
