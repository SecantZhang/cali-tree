# Semantic evidence and local calibration

The fixed four-group experiment meets the requested local threshold in each
group: **10/12, 12/12, 10/12, 10/12**. Each group still contains four No, four
Partial, and four Yes references, with no case replacement. These are separate
local fits using all twelve labels per group, not held-out evaluation.

The complete metrics, rules, comparison with flat, costs, and remaining errors are
in `logs/exps/261014-semantic-visibility-calibration-v6/report.md`. The independent
requirement audit is `audit.json` beside that report.

## Modules

- `critical/core/decision/semantic_evidence.py` and its versioned v5 prompt extract
  an instruction-only contract, grounded aspects, and eight independent quality
  grades. Unknown remains null; it is not silently changed to zero.
- `critical/core/calibration/semantic_calibration.py` clusters thirteen binary
  instruction-contract descriptors without labels or outcome grades. Its v5
  monotone ordinal score has optional cluster offsets and two shared thresholds.
- `critical/core/calibration/visibility_calibration.py` adds one fixed reusable
  observability predicate: a completed extraction cannot inspect either progress
  or endpoint. Its learned verdict requires two correct source cases and counts
  toward the shared four-term coefficient budget. It assigns a calibration label
  to uninspectable evidence; it does not alter the extracted facts.

The shared and clustered v6 policies each allow at most four nonzero terms,
including cluster offsets and the optional observability verdict, plus two cuts.
Class-specific collapse is prevented by requiring two correctly recognized
sources per class. The joint objective is the mean of accuracy and macro-F1,
followed by macro-F1, correct count, worst-class recall, and simplicity.

Clustering is pooled and label-blind; supervised calibration remains independent
per group. Cluster adjustments require two local source cases. Missing model
responses always abstain and remain in the denominator. Other unknown facts
use lower/upper intervals and resolve only when both imply the same verdict.

No exact instructions, words, case IDs, image hashes, or stored target labels
enter policy prediction. Identifiers and target hashes appear in provenance only.

## Reproduce the saved experiment

These commands use immutable existing caches and make **zero API calls**:

```bash
.venv/bin/python -m run.calitree_semantic_evidence --replay --output-dir logs/exps/261014-semantic-contract-evidence-v5
.venv/bin/python -m run.calitree_semantic_calibration --output-dir logs/exps/261014-semantic-cluster-calibration-v5-r1
.venv/bin/python -m run.calitree_visibility_calibration --output-dir logs/exps/261014-semantic-visibility-calibration-v6
.venv/bin/python -m run.audit_calitree_semantic
.venv/bin/python -m pytest tests/unit/calitree -q
```

The extractor separately supports `--preflight` and explicit `--live` for a new
versioned output directory. It pins the original fixed 48 cases, prompt/schema,
source hashes, model identity, and image hashes. Each case receives one new
source-first call with the same `gpt-6.1-sol/high` profile as the cached flat arm.
The completed run has 44 responses and four preserved SSL transport failures.

The v5 comparison retains its first invalid attempt for audit: floating-point
centroid drift caused restoration to reject values just outside [0,1]. The
repaired v5-r1 comparison clips this numerical drift and does not classify
restoration bugs as calibration infeasibility.

## Interpretation

Richer evidence and observability handling drove the gains. Clustering added no
correct cases. In G4 it improved macro-F1 by abstaining instead of issuing a
wrong Yes, reducing coverage from 11/12 to 10/12. Prefer the shared policy while
investigating whether finer check-semantic clusters yield a repeatable benefit.

The prompt and observability hypothesis were developed after earlier failures.
The bottle still exposes coupled endpoint/identity penalties; pouring exposes
an unverified requested endpoint. Four groups of local fits do not validate
transfer to unseen cases, and one response per case does not test repeatability.
