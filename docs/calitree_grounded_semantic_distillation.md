# Instruction-grounded semantic calibration

The v16 semantic student matches the previous learned policy's local result:
**42/48 (87.5%)**, with group results **10/12, 12/12, 10/12, 10/12**. Unlike v8/v9,
the runtime representation contains concrete physical predicates rather than
renamed quality grades. Teacher-only distillation and optional local-label
refinement both reach the same accuracy. The primary student fits teacher
predictions, not the original dataset labels.

This is teacher-guided semantic re-induction, not an exact algebraic rewrite.
Semantic representation design used exploratory local error analysis; the
overall study is not held-out or gold-blind. Full per-case and comparison results
are in `logs/exps/261014-instruction-semantic-distillation-v16/report.md`.

## Runtime representation

Three independent label-blind stages use the same Sol/high profile:

1. `ObservableFactExtractor` answers thirty physical questions from cached prose:
   source-instance persistence, destination counterpart, relative position,
   extra instances, residual attributes, orientation landmarks, closure gaps,
   disconnected material, transfer contents, grasp/contact, style structure,
   setting cues and unrelated object changes.
2. `PostconditionCompiler` sees only the instruction and predicate bank. It binds
   actual target/reference physical tests and records required-present,
   required-absent, supporting, identity and collateral roles.
3. `IntermediateFactExtractor` checks eight concrete intermediate configurations,
   such as reaching, an object-like form at a hand, vessel tilt and closure-edge
   motion. It does not output a progress grade or desired verdict.

`instruction_role_facts.compile_record` combines these into Boolean proof-status
facts and keeps the relevant primitive facts. A proof-status false means a
witness is not established, not that a hidden physical event certainly failed.
Raw unknowns remain unknown. This distinction is explicit in the trace data.

The instruction-bound program is inspectable. For a pickup request, it asks
whether the hand coherently grips/supports the object and whether the object
left its original position; it does not ask whether overall progress is "good".
For recoloring, it asks whether the requested property is visible and whether a
contrary original property remains. The predicate names are generic; actual
entities are bound from the instruction, not matched against a case lookup.

## Learned rule example

G2's actual rule is:

- Yes when all instruction-bound physical postconditions are established and
  relocation duplication is not observed.
- Otherwise Partial when at least one required physical witness is established.
- Otherwise No, with unresolved output when the uncertainty bounds disagree.

The duplication predicate activates only when the instruction compiler selects
original-instance relocation witnesses. The same count increase is permitted in
an addition. Appearance drift is separated from an unchanged source instance or
failed counterpart, and a descriptive identification attribute is separated
from a requested outcome attribute. Tests verify those role counterfactuals.

## Learning

`instruction_semantic_rules.ObservableDNFCalibrator` subclasses `Calibrator`.
It learns bounded disjunctions of physical witness conjunctions, using parent
policy predictions as teacher targets and the parent's selected concepts as
search priorities. The optional `human_refined` arm fits the original local
labels separately. Evaluation always includes all twelve cases in each group.

Each boundary has at most three clauses and each clause at most three factual
tests. Every clause has two definite distinct source cases. Every Yes clause
contains a requested physical witness; Partial requires requested or supporting
physical evidence. Predicate polarity and a fixed role-aware priority prevent
unqualified appearance warnings or incidental conditions from replacing equally
covering requested constraints. Runtime execution contains no weights, numerical
quality cuts, exact instructions, object names, hashes or reference labels.

Unknowns are conservatively evaluated at both evidence bounds. Missing records
remain unresolved. The final student has 42/48 coverage versus the teacher's
44/48; both score 42/48. The student corrects the teacher's bottle and pouring
errors but abstains on the pet-store and jacket cases. This is a coverage tradeoff,
not identical predictions or 48/48 accuracy. Macro-F1 rises .913 → .933.

## Reproduce

These commands make zero new API calls:

```bash
.venv/bin/python -m run.calitree_observable_facts --replay --output-dir logs/exps/261014-observable-semantic-facts-v10
.venv/bin/python -m run.calitree_postconditions --replay --output-dir logs/exps/261014-semantic-postconditions-v12
.venv/bin/python -m run.calitree_intermediate_facts --replay --output-dir logs/exps/261014-physical-intermediates-v13
.venv/bin/python -m run.calitree_instruction_distillation --output-dir logs/exps/261014-instruction-semantic-distillation-v16
.venv/bin/python -m run.report_calitree_instruction_distillation --output-dir logs/exps/261014-instruction-semantic-distillation-v16
```

Raw extraction, instruction binding and intermediate extraction used 44 text
calls each (132 total), zero new image calls, and about $2.43 in returned-token
standard uncached cost estimates. All source images, labels, cases and earlier
experiments remain unchanged. Four original source failures remain in every
denominator. Source snapshots and raw histories preserve failed and superseded
search variants as well as successful versions.

Independent auditing checks all 132 payloads, required witness roles, actual
teacher-only training targets, every conjunction's source support and exact
predictions/metrics. Unit tests cover predicate semantics, unknown/NA behavior,
postcondition bindings, exact loss arithmetic, serialization, required-witness
guards and instruction-role counterfactuals. The bounded search does not claim
global optimality; the local fit does not establish generalization, causal
correctness of every chosen condition, or repeated-model robustness. The physical
extractor and instruction compiler can still be wrong. Keep the method opt-in
until its frozen rules are tested on fresh examples.

## Frozen transfer test: 2026-10-14

The four `teacher_distilled` policies were copied and hashed before live calls,
then applied unchanged to one new source-disjoint twelve-case set (four per
class, all eight task categories). All 48 fitting sources and 144 earlier
excluded sources were excluded. The existing extraction prompts, Sol/high
model, source-first presentation, and role compiler were unchanged. Each policy
received the exact same physical evidence; no fitting, routing, or ensemble was
performed.

| Policy | Original local correct | New correct | No recall | Partial recall | Yes recall |
|---|---:|---:|---:|---:|---:|
| G1 | 10/12 | 6/12 (50.0%) | 50% | 0% | 100% |
| G2 | 12/12 | 9/12 (75.0%) | 100% | 25% | 100% |
| G3 | 10/12 | 9/12 (75.0%) | 100% | 25% | 100% |
| G4 | 10/12 | 8/12 (66.7%) | 50% | 50% | 100% |

All 48 calls succeeded (12 image observations, 36 text calls); every policy
resolved all twelve cases. There are twelve independent examples, not 48:
the four policies are scored on the same images. No new-case flat baseline was
run. Each label has only four examples, and repeated-call robustness is untested.
The existing half-point mapping of released mean human scores is unchanged.

The local success does not transfer reliably to Partial. Some failures reflect
rules ignoring available collateral evidence; others reflect insufficient
intermediate-state coverage or inconsistent bindings between independently
compiled tests and extracted facts. The frozen policies were not repaired after
observing these results. See the [case-level report](../logs/exps/261014-frozen-semantic-transfer12-v1/report.md)
and [failure analysis](../logs/exps/261014-frozen-semantic-transfer12-v1/failure_analysis.md).

Reproduce without new API calls:

```bash
.venv/bin/python -m run.calitree_semantic_transfer --replay --output-dir logs/exps/261014-frozen-semantic-transfer12-v1
.venv/bin/python -m run.audit_calitree_semantic_transfer logs/exps/261014-frozen-semantic-transfer12-v1
```

The independent auditor checks all 48 predictions, class metrics, confusion
counts, four original policy hashes, 24 image hashes, and pixel-level source
exclusion. The runner's payload audit checks that labels and policies never
enter model requests. Exact cached replay passes with zero new API calls.
