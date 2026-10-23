# Rejecting the reviewed coverage errors while retaining local accuracy

The v23 rejection layer rejects **all 22 reviewed false acceptances** while
preserving **144/144 local trained tree predictions** and **all 38 previously
correct transfer acceptances**. All twelve original child batches remain 12/12.
No tree verdict, human reference, upstream observation or earlier artifact was
changed. No new model calls were made.

This is counterexample calibration. The former transfer outcomes now explicitly
participate in fitting the rejection checks, so the post-fit result is a
regression result on development data, not fresh generalization evidence.

## What the review found

The 22 false acceptances represent 17 distinct examples across three alternative
gates. Fourteen have a Partial reference, seven No and one Yes. The previous
semantic-support filter did not fully constrain physical-check novelty and
interactions between the physical and semantic evidence.

The new layer uses only the existing declared evidence/task predicates. It learns
short Boolean support clauses: every clause must pass, and each clause is an OR
of at most three literals. A case violating a clause is sent to the regular judge.
This is equivalent to rejecting a particular unsupported conjunction of states.
There are 21 clauses containing 35 literal tests across the three gates.

Examples of observed rejection patterns include:

- A requested presence outcome is false across its checks, although the expert
  emitted Yes (N059 in splits 1 and 2).
- All intermediate contact checks are unknown in an accepted region that had no
  protected examples with that state (N047 in splits 2 and 3).
- A pose outcome is false and original identity is not fully established (N054).
- Some cases require combinations of two or three evidence predicates; no single
  predicate can reject them while retaining all protected correct inputs.

These are empirical applicability limits for the particular gate, not universal
rules for judging edit satisfaction. The detailed review records every instruction,
old prediction, reference, fallback prediction, previous matching expert region
and violated support clause with its predicate meaning and actual value.

## Calibration constraints

For each split, the fitter protects all 48 original local examples and every
previously correct accepted transfer example. It must reject every reviewed
accepted error. The fitter fails explicitly if an error is indistinguishable from
a protected input under the allowed features, or if its declared search/clause
bounds cannot separate them. It never introduces a case-ID or image-hash rule.

Runtime receives only the compiled instruction and validated evidence record.
The serialized layer contains feature literals, the unchanged previous gate and
aggregate calibration counts. It contains no reviewed-case list, source IDs,
instruction-text lookup or new predicted labels. A previous rejection stays a
rejection; an allowed prediction is exactly the previous frozen expert's output.

Correct transfer examples are protected to prevent a trivial reject-everything
solution. Every reviewed error is used; none is removed from the denominator.
Search is bounded to three literals per clause, 20,000 states per reviewed error,
64 clauses and 256 calibration examples. The bounded search does not claim a
globally minimum rejection model.

## Results

| Split | Local tree accuracy | Wrong acceptances before → after | Correct acceptances retained | Full development-system accuracy before → after |
|---|---:|---:|---:|---:|
| 1 | 48/48 | 7 → 0 | 17/17 | 37/50 → 40/50 |
| 2 | 48/48 | 5 → 0 | 11/11 | 37/50 → 40/50 |
| 3 | 48/48 | 10 → 0 | 10/10 | 30/50 → 36/50 |

Across the 150 development slots, accepted tree predictions change from 38 correct
out of 60 accepted to **38 correct out of 38 accepted**. The other 112 slots use
the regular judge: 90 previous fallbacks plus the 22 newly rejected cases.
The regular response is correct on twelve of those 22, raising the full-system
score from **104/150 to 116/150**. Ten reviewed cases remain incorrect under the
regular judge; they are no longer falsely accepted by the tree gate.

The 144 local raw-input checks pass only instructions and image paths with renamed
request IDs. The content cache supplies original bound observations and
interpretations, not labels or verdicts. All 144 remain covered, execute the same
frozen trees and return the correct local labels without a regular fallback.

## Limits and error-only leave-one-out diagnostic

When each reviewed error is omitted from rejection fitting while keeping the
protected pool fixed, only **1/22** is rejected by the remaining error-derived
clauses. This shows that the layer mainly provides targeted regression protection;
it does not establish broad rejection of unfamiliar failures. This diagnostic is
itself exploratory and not an independent full-distribution test.

Do not interpret the post-fit 100% accepted-prediction precision as an estimate of
unseen accuracy. Future evaluation needs new inputs that were not used to choose
the checks. The implementation remains opt-in; the regular judge and original
trees stay available unchanged.

## Use and verification

```python
from critical.core.calibration.counterexample_coverage_v23 import RejectionCoverageGate
from critical.core.optimization.prompt.calitree.bound_evidence_cache import (
    BoundEvidenceCache, CachedEvidenceCoveredJudge,
)

gate = RejectionCoverageGate(saved_gate)
cache = BoundEvidenceCache(model_identity, artifact=saved_evidence_cache)
judge = CachedEvidenceCoveredJudge(calls, gate, cache, identity=model_identity)
result = judge.judge(instruction, evidence, case_id=request_id)
```

The upstream cache and fresh-input behavior are unchanged from the
[evidence coverage pipeline](calitree_evidence_coverage.md). A rejected input gets
the exact regular-judge prompt, without the rejected rule or predicted label.

The recorded run is `logs/exps/261019-counterexample-coverage-v23`. The independent
audit refits the three rejection layers, checks every support clause against the
protected cases, replays all 294 local/development decisions, verifies all 22
rejections and 38 retained correct transfer routes, and repeats the 144 raw local
inferences. It also recomputes the error-only leave-one-out diagnostic. Seventy
unit/regression tests pass, including indistinguishable-input rejection, literal
and search bounds, identifier/order invariance and prevention of new acceptances.

```bash
PYTHONPATH=. /path/to/python -m run.calitree_counterexample_coverage_v23 \
  --previous-run logs/exps/261019-complete-evidence-coverage-v22 \
  --output-dir logs/exps/new-counterexample-run
PYTHONPATH=. /path/to/python -m run.verify_calitree_counterexample_coverage \
  --output-dir logs/exps/new-counterexample-run
```

Both commands are offline. See the [results and complete 22-case review](experiments/calitree_counterexample_coverage_v23.json)
and [portable calibrated gates](../examples/calitree_counterexample_coverage_v23/README.md).
