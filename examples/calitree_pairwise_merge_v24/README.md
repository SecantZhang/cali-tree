# Pairwise-merged coverage gates

Use `critical.core.calibration.merge_route_support_v24.restore(artifact)` to load
these gates with the existing `CachedEvidenceCoveredJudge`. The existing v23
upstream evidence caches remain valid. Split 2 uses a newly fitted seven-rule
parent and three deployed experts; splits 1 and 3 retain their prior experts.

The fixed v23 rejection clauses are unchanged. The merged artifact adds four
short support clauses to preserve former abstentions after removing an expert's
disagreement signal. Removed children are not retained as hidden executables.

All 144 local raw-input predictions and all 294 recorded accept/defer and verdict
decisions are preserved. These are fitted development/regression constraints,
not new generalization evidence. The implementation remains opt-in.

[Result, sharing preference and limits](../../docs/calitree_pairwise_merge.md)
