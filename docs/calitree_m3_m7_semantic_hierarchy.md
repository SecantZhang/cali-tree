# CaliTree M3–M7: portable local policies, routing, and guarded merging

**Date:** October 15, 2026. **Status:** implemented and evaluated offline against
the latest reviewed M2 v8 representation. No merge was accepted on AURORA.
The resulting frozen system retains M2's **44/48 (91.7%)** local accuracy.

This completes the experimental M3–M7 components, including their negative
outcome. It does not establish a useful learned hierarchy, statistical transfer,
or production qualification. M8 and M9 remain separate work.

## Result

| Frozen arm | Local training, 48 sources | Grouped development, 48 sources | Separate development, 12 sources |
|---|---:|---:|---:|
| Reviewed pooled M2 | 44/48 | 24/48 | 9/12 |
| Guarded routed locals | 44/48 | 24/48 | 9/12 |
| M7 selected system | 44/48 | 24/48 | 9/12 |

The identical scores are intentional: no candidate justified replacing the pooled
fallback. The final bundle contains its fourteen rules, no specialist routes,
and no training cases. Training recalls remain No 16/16, Partial 15/16, and Yes
13/16. The original missing observation stays unresolved in the denominator.

The grouped scores use four source-disjoint folds, stratified within each
original training batch and reference class. Each outer training set has 36
sources. Expert fitting, inner pooled comparison, scope selection, and the
whole-router guard exclude the scored outer sources. These estimates remain
development evidence: the representation and these historical cases have
already informed this project. The separate twelve also have historical
exposure. The reserved fifty were not evaluated.

## What each milestone now does

| Milestone | Implementation and inspected output | Dependency gate |
|---|---|---|
| M3 | Pinned pooled M2; two fit profiles per batch; eight saved candidates, six distinct deployed rule trees; local and out-of-source tables | Same authenticated cached features; all candidate class/support failures retained |
| M4 | Closed instruction-only scope grammar, explicit overlap priority, pooled fallback, nested evaluation, joint router selection | Restorable label-blind routes; whole-system fitting accuracy, macro-F1, class recalls, and coverage cannot regress against pooled |
| M5 | Predicate/role overlap, mutual transfer matrices, shared-error and complementary-error counts, deterministic pair ranking | Thirteen eligible pairs are explainable using training-only structure and behavior; similarity never accepts a merge |
| M6 | Full deduplicated child union, original labels, child-condition warm starts, common-grammar parent search, before/after actual routing | M0 class/scope/coverage gates plus the user's above-90% complete-system local fitting floor |
| M7 | Iteration across accepted parents/remaining candidates, bounded depth/proposals, provenance graph, complete rejection history, frozen export | No eligible untested pair remains; bundle restore reproduces decisions and traces |

M3 local fitting scores range from 10/12 to 12/12. Same-batch source-excluding
scores are much lower: G1 6/12, G2 6/12, G3 4/12, G4 7/12 for both retained
profiles in each batch. These are separately recorded, not presented as the
local fitting numbers.

## Routing failure found and fixed before merging

The preserved v9.1 experiment qualified scopes one at a time against
out-of-source pooled comparators, then combined the preferred routes. The
result fell to 32/48 locally and 22/48 in grouped development, compared with
44/48 and 24/48 for pooled. Separate development fell from 9/12 to 7/12.

This was not a stable M4 prerequisite. V9.2 evaluates bounded subsets of the
qualified routes as a complete system on fitting data, including their actual
overlap order and fallback. Its selection runs inside each outer training fold.
The empty router is an explicit candidate and wins in every context.

An additional diagnostic examined all 26 individually qualified alternative
scopes. Across all 3,240 combinations retaining at most one scope per expert,
with fixed validation-priority ordering, only the empty router preserved the
pooled fitting metrics. This does not rule out other routing grammars, expert
learners, or arbitrary route permutations. It shows that retaining a lower-ranked
scope was not enough within this inspected selection space.

## How parent learning and promotion work

For a proposed pair, every original descendant source is pooled, including
misclassifications and failed extraction records. Source duplicates are removed;
their original labels are never replaced by a child vote. The parent receives
both child conditions as warm candidates and searches the common M2 vocabulary.

Every shared terminal rule must contain at least two sources, two instruction
texts, and two originating batches. Cross-batch support constrains the search
itself. Case IDs, exact instructions, object names, coordinates, raw check
counts, majority thresholds, and observed-signature routing remain unavailable
as executable conditions.

Parent applicability is the union of measurable child instruction scopes. The
same procedure runs separately inside each outer fold. A parent from previously
unpromoted candidates is a new promotion proposal: it is compared against the
actual pooled/routed system, rather than an imaginary child ensemble.

Promotion requires the sealed M0 rules: nondecreasing macro-F1 and Partial
recall, at most one additional total error, protected No/Yes and descendant
scope counts, no coverage regression, sufficient validation denominators, and
either improvement or lossless active-complexity reduction. The complete
full-fit system must also remain above 90%. Unsupported folds cannot promote.

All thirteen proposals were rejected. Parent union fits ranged from 22/24 to
24/24, but the resulting full-system training scores were only 32–37/48 and
their grouped scores were 18–23/48 versus the current 24/48. Every proposal
therefore failed both the local fitting floor and macro-F1 gate. Rejection was
not caused solely by prioritizing held-out accuracy over the user's definition
of generalizability.

| Proposal | Original batches | Union fit | Parent rules | Complete-system fit | Grouped score |
|---|---|---:|---:|---:|---:|
| 1 | G1 + G4 | 24/24 | 10 | 37/48 | 19/48 |
| 2 | G1 + G2 | 23/24 | 8 | 33/48 | 21/48 |
| 3 | G1 + G4 | 24/24 | 10 | 37/48 | 19/48 |
| 4 | G2 + G3 | 22/24 | 7 | 32/48 | 23/48 |
| 5 | G1 + G2 | 23/24 | 8 | 33/48 | 21/48 |
| 6 | G3 + G4 | 22/24 | 8 | 34/48 | 18/48 |
| 7 | G1 + G4 | 24/24 | 10 | 37/48 | 19/48 |
| 8 | G1 + G3 | 23/24 | 8 | 36/48 | 19/48 |
| 9 | G3 + G4 | 22/24 | 8 | 34/48 | 18/48 |
| 10 | G1 + G3 | 23/24 | 8 | 36/48 | 19/48 |
| 11 | G2 + G4 | 24/24 | 10 | 33/48 | 21/48 |
| 12 | G2 + G4 | 24/24 | 10 | 33/48 | 21/48 |
| 13 | G1 + G4 | 24/24 | 10 | 37/48 | 19/48 |

Repeated batch pairs use different retained local-policy alternatives. Some
produce identical parent rule trees; all attempts and their initialization
identities remain recorded. The study used 105 unique cached fits: 64 baseline
fits and 41 additional shared-parent fits after exact cache reuse. There were
zero new model calls.

The result points to weak specialization/applicability from heterogeneous small
batches. A parent can explain its 24 fitting examples while its broad reusable
scope also serves cases it handles poorly. Semantic wording and cross-batch
support do not by themselves solve that routing problem. The current code
preserves M2 rather than promoting those local successes globally.

## Inference and export

The [deployment-only package](../examples/calitree_semantic_hierarchy_v9/manifest.json)
contains the frozen hierarchy JSON, exact compiler/observer/interpretation
prompts, compiler schema, contracts, model profile, and file hashes. It contains
no fitting rows, object identities, human references, or support examples.

A fresh image pair still uses the existing three upstream model passes with
GPT-6.1 Sol/high: compile the instruction, observe those exact physical checks
once, and interpret the evidence once. Instruction-only routing and the final
rule execution add no model call. The M3–M7 study used existing cached outputs.

```python
from critical.core.calibration.semantic_hierarchy.hierarchy_export_v9 import load

judge = load("examples/calitree_semantic_hierarchy_v9")
decision = judge.predict_bound(program, observation, image_pair_ref, interpretation)
```

The frozen CLI accepts exactly those four evidence fields and rejects reference
labels or fitting metadata:

```bash
.venv/bin/python -m run.calitree_semantic_hierarchy_predict \
  --bundle examples/calitree_semantic_hierarchy_v9 --evidence /path/to/bound_evidence.json
```

## Verification and reproduction

The final CaliTree unit run passes **954 tests**, with 23 skipped. The fifteen
new hierarchy tests cover the additions described below. The frozen-evidence
CLI also executes an actual development record from the exported package.

The implementation tests accepted improvements, rejected Partial and scope
regressions, insufficient denominators, preservation of failed descendants,
shared-mistake accounting, scope/schema tampering, cycles, no inference fitting,
and package integrity. A synthetic fixture performs repeated accepted merges
into a multilevel hierarchy and replays it exactly. It is a logical engineering
test, not additional human-labeled AURORA evidence.

The independent audits reconstruct source exclusions, raw M1/M2 feature
bindings, class metrics, transfer matrices, all thirteen parent lineages,
before/after routed predictions, and the terminal search condition. Across
59 observed sources, 515 exact check-order/identifier/duplication variants
produce zero feature, scope, prediction, or trace changes. The final system
and seven distinct proposed parent policies pass 4,120 decision/trace
comparisons. Interpretations are held fixed; model repetition and natural
language paraphrases remain untested.

Use the local cached M0/M1/M2 artifacts for training replay. The deployment
package can execute without those training logs.

```bash
.venv/bin/python -m run.calitree_semantic_hierarchy --stage all --replay \
  --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m run.audit_calitree_semantic_hierarchy --stage hierarchy \
  --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m run.audit_calitree_semantic_hierarchy --stage routes \
  --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m run.audit_calitree_hierarchy_invariance \
  --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m pytest tests/unit/calitree -q
```

Primary saved artifacts are `protocol.json`, `parent_protocol.json`,
`baseline/local_candidate_oof.json`, `proposals/initial.json`,
`hierarchy/history.json`, `hierarchy/node_registry.json`,
`hierarchy/provenance_graph.json`, `hierarchy/frozen_bundle.json`,
`hierarchy/results.json`, and their audits.
The initial v9.1 routing failure and preparation-only v9 artifacts are retained.
No historical M2 evidence or final-set reservation was overwritten.

M8 would be the separately frozen final comparison. It was not run or used to
repair this study. M9 production integration is also outside this milestone
range; the new implementation remains opt-in.

