# Supported evidence selectors

Load a gate with `SupportedCoverageGate`. Each gate embeds its unchanged frozen
experts, declared evidence guards, task profiles and semantic-support conditions.
It contains no training source memberships or raw instruction lookup table.

For raw inputs, use `CachedEvidenceCoveredJudge` with the versioned upstream
feature cache produced by `run.verify_calitree_raw_coverage`. Those larger caches
are kept under the experiment directory and store observations/interpretations,
not human labels or final verdicts. For new inputs, the existing compiler,
observer and interpreter provide evidence; unsupported cases use the regular judge.

All 144 recorded local inputs retain correct tree outputs. Accepted-prediction
precision on the exploratory transfer diagnostic is 38/60, so these selectors
remain opt-in and are not a correctness guarantee for unfamiliar examples.
See [the complete evidence and limitations](../../docs/calitree_evidence_coverage.md).
