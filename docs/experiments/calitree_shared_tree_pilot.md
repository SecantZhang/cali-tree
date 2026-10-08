# CaliTree shared decision-rule pilot — 2026-09-30

The first retrospective test does **not establish an improvement**. Learning a
shared tree slightly improves agreement and repeatability, but reduces balanced
accuracy by eliminating the yes prediction. Semantic-role features and a
robustness penalty produce the same evaluation predictions as pooled features.

This tests one component of the proposed idea: composing local observations into
a reusable decision program for new cases of the same judging task. It does not
yet learn or execute a shared library of parameterized semantic predicates.

Follow-up: [tree refinement experiment](calitree_tree_refinement.md) tests
class-balanced fitting, fraction features, supported rubric corrections and
loss pruning. Training-only selection prefers the fixed rubric; none of the
refinements demonstrates a clear overall improvement on the reused cohort.

## Design

- Source: 50 cases, 112 local conditions, five saved observation draws per case.
- Training cohort: 31 historical J cases, labels no/partial/yes = 25/5/1.
  J03 and J17 have no fully known draws; fitting uses 29 evaluable cases.
  Some historical criteria were fitted with their case's label feedback.
- Evaluation cohort: 19 later N cases, labels no/partial/yes = 7/10/2.
  Their criteria were compiled without their case labels, using previously routed
  prompts. Both cohorts and their outcomes had already been inspected, so this is
  retrospective validation, not an untouched test set.
- Local requirement text maps to three fixed semantic roles: requested change,
  target binding, and preservation. Each role supplies binary indicators for
  observed state presence; an empty role is explicitly not applicable. The mapper
  does not read outcome labels, case IDs, entity names as feature values, category
  IDs, or rationales. This is a coarse scaffold with unaudited assignments.
- CART candidates have depth 1–3 and minimum leaf case mass 2 or 4. Every case
  contributes total weight one regardless of how many known draws it has.
- Four-fold source-image/instruction-grouped validation on J cases selects the
  model using balanced accuracy, then macro F1 and complexity. All repeats stay
  together. The robust variant subtracts 0.1 times within-case pairwise prediction
  disagreement from the selection objective. Evaluation labels never select rules.
- Every arm abstains on unknown or incomplete draws. All reported conditional
  comparisons use the same known observations. No new model calls were made.

## Results

Of 95 planned evaluation draws, 75 are fully known, 16 contain unknown observations,
and four are incomplete. N04 and N57 have no known draws. Conditional agreement
therefore covers 17 of 19 cases at 78.9% draw coverage; repeat flip rate covers the
16 cases with at least two known draws. Agreement gives each evaluable case equal
weight across its known repeats.

| Method | Agreement | Balanced accuracy | Macro F1 | Partial recall | Yes recall | Repeat flip rate |
|---|---:|---:|---:|---:|---:|---:|
| Fixed reducer | 55.3% | 58.0% | 51.8% | 44.0% | 50.0% | 5.0% |
| Training majority | 29.4% | 33.3% | 15.2% | 0.0% | 0.0% | 0.0% |
| Pooled tree | 56.5% | 45.3% | 40.0% | 56.0% | 0.0% | 3.8% |
| Semantic-role tree | 56.5% | 45.3% | 40.0% | 56.0% | 0.0% | 3.8% |
| Robust semantic-role tree | 56.5% | 45.3% | 40.0% | 56.0% | 0.0% | 3.8% |

The learned tree's case-macro agreement difference versus the fixed reducer is
+1.2 percentage points, with a descriptive paired case-bootstrap 95% interval of
[-16.5, +18.8]. This interval excludes training/selection uncertainty and provides
no convincing evidence of an agreement gain. The fraction of all planned draws
that are both resolved and correct is 44.2% for both the fixed and learned rules.

The pooled tree chooses depth 1 and minimum support 4. It predicts no if any check
is absent, and partial otherwise. It cannot emit yes. The role tree chooses depth
2 and support 2 and yields the same later-case predictions. The robustness penalty
does not select a different model on this candidate grid.

Concrete cases explain the tradeoff:

- N24 is labeled partial, but its fully known observations are all complete. The
  learned rule changes the fixed reducer's yes to partial and corrects this case.
- N48 is labeled yes with all-complete observations. The same rule changes a
  correct fixed prediction to partial, losing the only correctly recognized yes
  evaluation case. N14 remains partial despite its yes annotation.
- N20 is labeled no with all-complete observations. Changing yes to partial does
  not correct it. N01, N43, N50, and N59 remain incorrectly negative despite their
  partial labels, suggesting a mismatch between local criterion boundaries and
  the overall grading rule, observational error, or annotation ambiguity.

An exploratory nested leave-source-category-out test on later N cases gives the
role tree 66.0% agreement and 50.9% balanced accuracy, but still zero yes recall.
It is an additional retrospective diagnostic, not independent confirmation.

## What this tells us

Repeatability alone is insufficient: the constant majority baseline has zero
prediction flips and poor alignment. Here part of the learned tree's stability
comes from merging yes and partial predictions. This does not show that atomic
semantic decisions became more reliable, since every arm uses the same observations.

The role scaffold does not demonstrate semantic transfer beyond pooled statuses.
Across all recorded known draws, some identical feature vectors have conflicting
labels. Their optimistic retrospective lookup accuracy is 76.5% for pooled
features and 77.1% for role features. These are representation diagnostics using
labels after evaluation, not test accuracy estimates or ceilings on richer features.

One yes training case is insufficient for robust three-class learning with this
minimum-support constraint. Five repetitions do not provide five independent
positive cases. Historical label feedback and provisional annotations further
limit conclusions. The original observations and labels are preserved; uncertain
J16 remains excluded by the source cohort.

## Next decisive experiment

1. **Audit and abstract local predicates.** Before outcome-driven changes, identify
   which checks contain mixed decisions or fail to represent the requested edit.
   Build training-derived concepts such as target identity, requested attribute
   change, relation satisfaction, and non-target preservation. Each concept needs
   a parameter schema, applicability rule, observable status definition, and
   source/edited evidence references. Keep concept identity separate from case
   parameters. Freeze this library before evaluation.
2. **Execute shared predicates.** Bind a new instruction to concept parameters and
   run the same shared checker on repeated observations. Compare against the
   original local criteria on the same cases with matched inference budgets.
   This isolates whether abstraction improves atomic correctness and stability.
3. **Learn and validate composition.** Obtain more independent cases from all three
   classes, especially yes; review human labels independently. Reserve fresh
   source/instruction groups before any trace inspection. Optimize shared rule
   structure and predicate wording using training and validation only, and keep
   the final test untouched. Compare fixed aggregation, pooled CART, semantic CART,
   and a direct optimized judge. Prompt-optimizer comparisons require the same
   training examples and an explicit matched search/inference budget.
4. **Require both alignment and robustness.** Report class-wise recall, balanced
   accuracy, macro F1, coverage, repeat disagreement, and cost. A candidate should
   improve alignment without achieving stability merely by dropping a class or
   abstaining more often. Separately perturb instruction paraphrases, concept
   order, and observation sampling; record node decisions as well as final labels.

## Artifacts and verification

Final experiment:
[`260930-21:03:10-exps/report.md`](../../logs/exps/260930-21:03:10-exps/report.md).
The directory contains input/code hashes, dependency versions, grouped selection
folds, portable tree JSON, per-decision paths, case/condition role mappings,
failure accounting, and paired uncertainty estimates. Development runs are
retained separately; none modifies the source observation cohort.

Runner: [`run/calitree_shared_tree.py`](../../run/calitree_shared_tree.py).
Model: [`semantic.py`](../../critical/core/optimization/tree/semantic.py).

```sh
.venv/bin/python -m run.calitree_shared_tree
```

Verification: 43 tests passed across the shared-tree, observation repeat, bounded
50-case, reliability, and parallel-observation suites. After report refinements,
all 13 shared-tree tests passed again. Tests include a complete synthetic offline
run, unknown/failure coverage, artifact-binding checks, repeated-case weighting,
source-group isolation, minimum support, portable execution, and evaluation-label
permutation proving independence of primary model selection. No provider calls
occurred during the experiment or tests.
