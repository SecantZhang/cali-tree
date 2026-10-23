# Semantically merged region gates

Restore with `critical.core.calibration.semantic_region_merge_v28.SemanticMergedRegionGate`
and use with the existing `CachedEvidenceCoveredJudge`. A region needs matching
evidence, full-bank consensus/rejection approval and a supported match from at
least one contributing expert. Task shortlisting alone never authorizes a verdict.

Nineteen merges reduce the three alternative split banks from 63 to 44 regions;
seven final regions combine multiple experts. All 144 local predictions and
294 recorded routes/final labels are preserved, including 115 exact regular
fallbacks. Regions may broaden on unseen inputs: this is an opt-in empirical
merge, not exact equivalence or proven unseen-case correctness.

See `docs/calitree_semantic_region_merge.md` for conditions, results and usage.
