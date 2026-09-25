# Ten-case GPT-6-Luna comparison

## Results and interpretation

Completed 1,870 model generations on the same ten cases, yielding 100 final-score
observations per arm. All completed outputs parsed successfully. Fifteen logged
requests failed with connection errors and were resumed; SDK-internal retries are
not separately counted. Every planned generation has exactly one completed record.
Estimated standard list-price usage is $0.918, excluding unobserved usage on failed
requests and ignoring cache discounts.

| Scoring setup, reasoning none | GPT-5.4-mini correct /100 | GPT-6-Luna correct /100 |
|---|---:|---:|
| Full selected judge prompt | 74 | 50 |
| Existing conditions + fixed aggregation | 67 | 45 |
| New Luna conditions + fixed aggregation | 55 | 38 |

Luna medium reasoning on the full judge prompt scored **60/100**. This arm also
omits temperature, so its difference from Luna none combines reasoning and sampling
changes. Medium reasoning was not tested as a leaf evaluator.

Luna direct/none agreed with itself on all ten repetitions in **7/10 cases**, versus
**4/10** for mini. Both were correct on all ten repetitions in only **4/10 cases**.
Thus three of Luna's perfectly stable cases were consistently wrong against the
benchmark human labels. Luna's yes-class recall was 1/30 direct/none and 10/30
with medium reasoning, versus mini's 25/30.

On identical historical atomic checks, Luna had **19/42 unstable checks**, compared
with mini's **14/42**. The gain in direct-judge repeatability did not carry over to
leaf evaluation. With the new condition plans the counts were 21/46 and 18/46.

Concrete diagnostic observations from the saved responses:

- **C01, cup movement (human yes):** mini direct was yes 10/10; both Luna direct
  settings were partial 10/10. Luna rationales penalized changes to the pot and its
  contents. Repetition did not resolve the scoring-policy disagreement.
- **C03, red sports car (human yes):** Luna's color-only strict-fidelity check was
  no in 6/10 fixed-plan draws, even though all ten presence checks were yes. In one
  saved no response Luna explicitly recognized that the car was red but rejected
  it for changed vehicle identity/viewpoint. This is observable evidence that the
  leaf rationale imported a criterion beyond color; it is not a verified account
  of the model's internal reasoning. Medium direct judging did recover yes 10/10.
- **C02, yellow ball left of cylinder (human yes):** Luna direct/none was no 10/10.
  Medium responses sometimes acknowledged the ball was left of the cylinder but
  penalized its distance and size. The left relation alone does not specify proximity.
- **C10, cat on bus (human partial):** Luna direct/none was partial 10/10 but medium
  was correct only 2/10. More reasoning did not improve every case. The new plan
  checked cat existence, location and size, with no distinct count check.

The visual/concept interpretation remains an unblinded assistant audit, not
independent human concept gold.

### Learned-tree diagnostics

All values below are held-out repeat accuracy; each fold holds out whole tasks or
source categories. Both feature schemas were fixed in the previous pilot. Every
combination had **zero yes-class recall** under leave-task-out evaluation.

| Measurements | Coarse task-out | Detailed task-out | Coarse category-out | Detailed category-out |
|---|---:|---:|---:|---:|
| Mini, existing conditions | 55% | 52% | 61% | 62% |
| Luna, existing conditions | 7% | 22% | 7% | 31% |
| Mini, new Luna conditions | 69% | 58% | 60% | 58% |
| Luna, new Luna conditions | 4% | 30% | 4% | 39% |

The detailed Luna measurements have no observed conflicting feature vectors in
this sample, yet their held-out tree results are poor. Therefore the previous
pilot's exact feature collisions are not the sole explanation: measurement
semantics, sparse supervision, tree capacity and task transfer also need study.
These numbers do not rule out a richer concept library or a better-supported tree.

The saved leave-task-out majority baseline happens to score 0%: holding out a
partial case leaves a three-way training-label tie and the recorded tie-break picks
a different class. Holding out a yes/no case predicts partial. This is a small-sample
LOOCV artifact, not a useful performance floor. For orientation, a fixed always-partial
predictor gets 40/100 on this sample; this descriptive reference was added after
observing the run and was not used to select a model.

**Conclusion:** replacing the model with Luna did not solve the current pipeline's
robustness or human-alignment problem under the tested settings. New Luna conditions
also did not improve either evaluator's fixed aggregation. The immediate priorities
remain precise scoring policies, isolation of each condition, human concept
annotations, and more independent task groups before learning the shared tree.

The direct Luna-minus-mini difference is -24 percentage points, with a descriptive
95% paired task-bootstrap interval of **[-54, +7] points**. Ten selected cases do
not establish a population ranking. The prompts were optimized for GPT-5.4-mini,
so this experiment measures their transfer to Luna; it does not evaluate a fresh
Luna-specific prompt optimization.

## Question and frozen protocol

Does changing the model reduce incorrect and unstable image-edit judgments, and
which part of the existing condition-tree pipeline benefits?

Use the exact ten tasks and images from the [retrospective pilot](assumptions_10_case_pilot.md),
with ten new independent repetitions per case and arm. Calls use the official
OpenAI API. Human scores are used only in local analysis; requests contain the
instruction, the appropriate prompt, and (for evaluation) the source/edited images.

| Arm | Evaluator | Conditions | Reasoning | Temperature |
|---|---|---|---|---|
| mini_direct | GPT-5.4-mini | Selected full judge prompt | none | 0.3 |
| luna_direct | GPT-6-Luna | Same selected full judge prompt | none | 0.3 |
| luna_direct_medium | GPT-6-Luna | Same selected full judge prompt | medium | omitted |
| mini_fixed | GPT-5.4-mini | Frozen historical conditions | none | 0.3 |
| luna_fixed | GPT-6-Luna | Same frozen historical conditions | none | 0.3 |
| mini_regenerated | GPT-5.4-mini | Frozen new Luna conditions | none | 0.3 |
| luna_regenerated | GPT-6-Luna | Same frozen new Luna conditions | none | 0.3 |

The new conditions are one Luna medium-reasoning generation per instruction using
the existing decomposer prompt. No selection by resulting accuracy, manual edits,
human labels, images, or optimized rubric are supplied to that generation. This
arm tests the existing instruction decomposer; it is not the proposed complete
compiler of optimized rubrics. A single plan per task cannot establish repeated
plan stability or isolate decomposer model effects from sampling.

Presence and strict-fidelity checks are separate calls. Deterministic aggregation
is unchanged. Preservation measurements are shared between historical/new condition
arms within each model/repetition, because their prompt and inputs are identical.
There are 1,150 initial calls, followed by up to 1,600 new-condition leaf calls.
Each final-score arm contains 100 judgments, clustered in ten tasks. Calls are
shuffled with a fixed seed within stages. Initial compatibility calls are retained
as the first observations. All completed generations are checkpointed, including
malformed outputs; only transport failures can be retried on resume.

## Analysis

Report repeat accuracy, per-case modes and ties, all-ten-agree cases,
all-ten-correct cases, pairwise disagreement, class recalls, and invalid-output
counts. Bootstrap accuracy differences over ten task groups, not 100 independent
observations. Fit the prior frozen depth-2 trees on condition features, keeping
all repetitions of each task together in leave-task-out and leave-category-out folds.

There are no prompt/rule revisions or hyperparameter searches based on these
outcomes. The subset was previously selected from repair cases, so this diagnostic
does not establish generalization or population accuracy. Stability does not
establish condition accuracy without independent human concept annotations.

## Artifacts

- [Full generated report](../../logs/exps/260923-21:43:52-exps/report.md)
- [Configuration](../../logs/exps/260923-21:43:52-exps/run_config.json)
- [Metrics and paired intervals](../../logs/exps/260923-21:43:52-exps/summary.json)
- [New condition plans](../../logs/exps/260923-21:43:52-exps/plans.json)
- [Runner](../../run/assumptions_model_comparison.py)
- [Offline checks](../../tests/unit/experiments/test_assumptions_model_comparison.py)

The run records returned model IDs, full requests (image references and hashes),
responses, usage and list-price estimates. The $15 threshold checks accumulated
list-price estimates before each new call; in-flight requests can finish after the
threshold. Estimates ignore cache discounts and do not replace provider billing.

```bash
PYTHONPATH=. .venv/bin/python run/assumptions_model_comparison.py \
  --output-dir logs/exps/260923-21:43:52-exps --dry-run
PYTHONPATH=. .venv/bin/python run/assumptions_model_comparison.py \
  --output-dir logs/exps/260923-21:43:52-exps --live
```

The run directory `260923-21:41:01-exps` contains an earlier dry run only. Its first
launch caught a JSON tuple/list comparison issue before any model calls. The
corrected runner uses `260923-21:43:52-exps`; the regression has an offline test.
