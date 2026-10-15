# M2 v4: remove label vetoes, detect conflicts, and learn semantic groups

**Date:** October 14, 2026. **Status:** implemented and verified as an experimental local-fitting method.

The revised M2 scores **47/48 (97.9%)** on its training cohort, versus the prior
pooled policy's 29/48 (60.4%). It correctly classifies all 47 cases with valid
observations. `G3C05` still has the original transport failure and remains
unresolved in the denominator. No observation was retried or replaced, and no
model calls were made for this experiment.

| Evaluation | Previous pooled v3 | Revised v4 |
|---|---:|---:|
| Fit and score the same training 48 | 29/48 (60.4%) | **47/48 (97.9%)** |
| Four held-out original groups | 16/48 (33.3%) | **23/48 (47.9%)** |
| Freeze full-48 model; supplementary development 12 | 7/12 (58.3%) | **9/12 (75.0%)** |

The training fit is strong; transfer remains weak. The original cached flat
judge scored 30/48 on this cohort. V4's out-of-fold Partial recall is 5/16, and
development Partial recall is only 1/4. No result here establishes robustness or
deployment readiness. The final fifty cases remain unevaluated.

## 1. Mandatory label gates removed

M2 v3 required every Yes clause to contain `all_requested_grounded`, and every
Partial clause to contain an established positive witness. These restrictions
made ten reference labels unreachable, including the missing record.

V4 learns a three-class rule tree with no universal identity, preservation,
positive-witness, or complete-outcome veto. Each predicate can interact with the
other observed properties. Authentication of questions/images and the M1 absence
safeguards remain intact; those protect the meaning of evidence rather than
dictate the final satisfaction label.

Unknown remains an explicit observation state. A learned policy can predict a
label from a pattern containing unknowns, but it does not change those unknowns
into true physical facts. A completely missing record still yields Unresolved.

The training objective prioritizes correct classification, then smaller trees
within the examined alternatives. This supersedes v3's macro-F1-first training
objective for this local-capacity experiment. All three label recalls and
macro-F1 remain reported. There is no requirement that each semantic subgroup
contain every class.

## 2. Richer features and explicit conflict detection

The fixed, label-blind projector reads authenticated M1 checks and exposes
1,530 Boolean predicates. Most are constant on this small cohort; only 123
distinct nontrivial partitions enter the full-training search. The vocabulary
is defined from physical check roles and kinds, not from the training labels:

- Whether at least one, two, or three checks exist in a role/kind family.
- Whether any, a strict majority, or all checks in that family have each desired
  state: true, false, unknown, or not applicable.
- An empty family never satisfies any/majority/all.

All compiled checks in a family participate in these summaries, including
explicit uncertainty and not-applicable states. Direct desired states are kept
separate from M1's dependency-conjoined readout; interactions between identity,
outcomes, preservation, and intermediates are learned by the tree. The raw
questions, dependency graphs, and observations remain available for auditing.

This resolves the old collision between `G1C10` (No, move a sphere in front of
another) and `G2C08` (Partial, move a console and bowl closer). Both previously
had exactly the same 62 aggregate features. The new representation distinguishes
their outcome counts, majority of successful spatial checks, and preservation
families. These distinctions are generic, but their semantic usefulness still
requires validation across other instructions.

Conflict reports operate both globally and within each learned group. They
identify exact feature collisions with different references, retain missing
cases, calculate an information-based accuracy upper bound, and list the closest
cross-label pairs with the features that distinguish them. Mixed terminal leaves
are marked as conflicted and expose their label counts. There are no remaining
exact cross-label collisions in the observed v4 training records.

## 3. Grouping after M1 and local rules learned together

The original G1–G4 memberships no longer determine the deployed local policy.
Training labels help select reusable splits over M1 evidence. Thus grouping is
**supervised and evidence-dependent**, rather than unsupervised clustering or
the earlier instruction-only M4 router. Inference requires no reference label,
case ID, object name, original batch ID, or exact instruction string.

A bounded look-ahead search forms the tree. The current limits are depth six,
24 candidate splits per node, and one million search states. Every terminal
rule must have at least two distinct training sources. Search stops at the first
perfect subtree in its shortlist; it does not claim a globally minimum or
globally optimal tree. The full fit examines 418,896 states without exhausting
its budget and produces 35 nodes / 18 terminal rules. Twelve terminal rules have
only two supporting sources.

The first one or two tree splits define groups, with a six-source minimum for
splitting a group further. Descendant subtrees are the local policies:

| Group condition | Sources | Local fit |
|---|---:|---:|
| At least one directly successful outcome check | 26 | 26/26 |
| No directly successful outcome; all collateral-disappearance desired states satisfied | 12 | 12/12 |
| No directly successful outcome; preceding collateral condition not established | 9 | 9/9 |

The latter condition is a predicate result, not a claim that an object definitely
disappeared. It can include unknown observations. The missing record receives no
group and stays unresolved.

For comparison, fitting the revised learner separately on the old random groups
gives G1=12/12, G2=12/12, G3=10/12, and G4=12/12: 46/48 combined in sample.
Regrouping and sharing the training cohort recover the additional observed
`G3C08` miss. These are fitting diagnostics, not label-free routing accuracies
for the old groups.

## Inference

The two M1 model stages remain unchanged: compile the instruction once, then
observe SOURCE and EDITED once. V4 derives the closed feature record, follows
the learned semantic group path, and executes the local subtree in code. The
result includes the label, group, branch trace, leaf support, and training label
distribution. There is no new model call for grouping or calibration.

## Soundness and remaining limitations

Near-perfect fitting was obtained by expanding expressive capacity and allowing
the classifier to learn label correlations that v3 prohibited. That solves the
local-capacity problem, but does not prove the correlations are reliable semantic
rules. In particular:

- A branch predicts Yes for three training cases without a directly established
  positive outcome: the inverted bottle, pet-store background, and fully closed
  jacket. It uses collateral state, intermediate-state patterns, and preservation
  check counts. This is an empirical boundary, not verification that the requested
  edit physically succeeded.
- Counts and majority features can depend on how the compiler decomposes an
  instruction. Adding a redundant check can change them. Paraphrase and repeated
  extraction robustness have not been measured.
- Two-source leaf support prevents literal singleton rules but is weak evidence
  for transfer. Generic feature names do not rule out combination-level overfit.
- The 48 cases informed feature and search design. Outer folds exclude each
  held-out group's labels from its fitted model, but this remains a development
  estimate after architecture exploration, not a globally untouched test.
- The development set is historically observed; its improved aggregate score
  hides three remaining Partial errors: H02, H05, and H11.

The full-48 artifact was frozen before supplementary development scoring. The
four outer models independently refit grouping and local rules on 36 sources.
V4 has not replaced the default pipeline or implemented M5 policy merging.

## Verification and reproduction

114 scoped tests pass, including 17 v4 tests and 97 M0–M4/legacy tests. The tests
cover removal of the old gates, polarity and empty-family behavior, distinctions
between unknown and false, exact collisions, source support, row/batch invariance,
no runtime label fields, tamper rejection, bounded search, and 12/24/48/96-row
fit/restore. The scaling fixtures are computational tests, not image accuracy.

An independent audit checks 90,270 projected feature values, all nine fitted
policies, 91 supported leaves, 156 predictions, group membership, metrics, and
the four outer source separations. Frozen replay makes zero new fits or calls.
All 127 sealed v3 completion artifacts remain unchanged.

```bash
.venv/bin/python -m run.calitree_m2_conflict_v4 --output-dir logs/exps/261014-m2-conflict-regrouping-v4 --replay
.venv/bin/python -m run.audit_calitree_m2_v4 logs/exps/261014-m2-conflict-regrouping-v4
.venv/bin/python -m pytest tests/unit/calitree/test_semantic_hierarchy_m2_v4.py -q
```

- [Frozen policy](../logs/exps/261014-m2-conflict-regrouping-v4/pooled_policy.json)
- [Readable rules](../logs/exps/261014-m2-conflict-regrouping-v4/pooled_policy.txt)
- [All results and conflict reports](../logs/exps/261014-m2-conflict-regrouping-v4/results.json)
- [Independent audit](../logs/exps/261014-m2-conflict-regrouping-v4/independent_audit.json)
- [Projector](../critical/core/calibration/semantic_hierarchy/features_v4.py)
- [Learner and inference](../critical/core/calibration/semantic_hierarchy/conflict_tree_v4.py)
