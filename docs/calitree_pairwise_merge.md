# Pairwise merge development with routing preservation

The initial pairwise development phase is implemented and audited. One learned
parent is accepted in split 2. It reduces the routed expert bank from **4 to 3**
experts and **22 to 19** terminal rules, while every recorded accept/defer decision
and final prediction remains unchanged. Splits 1 and 3 retain their existing
experts because no candidate passes all constraints.

| Split | Experts before → after | Terminal rules before → after | Stored Boolean conditions before → after | Accepted merges |
|---|---:|---:|---:|---:|
| 1 | 4 → 4 | 21 → 21 | 593 → 593 | 0 |
| 2 | 4 → 3 | 22 → 19 | 476 → 442 | 1 |
| 3 | 2 → 2 | 16 → 16 | 221 → 221 | 0 |

Stored conditions count expert split tests, evidence guards, semantic-support
conditions, fixed counterexample literals and new abstention-preservation literals.
This is a storage/complexity measure, not a measured latency or API-cost reduction.
Across the three alternatives, the expert total falls 10→9 and terminal rules 59→56.

## Local accuracy and cross-batch sharing

Parent fitting uses only original reference labels on the exact deduplicated
child union. It preserves each immediate child's correct count, each original
batch within each child, and inherited retention requirements. Unsupported leaves
and explicitly contradictory Yes paths remain prohibited.

Among feasible trees, the search prefers:

1. Fewer total training errors.
2. Fewer terminal rules.
3. More correctly predicted examples reaching leaves supported by multiple original batches.
4. More correct support beyond each leaf's largest contributing batch.
5. Shallower structure and deterministic ties.

Sharing participates inside the local-error search frontier, so an equally
accurate and equally compact shared alternative is not discarded before ranking.
Incorrect examples from a second batch do not earn sharing credit. An exhaustive
small-tree test verifies this objective, and a counterexample fixture increases
shared correct support from 12 to 14 with the same 16/16 accuracy and four leaves.

The accepted real merge combines a G2 specialist with an overlapping G2/G4
expert. The union has 24 distinct cases, not 36. The parent has seven terminal
rules and retains both immediate-child accuracies: **12/12 and 23/24**. Its G4
floor remains 11/12. The complete routed system still serves every original
batch correctly at 12/12 through the remaining experts and recomputed coverage.

The new parent has four correctly shared terminal rules, serving **17** correct
examples across G2/G4, versus three shared rules serving **15** in the former
larger expert. A cheaper subsumption alternative also passed, but at equal
expert/rule counts the final selection prefers this better-shared learned parent.
Both alternatives were recorded; the chosen parent is newly fitted, not just an
old expert renamed as a merge.

## Coverage is rebuilt before accepting a merge

For every locally eligible parent, the pipeline:

1. Removes the two proposed children and adds the candidate parent.
2. Refits evidence coverage over the original local training pool and recomputes
   semantic-support conditions. Removed children cannot be silently reintroduced.
3. Retains the v23 counterexample rejection clauses unchanged.
4. Checks the complete routed system against the frozen baseline decisions.
5. Rejects the candidate if it loses protected coverage, changes a protected
   verdict, fails actual deployed compression, or leaves an unpreserved route.

The first experiment exposed an additional issue: removing an expert can remove
its disagreement signal. A locally accurate parent can consequently accept cases
that were previously deferred. This is a routing regression even when the
regular judge happened to produce the same label on a case.

The final implementation distills those old abstentions into short coverage
clauses, using only the frozen gate's accept/defer behavior. It does not read
human reference labels during this step. Each clause has at most three existing
observable feature literals. Lost coverage or changed protected verdicts cannot
be repaired by these rejection-only clauses; such candidates are rejected.

For the accepted merge, four clauses containing nine literals preserve four
previous deferrals. The old child executable is removed; its tree is not hidden
inside the new wrapper. Counting the extra clauses, total stored condition
occurrences still fall **476→442**. Coverage support is freshly fitted rather
than copied from a child to a different parent.

## Verification results and limits

- **144/144 local raw-input tree predictions preserved.** All twelve original
  child batches retain 12/12, using content-cached evidence and renamed request IDs.
- **294/294 recorded pipeline decisions preserved.** This includes all 150
  reviewed development slots, all 38 correct transfer acceptances and all 112
  regular fallbacks. The 22 reviewed false acceptances remain rejected.
- Development accuracy stays **116/150**. The measured gain is compression with
  unchanged recorded behavior.
- Five locally qualified candidate parents and five fresh gate rebuilds were
  independently audited. Two split-1 candidates lose protected coverage and are
  rejected. Three split-2 alternatives qualify; one is selected. Subsequent
  bounded pair searches find no further qualified parent.
- Eighty-two unit/regression tests pass. They cover sharing in the search itself,
  exhaustive small-tree optimality, overlapping scopes, per-child retention,
  routing regressions, immutable rejection clauses, abstention distillation
  without reference labels, serialization and search-budget fallback.
- The audit reproduces the selected parent fit, all candidate coverage rebuilds,
  490 candidate routing decisions, final raw inference and fallback identities.

Parent search is bounded to depth eight, 24 shortlisted partitions per state,
80,000 states per fit and 500,000 combinations. Each split allows at most three
pairwise rounds, 24 new fits and 32 gate rebuilds. The recorded run uses 30 unique
fits across the splits, two fit-cache hits and five gate rebuilds. Eight fits hit
their state limit; four stop at a feature-equality infeasibility certificate.
Other completed bounded searches are not global infeasibility proofs.

All routing probes are known training/development/regression cases. They also
supervise abstention preservation and candidate selection. Zero measured routing
regressions is therefore a regression guarantee for this recorded set, not a
new generalization claim or universal equivalence over unseen feature records.
This remains opt-in. No new model calls or reserved final-set predictions occur.

## Artifacts and use

Final run: `logs/exps/261019-pairwise-merge-v24-r1`. The pilot and first full draft
remain recorded. The draft ranked total gate storage before sharing; the final
ranking follows the requested preference for cross-batch sharing at equal expert
and terminal-rule counts. Source snapshots preserve that earlier draft.

```python
from critical.core.calibration.merge_route_support_v24 import restore
from critical.core.optimization.prompt.calitree.bound_evidence_cache import (
    BoundEvidenceCache, CachedEvidenceCoveredJudge,
)

gate = restore(saved_gate)  # Handles unchanged and merged gate artifacts.
cache = BoundEvidenceCache(model_identity, artifact=saved_evidence_cache)
judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=model_identity)
result = judge.judge(instruction, evidence, case_id=request_id)
```

The existing v23 upstream caches remain valid; no observation or interpretation
is regenerated for this experiment.

```bash
PYTHONPATH=. /path/to/python -m run.calitree_pairwise_merge_v24 \
  --previous-run logs/exps/261019-counterexample-coverage-v23 \
  --output-dir logs/exps/new-pairwise-run
PYTHONPATH=. /path/to/python -m run.verify_calitree_pairwise_merge_v24 \
  --output-dir logs/exps/new-pairwise-run
```

See [compact results](experiments/calitree_pairwise_merge_v24.json) and
[portable gates](../examples/calitree_pairwise_merge_v24/README.md).
