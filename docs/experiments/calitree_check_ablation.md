# Paired visual-check experiment — 2026-10-06

**This pilot did not demonstrate a stability benefit from separating checks. It is inconclusive about the broader hypothesis.** Only three of twelve cases obtained an approved rule bank, and those banks used fairly broad progress/completeness questions. On those three cases, separated execution varied more and had the same reference agreement, at three times the execution-call count.

## What was compared

The combined arm returned all visual fact observations and the outcome judgment in one image call. The separated arm evaluated each fact in an isolated image call, then used a text-only fulfillment call to apply the exact same decision criteria. Each arm ran five fresh repeats per case with alternating order. The original label-free seeds and images were reused; reference labels were supplied only to reporting. This tests an execution format, not a new optimizer search.

## Paired results on the three eligible cases

| Metric | Combined | Separated |
|---|---:|---:|
| Independent cases | 3 | 3 |
| Repeated decisions | 15 | 15 |
| Pairwise label inconsistency (lower is better) | 13.3% | 36.7% |
| Disagreement among resolved pairs only | 0.0% | 30.0% |
| Atomic observation inconsistency | 13.3% | 20.0% |
| Agreement with reference labels | 4/15 (26.7%) | 4/15 (26.7%) |
| Resolved coverage | 14/15 (93.3%) | 14/15 (93.3%) |
| Five-of-five resolved-consistent cases | 2/3 | 1/3 |
| Five-of-five matching cases | 0/3 | 0/3 |
| Execution calls | 15 | 45 |
| Measured input tokens | 19,900 | 38,791 |
| Measured completion tokens | 1,508 | 1,928 |

Pairwise inconsistency is calculated over the ten unordered pairs of draws within each case, then averaged across cases. Any pair containing an unresolved draw counts as inconsistent; unresolved draws also count as incorrect. Atomic inconsistency uses the same rule per fact. These are consistency metrics, not evidence of correct reasoning. The separated-minus-combined difference was +23.3 percentage points; the exploratory exact case-level sign-flip diagnostic gave p = 0.5. Three selected cases are far too few to establish a general ranking.

| Case | Reference | Combined labels | Separated labels |
|---|---|---|---|
| Pencil drawing | partial | yes, yes, yes, yes, yes | yes, partial, yes, yes, yes |
| Basketball background | yes | yes, yes, yes, yes, unresolved | yes, yes, yes, partial, unresolved |
| Chalk drawing | partial | yes, yes, yes, yes, yes | yes, yes, yes, yes, yes |

The pencil case illustrates why stability and correctness must be measured separately: the combined answer was consistently wrong, while the one changed separated answer matched the reference. The chalk case was consistently wrong in both formats. The two unresolved basketball draws came from one SSL transport failure in each arm, not model abstention. They were retained without retries. Even among resolved pairs, separation did not improve consistency in this sample.

## Preparation was the main bottleneck

The initial banks all failed preparation. Most were rejected by the model audit for weakening complete/partial/absent distinctions, introducing extra requirements, or requiring visual evidence that no fact recorded. The helmet bank initially contained only one fact, violating the planned two-to-three-fact comparison. Before any live evaluation, one label-blind semantic repair per case was added within the original budget. Three repaired banks passed; nine remained audit-rejected. All rejections and exact proposed banks are saved. These audit judgments are model opinions, not established ground truth.

The three surviving cases comprise one yes and two partial targets; no no-target case survived. They are therefore neither a balanced subset nor evidence about the other nine cases. The machine report also retains full-cohort metrics with those nine cases unresolved: agreement 6.7% and coverage 23.3% for both arms. Those numbers mostly measure preparation failure and should not be interpreted as the execution-format comparison. Its failed-draw counters include these unexecuted preparation failures; the actual HTTP failure count is two.

The surviving facts were coarse. For chalk, F1 asked whether any chalk treatment was visible, and F2 asked whether the image as a whole was rendered as chalk. They were not separate low-level checks for grain, outlines, and remaining photographic detail. F2 still requires a holistic judgment, so this experiment only partially represents the proposed fine-grained decomposition. Passing the current model audit did not guarantee the desired granularity.

## Interpretation for CaliTree

The result does not justify assuming that more calls alone improve stability. Explicit nodes did make the source of variation observable: in the pencil and basketball cases, F1 remained positive while F2 changed. That trace visibility is useful for targeting repairs, even without an accuracy improvement.

A stronger next experiment should freeze a reviewed set of concrete visual predicates, ensure fulfillment cannot hide an additional holistic image judgment, and test more cases before optimizing the rule set. The atomicity audit needs clearer criteria than one question per node: a single question can still bundle several visual decisions. Keep repeat consistency, reference agreement, semantic coverage, and cost as separate measures.

## Reproducibility and accounting

- GPT-6 Luna throughout, temperature zero and supported reasoning none; all successful responses reported `gpt-6-luna`. No substitution.
- Approved ceiling: 400 calls and 409,600 completion tokens across all attempts. Actual cumulative use: **107 calls and 16,670 charged completion tokens**, including 47 preparation calls and both failed calls. Measured completions were 14,622 tokens.
- The first attempt exposed a parser defect: empty explanatory reason strings were incorrectly rejected. Fixed that metadata validation and reused exact saved responses. No compilation was repeated to correct this defect.
- The preparation repair amendment occurred before any evaluation output. It used only instructions, images and label-blind audit diagnostics. No final outcome triggered another repair.
- Earlier runs `261006-check-ablation-v1` and `v2` remain intact. `v3` carries their exact slots and budget forward, so copied artifacts do not represent additional calls. Every failed or interrupted slot remains durable.
- Final full offline suite: **1,126 passed, 23 skipped**. Fourteen experiment tests cover paired criteria, label isolation, negative evidence, unknown propagation, malformed banks, rejected audits, bounded semantic repair, fresh repeats, case-level metrics, interrupted slots and zero-call resume.
- Replayed all **30 executed draws** from durable responses with a provider factory that rejects new calls; final observations and predictions matched. Completed-run resume produced identical results with unchanged budget and zero new calls. Source snapshots, image hashes, returned model identities and call caps were verified.

```sh
.venv/bin/python -m run.calitree_check_ablation --report --output-dir logs/exps/261006-check-ablation-v3
.venv/bin/python -m logs.exps.261006-check-ablation-v3.verify_run
```

Artifacts: [protocol](../calitree_check_ablation.md), [manifest](../../logs/exps/261006-check-ablation-v3/manifest.json), [eligible-case summary](../../logs/exps/261006-check-ablation-v3/eligible_summary.json), [verified audit](../../logs/exps/261006-check-ablation-v3/audit.json), [per-case CSV](../../logs/exps/261006-check-ablation-v3/per_case.csv), [complete results](../../logs/exps/261006-check-ablation-v3/results.json).
