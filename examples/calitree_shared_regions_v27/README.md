# Shared semantic region gates

Restore using `critical.core.calibration.shared_regions_v27.SharedRegionGate`.
Use with the existing `CachedEvidenceCoveredJudge`. `shortlist(program)` selects
candidates; `select_bound(...)` requires evidence, consensus and rejection checks.
`definition(ref)` expands shared literals and exposes pooled/per-task support.

These three alternative split banks preserve v26 decisions exactly: 144 local
predictions, 294 total recorded decisions and 115 exact regular fallbacks.
Definitions fall 149→63 but task-specific support sparsity is unchanged. No real
cross-expert equivalents were found. These remain opt-in research artifacts.
See `docs/calitree_shared_regions.md` for results and reproduction.
