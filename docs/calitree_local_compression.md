# Local accuracy first: CaliTree child optimization and merging

The user clarified the objective on October 18: generalization needs room to
happen, while local accuracy must be preserved. This supersedes the earlier
requirement to establish a held-out gain before continuing merge work.

V18 makes local accuracy a hard constraint. Every proposed parent must match or
improve each immediate child's correct count on that child's original training
scope, and retain the optimized original descendants' correct counts. It must
also remove at least one terminal rule. There is no error-versus-rules penalty,
no cross-validation promotion threshold, and no new model call.

## Current result

The experiment starts from the highest-fit existing v12 children in each original
four-group partition. It uses all 894 declared reusable features, the same cached
evidence, and the original human reference targets.

| Training split | Original local correct | Retained forest local correct | Original rules | Retained rules | Trees remaining |
|---|---:|---:|---:|---:|---:|
| 1 | 48/48 | 48/48 | 22 | 21 | 4 |
| 2 | 47/48 | 48/48 | 18 | 15 | 3 |
| 3 | 46/48 | 48/48 | 19 | 16 | 2 |

All seven accepted merge proposals pass every local retention check. Some are
alternative pairs and do not belong to the selected forest. Split 1 improves one
child by one rule without changing fit. The selected forests in splits 2 and 3
contain one and two accepted pair merges, respectively. Rule reductions are
4.5%, 16.7%, and 15.8% relative to the original separate children.

These are **scope-local training scores**: each retained tree is measured on its
own descendant cases. No complete merged root was found, and there is no hidden
case-ID router that turns a forest into a single predictor. Each individual tree
is executable on unseen feature records, but combining these forests for an
unknown incoming case remains a separate routing/merging question.

Split 1 has a conclusive obstruction: N003 and N011 have identical feature
records with different reference labels, while their children are both correct.
One deterministic feature-only parent cannot preserve all 48 answers. Split 2
contains the same feature conflict but originally allows one error; equality
alone does not rule out its original floors. Split 3 has no exact feature
conflict. Bounded search failures in the latter splits do not prove that a
qualifying root is impossible.

## How the optimizer works

1. Reuse the existing fitted children and exact-union cached policies. Verify
   evidence, original targets, scope and runtime before considering a candidate.
2. Search supported majority-label trees while retaining alternative vectors of
   errors across child scopes. A global error total cannot hide one child's loss.
3. Among feasible trees, minimize total training errors first and terminal rules
   second. A smaller imperfect incumbent cannot reduce the rule budget so far
   that it blocks a higher-accuracy candidate.
4. Optimize four children, try six pairs and at most three root partitions.
   Preserve the best disjoint forest if no complete parent passes.

Search uses depth at most six, sixteen shortlisted partitions per state, at most
20,000 memo states, 200,000 combinations and 256 frontier entries per fit. Five
of the 32 searches hit a declared bound; completed feasible incumbents remain
available. The method makes no global tree-optimality claim. The three runs used
13,694, 55,321 and 116,751 states and roughly 0.9, 2.6 and 6.3 seconds locally.
These are incremental timings that reuse historical policies, not a controlled
speed comparison with a cold learner.

To preserve room for generalization, branch conditions come only from the closed
portable evidence vocabulary. There are no source IDs, image names, reference
labels, or memorized lookup tables in the runtime. Every leaf has at least two
distinct sources and instructions; explicit contradictory Yes paths remain
excluded. Training-equivalent predicate names remain recorded as alternatives,
without claiming semantic equivalence. These are structural properties, not a
claim of measured generalization.

Missing evidence remains in local accuracy checks. The new search currently
defers when evidence or interpretation is incomplete and keeps eligible existing
policies; it does not drop missing cases or treat unknowns as negative evidence.
The current three training records have complete cached evidence.

## Reproduce and inspect

```bash
.venv/bin/python -m run.calitree_local_compression_v18 --output-dir logs/exps/my-local-compression-v18
.venv/bin/python -m run.verify_calitree_local_compression_v18 --output-dir logs/exps/my-local-compression-v18
.venv/bin/python -m pytest tests/unit/calitree/test_local_compression_v18.py -q
```

The recorded run is `logs/exps/261018-local-compression-v18-r1`. The initial
`261018-local-compression-v18` run was superseded before sealing by an incumbent
budget fix; its three reported scores happen to be identical. The audited run
replayed 312 training predictions, checked 19 nodes and all seven accepted
merges, and verified original targets, complete scope coverage and portable
runtime serialization. Fourteen tests include exhaustive small-tree comparisons,
aggregate-versus-local retention, infeasible conflicts, missing evidence, bounded
search fallback, cache scope and identifier/order invariance.

See the [compact results](experiments/calitree_local_compression_v18.json) and
[portable trees](../examples/calitree_local_compression_v18/README.md). No held-out
or final-set predictions were made. Prior studies remain frozen.

## Criterion for continuing merging

The current evidence is sufficient to continue: a merge or child optimization
preserves local accuracy, saves rules, and uses reusable predicates within a
bounded cost. A held-out gain is useful diagnostic evidence but is not required
for this milestone. Next merge work can target a larger supported parent in
split 3 while preserving the two accurate pair trees as fallbacks. Representation
changes for the split 1 equality conflict are a separate question; relaxing the
local fit gate would conceal that obstruction.
