# Regularized CaliTree children and compressed parents

**Current priority (October 18, user revision): preserve local accuracy, then
compress and reduce learning cost.** Generalization remains possible through
reusable feature-only predicates; held-out improvement is no longer a gate for
continuing merge work. The active opt-in path is
[local-fit-first v18](calitree_local_compression.md). The v13–v16 studies below are
historical evidence, including their original stricter promotion criteria.

This opt-in research path addresses the October 18 review of the union learner:
many two-source rules, training-equivalent predicates with different meanings,
parents larger than their children, and expensive searches whose selected roots
were identical to direct fitting. Existing v8–v12 experiments and runtimes remain
unchanged. The implementation studied below is `supported_pruning_v14`, building on the
bounded grower and merge scheduler in `regularized_tree_v13`.

## What changed

- The default research vocabulary uses the 62 existing semantic-interpretation
  predicates. The core API also supports global physical summaries and the full
  vocabulary; those alternatives are not silently included in the recorded study.
- Child specialization uses depth at most six, two distinct sources and
  instructions per terminal rule, and the original reference labels. Parent
  profiles grow shallower trees and penalize rule count. Child predictions never
  become parent targets.
- Finite-sample predicate equality only shares score computation. Each predicate
  keeps its identity, and child artifacts retain matching and complementary
  alternatives without claiming they have the same meaning. The two declared
  any/all preferences are selected through training-only validation.
- Fixed-shape pruning minimizes fitting errors plus a per-rule cost. V14 retains
  an alternative for every correctly recognized class set (at most eight states
  per tree node). When possible, it preserves every class represented by at least
  two observed training sources. It does not invent labels or change majority
  labels to satisfy this condition. Unachievable class coverage is disclosed.
- Each accepted parent reduces its immediate children's combined rule count by
  at least 20%. Four seed groups generate six first-level pair proposals; at most
  two distinct policies survive per union, followed by at most twelve root-pair
  proposals. Inference still executes one ordinary portable semantic policy.
- Child shapes, inherited predicate alternatives and fixed generic semantic
  anchors produce parent candidates. The core offers an explicit full-grammar
  challenger mode, but the recorded matched study compares `merge` and `direct`.
- Fits have content-bound caches, measured predicate tests and partition scores,
  and enforced fit budgets. Missing observations and infeasible hierarchies remain
  in every metric denominator. A failed hierarchy is not replaced by direct fitting.

These changes improve the ability to test the research objective. They do not by
themselves establish semantic truth, generalization, or deployment readiness.

## The acceptance change is explicit

`Config(gate_mode="strict")` requires the original v10 acceptance gate **and**
compression. It remains available as a compatibility control.

The recorded v13/v14 experiments use `gate_mode="regularized"`. This replaces the
strictly-above-90% training-accuracy target and fixed per-child error allowance with:

```text
parent fitting errors + penalty × parent rule count
    <= sum(child fitting errors) + penalty × sum(child rule counts)
```

The original full-union, source/instruction support, supported-class collapse and
written-contradiction checks remain. Original gate outcomes are stored alongside
each new decision. A parent can pass this experimental gate and fail the old one;
the experiment never describes that as passing the old >90% requirement.

This is a training objective, not a substitute for validation. It makes an explicit
tradeoff between fitting accuracy and complexity, which is assessed separately.

## Recorded results

The matched v14 study yields the following nested training-validation results:

| Split | Separately tuned direct | Child-guided merged | Complete merged folds |
|---|---:|---:|---:|
| 1 | 17/48 | 23/48 | 4/4 |
| 2 | 25/48 | 27/48 | 4/4 |
| 3 | 30/48 | 33/48 | 4/4 |

Pooled merged correctness is 83/144, versus 72/144 for separately tuned direct
fitting. Direct fitting with exactly the merge-selected profiles scores 70/144;
the paired outcomes are 18 merge-only correct, five direct-only correct, 65 both
correct and 56 both wrong. The improvement therefore is not solely a difference
in the chosen hyperparameter profiles. These slots represent 98 unique sources
with overlapping training cohorts; no independent-replication or significance
claim is made.

The full training candidates compress 14, 14 and 16 initial child rules into 5,
5 and 3 root rules. Every selected intermediate merge also clears the 20% rule
reduction requirement. Complete final hierarchies use 25, 40 and 37 bounded fits
(including child-shape evaluations), compared with 296, 230 and 156 distinct
cold/restricted fit references in v12's corresponding four-group procedures.
These are different complete algorithms, not a matched hardware timing ablation.
Direct fitting remains cheaper than building a hierarchy.

After every policy was frozen, a separate stage evaluated the previously
inspected 36-source development cohort. V14 scores 22/36 (8, 7 and 7 per split),
versus v12's 18/36 (6 per split). The v14 direct control also scores 22/36 with the
same predictions: this cohort supports the simpler learner but does not show an
additional merging advantage. V13 also scores 22/36, despite its weaker nested
validation and one infeasible outer fold. No candidate was refitted or selected
from these transfer outcomes. The fifty remained reserved during that stage; their
subsequent approved frozen evaluation is reported separately below.

See [the compact machine-readable results](experiments/calitree_supported_children_v14.json),
the [portable candidates](../examples/calitree_supported_children_v14), and the full
local experiment directories named in the result artifact. The findings justify
further controlled validation, not unconditional production promotion.

### Additional semantic and construction audit

Fifteen deterministic training-identifier renamings combined with row reversal
reproduced the exact frozen v14 runtime policies. The observed gains do not depend
on those tested naming or ordering choices.

The semantic stress check exposed an unresolved limitation: all three policies
predict Yes for a synthetic, coherent interpretation describing only incidental
change and a missing core endpoint, with identity preserved and no collateral
damage. A two-requirement probe with one completed and one unfulfilled requirement
receives Yes, No and Yes. These probes contain no image evidence or reference
labels; they expose conflicts with the declared feature meanings rather than
establishing additional measured image-judging errors.

The training interpretations have one requirement in 48/48, 47/48 and 47/48 cases.
Any/all quantifiers are identical on a single requirement. These cohorts therefore
provide almost no evidence for selecting their behavior on compound requests.

The same known-negative interpretation flags identify nine fitted training slots
across five distinct sources. Seven flagged Yes predictions agree with the original
released labels and two disagree. Visual/evidence inspection suggests a mixture of
uncertainty represented as a negative, ambiguous actor binding, and degree/scope
judgments. A hard output veto or automatic relabeling is not justified by this
diagnostic. No references, observations or frozen policies were changed.

The remaining work must distinguish generalization of reference-label agreement
from consistency with extracted semantic evidence. More parent search alone cannot
resolve an incorrect or ambiguous evidence record. The approved frozen final-set
evaluation has now completed; its findings follow below.

Reproduce the offline diagnostic with
`python -m run.audit_calitree_semantic_stability_v14 --output-dir logs/exps/261018-v14-semantic-stability-audit`.
See [the complete diagnostic artifact](experiments/calitree_v14_semantic_stability.json).

## Approved frozen final evaluation

After explicit user approval, all nine previously frozen policies were applied to
one shared Luna/compiler-v3 extraction of the reserved fifty sources. No fitting,
policy selection, retries or replacement cases occurred. One observation request
failed (F34); that source remains unresolved in every denominator.

| Training split | V12 merged | V14 direct | V14 merged | V12 / V14 merged rules |
|---|---:|---:|---:|---:|
| 1 | 21/50 | 26/50 | 26/50 | 19 / 5 |
| 2 | 27/50 | 26/50 | 26/50 | 17 / 5 |
| 3 | 18/50 | 25/50 | 25/50 | 17 / 3 |

V14 merged and direct predictions are identical on all fifty sources in each
replication. The smaller learner improves over v12 in two replications and loses
one case in the third. Partial recall remains weak: 29.4%, 23.5% and 29.4% for v14,
versus 35.3%, 58.8% and 29.4% for v12. The final set therefore does not confirm an
additional merging advantage or establish the full generalization objective.
Compression and reduced search work are verified; production promotion is not.

The run used 149 requests, 473,713 reported input tokens and 101,643 reported
completion tokens. Including the failed request's conservative reservation,
118,027 completion tokens were charged against the approved 2,048,000 cap.
Forty-nine observations and forty-nine interpretations validated. The audit
replayed all 450 policy predictions and checked request payloads, budgets, image
bindings, source exclusion and paired scores. These are fifty unique sources,
not 150 independent evaluation examples. Historical project exposure remains
disclosed.

See [the tracked final result](experiments/calitree_frozen_final_v14.json) and
`logs/exps/261018-frozen-final-v14/report.md`. A completion seal covers the evidence
and outputs; a separate consumption record was added under the original M0
reservation without modifying its sealed historical files. Do not tune or select
policies on these now-exposed outcomes and call the resulting score a fresh test.

## Leakage boundaries and comparisons

The runner reads only the three original 48-source **training** files. It has no
live/model-call option and no historical-36 or reserved-fifty evaluation path.

For each split, four outer folds each withhold twelve sources. Three inner folds
select among six fixed profiles. The complete procedure—including children,
vocabulary alternatives, pruning, pair selection and parent fitting—is rebuilt
inside each inner fold. The selected procedure then refits on 36 sources and is
scored on the untouched outer fold. Direct fitting receives the same profiles and
selection process. Full-48 development candidates are selected separately and
exported only after their fitting scope is established.

V14 changes only the pruning algorithm relative to v13. It reuses the same source
cohorts, nested fold assignments, profiles, grower, pairing and gates. All versions
remain separately reproducible. Training cohorts overlap; pooling their 144 slots
does not create 144 independent sources. These are exploratory validation results
after earlier work on these training cohorts, not a fresh confirmatory benchmark.

## Run and audit

```bash
.venv/bin/python -m pytest tests/unit/calitree/test_regularized_tree_v13.py tests/unit/calitree/test_supported_pruning_v14.py -q
.venv/bin/python -m run.calitree_regularized_v13 --output-dir logs/exps/261018-regularized-child-compression-v13
.venv/bin/python -m run.verify_calitree_regularized_v13 --output-dir logs/exps/261018-regularized-child-compression-v13
.venv/bin/python -m run.calitree_supported_pruning_v14 --output-dir logs/exps/261018-supported-child-compression-v14
.venv/bin/python -m run.verify_calitree_supported_pruning_v14 --output-dir logs/exps/261018-supported-child-compression-v14
```

The runners resume completed, content-checked procedure caches. Changed source,
configuration or cached results cause an explicit failure rather than overwriting
a frozen study. Use a new output directory for a changed protocol.

Each study contains `protocol.json`, source/code hashes, nested selections and
predictions, frozen policies, `results.json`, `report.md`, and compressed procedure
caches with complete construction lineages and proposal decisions. V14 also saves
its executable source snapshot. The audit replays metrics, source scopes, alias
bindings, selected procedures, policy exports and every accepted compression gate
without fitting or model calls. V14 additionally replays its pruning frontier;
small exhaustive-enumeration unit tests check the fixed-shape optimum.

## Python API

```python
from critical.core.calibration.semantic_hierarchy.regularized_tree_v13 import Config
from critical.core.calibration.semantic_hierarchy.supported_pruning_v14 import learn
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

# rows: original targets and bound v8 features, with unique source_group and
# instruction fields and four training batch IDs. No evaluation rows here.
result = learn(rows, Config(gate_mode="regularized"), mode="merge")
if result["root"] is not None:
    runtime = result["root"]["runtime"]
    predictions = PortableRuleExecutor(runtime).predict_records(new_feature_records)
```

Regularized merging remains experimental. Do not promote it solely because it
compresses training rules; require comparable or improved out-of-sample behavior,
report failures and per-class recall, and compare against the regularized direct
control. The historical-development and approved final comparisons are now
complete. Further development needs a new confirmation plan; these fifty final
outcomes must not become optimization feedback for a claimed fresh evaluation.

## Training-only follow-ups after the final evaluation

### Macro-F1 pruning: implemented, not promoted

`critical/core/calibration/macro_pruning_v15.py` replaces the fixed-shape pruning
loss with macro-F1 minus the same normalized rule cost. It retains majority labels,
support, class-coverage and written-consistency constraints. A bounded confusion-
count frontier accounts for missing interpretations and is tested against exhaustive
prunings. The frozen grower and parent compression/acceptance gates are unchanged.

The matched diagnostic uses one fixed compact/all profile on the existing training
folds. It is not a comparison with each learner's nested-selected best profile:

| Arm | Correct / 144 slots | Partial correct / 48 slots | Macro-F1 |
|---|---:|---:|---:|
| V14 direct | 69 | 14 | 0.473 |
| V15 direct | 68 | 14 | 0.467 |
| V14 merged | 78 | 15 | 0.530 |
| V15 merged | 73 | 13 | 0.495 |

The change did not improve this diagnostic and remains an experimental negative
result. No historical-development or final cases were read by the experiment.
The independent audit replayed 576 predictions and 719 scoped node/pruning checks.
See [the result artifact](experiments/calitree_macro_pruning_v15.json).

### Paired evidence-contract diagnostic: mixed, not promoted

The user approved a separate twelve-source training diagnostic: five previously
identified conflict sources plus a stable class-balanced completion. Both original
and clarified prompts received fresh observations and interpretations with the
same frozen compiler programs. This used 48 requests and 32,393 completion tokens,
within caps of 48 requests and 589,824 completion tokens. All responses validated;
no references were sent to the model, no cases were retried, and no labels or
policies were changed.

The effective unknown count remained eleven in both arms. Clarified interpretation
reported useful uncertainty/conflicts for N045 and N026, but observations still
disagreed and the N071 actor-binding problem persisted. This does not establish a
reliable quality improvement from the prompt additions. The sample is diagnostic,
failure-selected and has only one fresh response per arm.

Inspection revealed a structural compiler problem: identity/preservation questions
can presuppose the requested result. Examples include a "brown cylinder" identity
check applicable only when a brown cylinder exists, "keys inside the bowl," and an
actor "performing the hand-rubbing action." The intended identity/preservation
measurement should be anchored to the source entity and assessed independently of
whether the edit succeeded. Extra observer prose alone does not enforce this.

Neither prompt arm is promoted. Source-anchored, atomic check construction was
implemented as the opt-in v17 compiler candidate; its 25 offline tests pass and a
five-program preview expands eight support questions into fifteen atomic checks.
Its source proposals remain unverified and cannot be sent to the observer.
Empirical evaluation is deferred under the revised local-fit-first priority.
It preserves explicit authorized transformations/removals and ambiguity without
automatically rewriting labels. No live v17 observations were made.
See [the paired evidence and review](experiments/calitree_evidence_contract_v16.json).
