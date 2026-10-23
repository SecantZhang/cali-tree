# Counterexample-calibrated coverage gates

Load with `RejectionCoverageGate` and use the existing `CachedEvidenceCoveredJudge`.
The layer only rejects prior acceptances; accepted labels remain frozen expert
outputs. It uses declared Boolean evidence/task predicates, with at most three
literals per clause. There is no runtime case-ID or image-hash blacklist.

The three gates reject all 22 reviewed false acceptances, preserve all 38 correct
transfer acceptances, and retain 144/144 local trained tree outputs. These are
post-calibration regression results. Only 1/22 reviewed errors was rejected when
its own counterexample was withheld, so broad unseen-failure protection is not
established. Keep this path opt-in and evaluate new inputs independently.

[Full result and error review](../../docs/calitree_counterexample_coverage.md)
