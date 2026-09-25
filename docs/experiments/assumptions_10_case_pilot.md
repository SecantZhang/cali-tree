# Ten-case condition-tree assumption pilot

Date: 2026-09-23. This is a retrospective diagnostic of existing real AURORA
evaluations, with new local tree fits and an assistant visual/text audit. No new
model API calls were made.

## Scope

Ten distinct source-instruction tasks cover all eight AURORA source categories,
all five editors, and labels `no/partial/yes` in a `3/4/3` allocation. Selection
uses metadata coverage within 33 cases with compatible stored traces, not their
pilot outcomes. Seven selected prompts are modified and three are unchanged seed
rubrics. The cohort is selected from prior repair experiments; it is not a
probability sample of AURORA or an untouched validation set for prompt optimization.

For each case, use ten recorded repetitions at temperature 0.3 with the historical
`gpt-5.4-mini` provider. Use fresh-natural ablation repetitions, not successful
optimization-selection repeats, and exclude acceptance-triggered confirmation
runs. The effective sample size is ten tasks, not one hundred independent examples.

The prompt-to-semantic-policy arm and the independent-condition arm are distinct:
the former extracts the selected rubric and executes it in one LLM call; the latter
uses a generic instruction decomposition and fixed aggregation. Neither is the
complete proposed compiler plus learned concept library. The new tree experiment
learns a shared mapping from the latter's recorded condition measurements.

## Results

| Assumption | Finding |
|---|---|
| Well-defined score | Preservation policies differ between selected rubrics and fixed aggregation; benchmark human yes can coexist with a partial-preservation measurement. Scoring validity remains unverified. |
| Complete decomposition | Count/duplication is omitted in C10; C02 duplicates modifiers inside its core check; C04 just restates a subjective task. A structured policy adds a scene-replacement exception absent from its source rubric. |
| Dependable condition evaluation | 20/42 leaf evaluators vary across ten repeats, affecting 7/10 cases. Absolute concept accuracy cannot be measured without independent human concept labels. |
| Sufficient shared features and small tree | Identical observed feature vectors occur with different human labels. A depth-2 tree obtains 66% leave-task-out accuracy but zero recall on the three yes cases. |
| Transfer across tasks | Leave-source-category-out accuracy is 58%. This is a preliminary stress test, not proof of operation-family or external-dataset transfer. |
| Adequate data | Ten selected cases, three yes cases, no human concept labels, and no individual rater votes are insufficient to establish the assumptions. |

| Method | Correct recorded repetitions |
|---|---:|
| Selected natural prompt | 61/100 |
| Extracted policy in JSON | 67/100 |
| Same policy in controlled prose | 69/100 |
| Original text losslessly wrapped in JSON | 57/100 |
| Generic independent leaves plus fixed rules | 66/100 |
| Learned depth-2 tree, leave task out | 66/100 |
| Learned depth-2 tree, leave source category out | 58/100 |

The semantic JSON arm changes the modal prediction on 5/10 cases. Its six-point
accuracy advantage over the natural prompt has a paired task-bootstrap 95%
interval of **-20 to +32 percentage points**. Disagreement is not automatically
noise, but improvement is not established either. Lossless formatting changes the
mode on 7/9 non-tied comparisons, so behavioral disagreement alone does not prove
semantic information was lost.

For the coarse and detailed feature schemas, the best possible deterministic
lookup on the *observed* feature-label records is capped at 81% and 88%, respectively,
because of exact conflicting-feature collisions. These are empirical limits of
the measured representations in this sample, not limits on richer concepts or
the proposed architecture. In particular, C01 (human yes) and C07/C08/C09 (human
partial) can share fully satisfied target checks plus partial preservation.

All folds keep a task's ten repetitions together. Features exclude human scores,
instruction text, editor identity, source-category identity, optimizer identity,
and original final judgments. Both schemas use preselected `max_depth=2`,
`min_samples_leaf=20`, and `random_state=44`; no hyperparameters are selected from
these results.

The visual audit is unblinded Codex inspection, not independent human annotation.
It was not used as training features. Human-verified feature sufficiency, stability
of repeated instruction decomposition, and full unseen-task generalization remain
untested.

## Artifacts and reproduction

- [Full report](../../logs/exps/260923-20:00:01-exps/report.md)
- [Images, source prompts, condition plans, and repeat rationales](../../logs/exps/260923-20:00:01-exps/case_review.html)
- [Selection and input fingerprints](../../logs/exps/260923-20:00:01-exps/manifest.json)
- [Per-case results](../../logs/exps/260923-20:00:01-exps/case_results.json)
- [Learned trees and fold membership](../../logs/exps/260923-20:00:01-exps/learned_trees.json)
- [Versioned visual audit](assumptions_10_case_visual_audit.json)
- [Runner](../../run/assumptions_pilot.py)

```bash
.venv/bin/python run/assumptions_pilot.py \
  --output-dir logs/exps/260923-20:00:01-exps \
  --archive /private/tmp/calitree-assumptions-aurora-human-ratings.zip
```

The archive is optional for numerical replay. Its SHA-256 was verified against
`run/setup_aurora_bench.py`; the run includes the 20 extracted images and their
individual hashes. Unit checks cover task-fold isolation, empirical collision
bounds, and repeat-disagreement/tie calculations.

Before scaling, revise count/identity coverage and preservation severity/relevance,
separate uncertainty from partial fulfillment, obtain independent concept
annotations, and freeze the complete pipeline before testing new task groups.
