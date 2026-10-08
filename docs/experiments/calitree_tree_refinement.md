# CaliTree tree refinements — 2026-09-30

The follow-up improves the learning and selection machinery, but does not establish
a better learned judge. Class balancing recovers yes predictions while losing
most partial predictions. A guarded tree preserves the fixed rubric because the
training evidence does not support more reliable corrections. Training-only
validation selects that fixed rubric, which is now an eligible candidate rather
than forcing deployment of a learned tree.

## Changes tested

1. **Class-balanced fitting with independent support.** Greedy CART splits and
   leaf decisions use equal total weight per observed class, and equal case weight
   within each class. Splits must independently meet ordinary case-mass and
   source/instruction-group support constraints. Minority weighting cannot count
   one positive case or many repeats as multiple independent cases.
2. **Proportion features.** In addition to binary role/state presence, retain the
   fraction of each role's checks that are complete, partial, absent or unknown.
   This distinguishes one absent check among three from two absent checks among
   three. Empty roles keep a distinct not-applicable indicator. This does not
   introduce case identity, category identity or outcome-derived features.
3. **Supported corrections with rubric fallback.** A guarded leaf can invoke
   the fixed reducer. Overwriting it with a constant label requires target-matching
   correction evidence from at least two independent source/instruction groups.
   The guarded objective also penalizes divergence from the fixed rubric.
4. **Loss pruning and conservative selection.** Grow with class-balanced Gini,
   then prune branches whose children do not improve balanced training loss plus
   leaf-count and optional rubric-change penalties. Training-grouped validation
   ranks models by balanced accuracy minus 0.1 times within-case prediction flips,
   then macro F1 and smaller programs. The fixed rubric is explicitly eligible.

The implementation remains a greedy shallow CART program. Pruning does not make
it globally optimal, and repeat disagreement enters validation selection rather
than the splitting objective. The original CART implementation is preserved.

## Protocol

Use the original pilot's frozen observations: 31 historical cases for training,
19 later cases for reused evaluation, five repeats each. Two historical and two
evaluation cases have no known draws. Training has 29 evaluable independent cases
(23 no, five partial, one yes). Evaluation has 17 evaluable cases (five no, ten
partial, two yes) and 75 known draws. All repeats remain within their source/image
instruction group in four-fold training validation. Model selection uses training
labels only. Unknown and incomplete draws remain unresolved for every arm.

The fixed role mapper is unchanged. The new model families are balanced presence,
balanced fractions, and guarded fractions. Each has the same depth 1–3 and minimum
support 2/4 grid. Leaf penalty is 0.005; guarded rubric-change penalty is 0.05.
These settings were fixed before follow-up scoring. Because the original outcomes
were already inspected and motivated the changes, evaluation is exploratory and
cannot provide independent confirmation. No provider calls were made.

## Results

| Candidate | Training-validation balanced accuracy | Training-validation macro F1 |
|---|---:|---:|
| Fixed rubric | 68.3% | 66.6% |
| Balanced presence | 44.7% | 43.6% |
| Balanced fractions | 45.4% | 42.8% |
| Guarded fractions | 68.3% | 66.6% |

Selection prefers the fixed rubric on validation performance and simplicity.
The guarded tree exports a single leaf that invokes that same rubric.

| Candidate | Reused-case agreement | Balanced accuracy | Macro F1 | Partial recall | Yes recall | Repeat flip rate |
|---|---:|---:|---:|---:|---:|---:|
| Fixed rubric | 55.3% | 58.0% | 51.8% | 44.0% | 50.0% | 5.0% |
| Original learned role tree | 56.5% | 45.3% | 40.0% | 56.0% | 0.0% | 3.8% |
| Balanced presence | 37.6% | 61.3% | 35.5% | 4.0% | 100.0% | 5.0% |
| Balanced fractions | 40.6% | 63.0% | 39.2% | 9.0% | 100.0% | 9.2% |
| Guarded fractions | 55.3% | 58.0% | 51.8% | 44.0% | 50.0% | 5.0% |

All arms have matched 78.9% planned-draw coverage. Agreement and confusion metrics
weight each evaluable case equally. Flip rate conditions on known repeat pairs
within 16 cases with multiple known draws. The apparent balanced-accuracy increase
for the unconstrained variants is accompanied by poor partial recall, reduced
agreement and macro F1. It is not a clear overall improvement.

The richer balanced tree selects depth 2/support 2 and uses a 0.75 threshold on
the proportion of complete requested-change checks. It predicts yes above that
threshold; below it, it predicts partial when a requested-change partial status
is present, otherwise no. This illustrates why criticality and calibrated node
semantics matter: a learned completion threshold can propagate one noisy positive
case to many partial examples.

The paired agreement difference versus the fixed rubric is -14.7 percentage points
for balanced fractions, with a descriptive case-bootstrap 95% interval of
[-41.2, +8.8]. These intervals exclude selection uncertainty and adaptive cohort
reuse. Identical guarded/fixed outputs are preservation of existing behavior, not
new evidence of calibration quality.

## Implication for the next phase

Keep class/support accounting, fraction features, loss pruning and rubric fallback
available for later experiments. Use validation to decide whether learning adds
value rather than assuming a learned tree must replace the fixed rule.

The higher priority is semantic evidence: audit which local conditions represent
critical requested changes versus secondary preservation failures, abstract them
into parameterized shared predicates, and review their status boundaries against
independent human judgments. Identical feature vectors with conflicting labels
cannot be separated merely by increasing tree depth. Collect more independent
positive cases before relying on minority reweighting. Validate the frozen concept
library and tree on fresh source/instruction groups with a matched observation
budget and balanced class coverage.

## Reproduce and inspect

```sh
.venv/bin/python -m run.calitree_tree_refinement
```

Final artifacts:
[`260930-21:25:41-exps/report.md`](../../logs/exps/260930-21:25:41-exps/report.md).
`manifest.json` records input/code hashes, dependency versions, penalties, schema
and search grid. `results.json` contains training folds, all candidate validation
metrics, the training-selected family, portable programs, evaluation decision
paths, failure accounting and conditional uncertainty. `feature_rows.json`
contains the exact encoded inputs. Development output is retained separately.

Implementation:
[`regularized.py`](../../critical/core/optimization/tree/regularized.py),
[`calitree_tree_refinement.py`](../../run/calitree_tree_refinement.py).

Verification: 51 focused tests passed. Eight new tests cover fraction severity and
duplication invariance, minority fitting without inflated support, correction
evidence independent of repeats, source-group support, real-valued split round
trips, rejection of unsupported corrections, unknown/invalid feature handling,
and evaluation-label permutation proving independence of model selection.
