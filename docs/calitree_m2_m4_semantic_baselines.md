# M2–M4: scalable semantic rules, baselines, and routing

**Date:** October 14, 2026\
**Status:** M2–M4 engineering and development evaluation complete. The resulting judge remains experimental and is **not qualified for deployment**. M5–M9 are not implemented by this work.

## Results first

The implementations pass their arithmetic, source-separation, serialization,
and inference-contract checks. Their predictive performance is still weak.

| Evaluation | Pooled policy | Routed local policies |
|---|---:|---:|
| Four outer source-grouped folds, 48 cases | 16/48, 33.3% | 18/48, 37.5% |
| Already-observed development set, 12 cases | 7/12, 58.3% | 6/12, 50.0% |

| Grouped out-of-fold metric | Pooled | Routed |
|---|---:|---:|
| No recall | 6/16, 37.5% | 7/16, 43.8% |
| Partial recall | 2/16, 12.5% | 2/16, 12.5% |
| Yes recall | 8/16, 50.0% | 9/16, 56.2% |
| Macro-F1 | 0.394 | 0.425 |
| Unresolved | 16/48 | 15/48 |

The routed method has three paired wins and one loss against pooled predictions
on the 48 out-of-fold cases. It loses one case on the separate development
twelve. This does not establish a reliable routing benefit.

For historical context, the cached fixed flat judge on these same 48 cases and
the same requested Sol/high profile scored **30/48, 62.5%**. Its four failed
responses remain in that denominator. This is a verified cached comparison,
not a new randomized flat run. The semantic prototype remains behind it.

**The reserved fifty-case test set was not evaluated.** No merges were performed,
and no experimental policy was made the default pipeline.

## Data and extraction

The study retains M0's 48 training cases and twelve observed development cases,
with the same AURORA editing-model category and released-mean label mapping.
M1's bound-evidence v2 schema, prompts, and Sol/high profile remain unchanged.

The 48 training cases required 96 calls: one instruction compilation and one
SOURCE-first image observation per case. All 48 programs compiled; 47 visual
observations succeeded. `G3C05` had a transport failure and remains Unresolved
throughout every full-denominator evaluation. It was not resampled or replaced.

The twelve existing M1 development records were reused without calls. The
cumulative extraction count is 143: M1's 47 calls across its two versions plus
this collection's 96. Missing returned usage for the failed request is not a
claim that the request was unbilled.

An independent collection audit checked all 96 payload identities, ordered
image hashes, and 366 returned question bindings. Labels and prior model
answers were absent from the extraction payloads. The collection replays
exactly without provider access.

## M2 — Scalable fitting and correctness

Current modules:

- [Typed feature projection](../critical/core/calibration/semantic_hierarchy/features_v2.py)
- [Scalable fitter and evaluator](../critical/core/calibration/semantic_hierarchy/rule_search_v3.py)
- [Numerical/reference verification](../run/verify_semantic_hierarchy_m2.py)

The fitter uses packed `uint64` coverage masks and Python integer bitsets. It
does not allocate a lookup table indexed by all `2**n` subsets of examples.
Candidate and region budgets stay bounded independently of sample count.

The model learns AND/OR clauses over a closed vocabulary of physical
quantifiers and instruction-derived flags. No case IDs, object names, exact
instructions, image hashes, or original batch memberships are prediction
conditions. Batch/source identifiers appear only in provenance and support
accounting.

The first objective is macro-F1, followed by worst-class recall, total correct,
fewer atoms, fewer clauses, and deterministic canonical order. Every fitted
candidate must recognize at least two distinct source examples of every label.
The scorer uses floating point only to shortlist candidates and recomputes the
winning ranks with exact rational arithmetic.

The grammar remains at most three atoms per clause and three clauses per label
boundary, with 128 proposal terms and 2,048 candidate regions per boundary.
Every Yes clause requires the requested outcomes, identity conditions, and
necessary physical interactions to be established. Partial clauses require a
requested change or intermediate witness. Optional preservation compatibility
alone cannot supply progress. This strong Yes guard is an explicit inductive
restriction, not a proof of human-label correctness.

Unknowns are propagated through dependency-aware quantifiers. Prediction is
resolved only when the rule's evidence bounds agree; missing records remain
unresolved. Empty optional constraints can be compatible, but absent check
families cannot masquerade as affirmative witnesses.

### Defects found and corrected during verification

**Negative constraints were being counted as progress.** An unchanged bowl with
no extra copy could activate `any_outcome_direct` through a passed “no duplicate”
condition. The corrected projection distinguishes an affirmative change or a
source-anchored original absence from merely avoiding an unwanted side effect.
Negative-polarity removal remains eligible. The interpretation depends on M1's
typed contracts; it does not parse case-specific nouns or IDs.

**The proposal search could discard a necessary Partial subtype.** On a
synthetic 96-row fixture, a legal three-atom rule classified all 96 rows, but the
old search found only 80/96. Ranking Partial proposals by combined Partial/Yes
coverage caused strong Yes-covering terms to displace a complementary Partial
witness. The corrected search preserves primitive witnesses and treats Yes as
neutral while proposing Partial regions. Final paired scoring still evaluates
all three labels and penalizes a Yes case wrongly left as Partial.

The initial v1 and corrected-projection v2 experiments are preserved. The
current v3 changes proposal construction; it does not change the M1 observations,
the objective, support limits, or routing criteria. Revisions were tested as
development iterations, not disguised as independent confirmations.

### M2 verification evidence

| Rows | Packed words per coverage mask | Fit / restore / reference scoring |
|---|---:|---|
| 12 | 1 | Pass |
| 24 | 1 | Pass |
| 48 | 1 | Pass |
| 96 | 2 | Pass |

The simple synthetic scaling fixtures took roughly 0.06–0.09 seconds and
0.10–0.39 MiB of traced peak allocations in this run. Those measurements are
fixture-specific, not a claim about every search workload.

The complementary-Partial regression now reaches 96/96 with three atoms.
These are synthetic computational tests, not image accuracy measurements.
On the actual full-48 fit, an independent scalar scorer checked **1,131,312
retained region pairs** and matched the selected optimum exactly:
macro-F1 `23732/35061`, worst recall `1/2`, 29/48 correct in sample.
This certifies the bounded search result, not global optimality over every
possible rule.

## M3 — Pooled and local baselines

The feature projection is frozen for each version. Every semantic arm receives
the same authenticated M1 observations. The final full-48 pooled model fits
29/48 locally; that is fitting capacity, not transfer accuracy.

Each original twelve-case group produces two distinct eligible candidate
behaviors, giving eight local candidates. They are selected using only their
own fitting examples. All individual rules, source/batch support counts,
candidate metrics, and rejection diagnostics are saved in the registry and fit
artifacts.

| Candidate | Local fitting correct | Outside-fit correct |
|---|---:|---:|
| G1 candidate 0 | 8/12 | 11/36 |
| G1 candidate 1 | 8/12 | 13/36 |
| G2 candidate 0 | 12/12 | 9/36 |
| G2 candidate 1 | 11/12 | 12/36 |
| G3 candidate 0 | 8/12 | 18/36 |
| G3 candidate 1 | 8/12 | 14/36 |
| G4 candidate 0 | 8/12 | 10/36 |
| G4 candidate 1 | 8/12 | 12/36 |

These outside-fit rows overlap in evaluation sources. They are not eight
independent 36-case tests. A perfect local candidate still transfers poorly.

Four outer folds each hold out one complete original batch. For each fold, all
policy fitting and routing selection use only the other three batches. Inner
leave-one-batch-out pooled predictions supply routing comparators. Reusing a
cached fit is allowed only when its complete source/label/feature fingerprint
matches; a fit containing an outer evaluation source is never reused there.

The final full-training bundle is frozen before scoring the twelve additional
development examples. Those labels are not used to refit the system. All sixty
examples have historical research exposure and the representation itself was
developed on observed data, so these are development estimates, not globally
untouched test results.

## M4 — Actual inference routing

Current modules:

- [Instruction-only router](../critical/core/calibration/semantic_hierarchy/routing_v3.py)
- [Nested evaluation runner](../run/calitree_semantic_baselines_v3.py)
- [Independent audit](../run/audit_semantic_baselines.py)

Scopes use only the compiled requested-outcome kinds, original-instance
requirements, and requirement/dependency structure. The names `requires_*`
refer to requested outcome kinds; they do not enumerate every incidental
preservation check. Check decomposition can affect structural flags, so
paraphrase/redecomposition robustness is not established by this run.

A scope has at most two Boolean conditions. A routing proposal must have at
least six outside-fit validation sources across two originating batches, with
at least two examples per label and at least one correctly recognized example
per label by the expert itself. It must improve macro-F1 against an inner
out-of-fold pooled comparator without class-recall or coverage regression.
Unsupported pooled comparators cannot manufacture apparent expert gain.

At inference:

1. Extract the closed instruction-only scope flags from the authenticated record.
2. Choose the most-specific qualifying scope, then its frozen validation rank.
3. Fall back to the pooled policy for unsupported operation combinations or no scope.
4. Execute only the chosen expert; if it is unresolved, execute the pooled fallback.

The router does not receive a label, dataset category, case ID, or original
batch membership. It does not run every expert and pick a favorable answer.
All expert comparisons and oracle calculations happen offline for evaluation.

The final fitted router has four **selection-qualified** routes. That term
describes the internal development gates, not deployment readiness. In outer
evaluation, 31/48 cases ultimately use pooled fallback; the other 17 use an
expert decision. Six of the 31 first try an expert that abstains. No routing
step adds another image/model call.

An oracle allowed to select a correct answer using the reference label among
the available pooled/local policies scores 29/48. It is only a diagnostic upper
bound and is not an executable label-free routing result.

## Soundness review and practical decision

The independent audit checked 15 distinct fits, 30 policy artifacts, 504
predictions, all four outer folds, 16 inner source separations, and 20 selected
scope gates across the five fitted contexts. It independently recomputed
support counts, reference metrics, actual routes, fallbacks, and oracle bounds.
All checks passed. Ninety-seven scoped tests, including prior M0/M1 protections,
also pass. The collector and all three baseline versions replay without new
model calls.

Passing these checks means the implementation executes and measures its stated
algorithm correctly. It does not mean the learned rules are accurate.

The performance limits are material:

- Partial recall remains only 2/16 out of fold.
- Fifteen routed cases are unresolved; only one is a transport failure.
- Only 11 of the 16 Yes-reference training cases have an established required
  core under this representation. The current Yes guard cannot recognize the
  other five as Yes, regardless of search quality.
- A local 12/12 fit can fall to 9/36 outside its fitting sources.
- The routed method regresses on the supplementary twelve and remains below
  the cached flat judge on the 48-case cohort.

These findings point to representation/guard restrictions and unstable local
boundaries as well as routing limitations. They do not prove that clustering
or merging can repair those limitations. The next research decision should
review those issues before treating M5 merging as an accuracy solution.

The current artifact is explicitly **experimental / not deployment-qualified**.
No existing default pipeline was replaced. The reserved fifty remain available
for a later frozen evaluation, with their approved historical-exposure caveat.

## Reproduction and artifacts

Current results:

- [M2 reference/scaling certificate](../logs/exps/261014-m2-scalable-verification-v3/m2_verification.json)
- [M3/M4 case and metric report](../logs/exps/261014-m2-m4-semantic-baselines-v3/report.md)
- [Independent audit](../logs/exps/261014-m2-m4-semantic-baselines-v3/independent_audit.json)
- [Per-candidate scope proposals](../logs/exps/261014-m2-m4-semantic-baselines-v3/scope_proposals.json)
- [Soundness and deployment assessment](../logs/exps/261014-m2-m4-semantic-baselines-v3/soundness_review.json)
- [Frozen inference bundle](../logs/exps/261014-m2-m4-semantic-baselines-v3/frozen_bundle.json)
- [Requirement-by-requirement completion audit](../logs/exps/261014-m2-m4-semantic-baselines-v3/goal_completion_audit.json)

Offline commands:

```bash
.venv/bin/python -m run.calitree_hierarchy_collect --replay --output-dir logs/exps/261014-m2-m4-bound-training48-v1
.venv/bin/python -m run.calitree_semantic_baselines_v3 --replay --output-dir logs/exps/261014-m2-m4-semantic-baselines-v3
.venv/bin/python -m run.audit_semantic_baselines logs/exps/261014-m2-m4-semantic-baselines-v3
.venv/bin/python -m run.verify_semantic_hierarchy_m2 --output-dir logs/exps/261014-m2-scalable-verification-v3 --actual-data logs/exps/261014-m2-m4-semantic-baselines-v3/data.json
```

The reference benchmark refits synthetic and cached feature records offline;
its timing fields may vary. It makes no model calls. Primary inference replay
uses the frozen artifacts and makes no new fits. V1/v2 experiments and source
snapshots remain available for reconstructing both discovered defects.
