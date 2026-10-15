# Translate learned policies into executable semantic rules

The successful local method has two parts: a lossless translation into explicit
semantic conditions, and a tested prose-only interpretation of those conditions.
The refined prose version matches all original Sol predictions: **42/48 dataset
accuracy, 48/48 agreement with the teacher**, with four source failures retained.

## Exact translation

`critical/core/calibration/policy_semantics.py` implements a `Calibrator` subclass
that compiles a learned shared v6 ordinal teacher. For each positive decision
boundary it finds all minimal sufficient feature-state combinations. Each
combination is a conjunction; alternatives are disjunctions. Execution compares
named semantic states and never sums weighted grades. The generated artifact
contains no weights, numerical cut points, case IDs, or reference lookup table.

For the Sol G2 teacher, Yes becomes:

- Near-complete progress AND complete coverage; OR
- Complete progress AND near-complete coverage.

Partial has four weaker sufficient combinations, applied only when Yes fails.
No is the remaining region. Unknown states use lower/upper completions; missing
responses and the teacher's explicitly learned uninspectability convention are
preserved. No independent identity/preservation veto is added.

This uses the meaning assigned to the existing evidence grade levels. Converting
those levels to named states preserves their ordinal information; it is a
faithful representation rather than fresh evidence or proof of causal correctness.
The current compiler supports shared v6 teachers with zero cluster offsets,
not arbitrary model families.

```python
from critical.core.calibration.policy_semantics import SemanticConditionPolicy, semantic_record
from critical.core.decision.semantic_evidence import feature_record

rules = SemanticConditionPolicy.from_teacher(teacher.metadata())
states = semantic_record(feature_record(observation, instruction))
decision = rules.predict_records([states])[0]
readable_rules = rules.render()
```

Certified teacher → semantic-state accuracy on the same 48 cases:

| Source | Teacher | Semantic conditions | Agreement |
|---|---:|---:|---:|
| Sol/high | 42/48 | 42/48 | 100% |
| Luna/none | 39/48 | 39/48 | 100% |
| Mini/none, previous quote repairs | 34/48 | 34/48 | 100% |

All twelve policies pass exhaustive known/full-unknown checks over their dependent
features (2,412 domain records), plus 576 cached predictions across the entire
source pool. Missing-response behavior is checked separately. These are logical
equivalence certificates, not image-understanding or transfer guarantees.

## Prose-only semantic execution

`SemanticPolicyExecutor` receives only cached instruction, contract, aspect and
quality prose plus a rendered reusable rule. It sees no grades, scores, weights,
cuts, case predictions, labels, examples, or images. The same Sol/high model assigns
named feature states; the deterministic semantic conditions combine them.

The initial v8 prompt scored 40/48. Inspection found two semantic drifts:

- Scope was mistaken for activity at a destination, despite no established edit
  of the intended original target.
- A bounded residual change was treated as material incompleteness on both
  progress and coverage.

V9 refines those shared definitions without adding object names, case checks,
expected labels, or numerical thresholds. It scores **10/12, 12/12, 10/12, 10/12**,
exactly matching all teacher predictions. All 44 calls completed per version;
the four original missing observations remain denominator losses.

The definitions were refined after inspecting local disagreements. This is local
optimization, not untouched held-out evaluation or repeated-sampling robustness.
Prose-only live testing covers Sol; Luna/mini results above use the deterministic
semantic-state conversion. The bottle and pouring teacher errors are preserved.

## Reproduce

The result report, audit and per-case comparisons are in
`logs/exps/261014-policy-semantic-refinement-v9/`. Generated rules and domain
certificates are in `logs/exps/261014-policy-semantic-translation-v8/`.

```bash
.venv/bin/python -m run.calitree_policy_translation --certify --output-dir logs/exps/261014-policy-semantic-translation-v8
.venv/bin/python -m run.calitree_policy_translation --replay --output-dir logs/exps/261014-policy-semantic-translation-v8
.venv/bin/python -m run.calitree_semantic_refinement --replay --output-dir logs/exps/261014-policy-semantic-refinement-v9
.venv/bin/python -m run.report_calitree_policy_translation --output-dir logs/exps/261014-policy-semantic-refinement-v9
```

These replay/certification/report commands make zero API calls. New live runs
require a separate output directory and preflight; both source snapshots and
versioned prompts are pinned. The exploration used 88 text calls, zero new image
calls, and about $0.478 in standard uncached returned-token estimates. Existing
semantic-state execution needs no extra API calls once evidence is available.
Directly emitting named states in a single image call has not been validated here.

Seven new offline tests cover the exact sufficient condition sets, full
four-feature truth table, serialization, no lookup fields, missing/unknown
behavior, learned uninspectability, grade-free payloads and named-state validation.
The full CaliTree suite passes 711 tests with 23 skipped. Independent auditing
recomputes domain predictions, local accuracy/F1/recalls/coverage, every text
payload, and exact agreement in the refined run.
