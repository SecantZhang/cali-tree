# Bank 2: one harmful override and a locally preserving gate revision

Bank 2 scored 19/36 versus regular's 20/36 because it made **one harmful
override and no beneficial overrides**. Four of its eight accepted tree answers
were wrong, but regular was also wrong on three of those four. Rejecting those
three cannot improve accuracy if the fallback remains the same regular judge.

| Case | Instruction | Reference | Regular | Tree | Effect versus regular |
|---|---|---|---|---|---|
| N034 | Transform the car into a red sports car | Yes | Partial | Partial | Both wrong |
| N097 | Show his hands on the plate to arrange the food | Partial | Yes | No | Both wrong |
| **N102** | **Remove the car in front of the bus** | **Yes** | **Yes** | **Partial** | **Loses one correct answer** |
| N130 | Move the book to the right of the cap | Partial | No | No | Both wrong |

## Why the harmful route was accepted

For N102, expert `a7821fa6…` takes this path:

```text
identity evidence is not entirely uncertain
spatial outcome is not entirely false
preservation is not unknown
material unrequested collateral change is reported
→ Partial
```

That leaf was fitted on **two Partial examples from batch G3**. Its collateral
penalty extends to this removal task, even though the requested removal,
identity checks and explicit preservation checks are recorded as satisfied.
The gate has supported Partial coverage for this task/evidence pattern.

The raw expert bank predicts Partial, Partial and Yes. The Yes expert is filtered
out because its existing guard requires the collateral-deformation checks to
meet their desired state. N102 fails that guard. The accepted route therefore
comes from the supported Partial expert; this is not a missing Yes vote.

The observer reports that the bus's lettering, emblem and other details changed,
and the interpreter calls those changes material. Visual inspection confirms
that the target car is removed and the bus's markings/details also change.
The human reference and regular judge nevertheless give Yes. This is a
materiality/rubric mismatch, not simply an invented disappearance or failure
to detect the requested edit.

Deleting the entire expert or rejecting every use of this leaf would discard
correct local decisions. N135, “Move the book to the right of the headphones,”
uses this leaf as its only supported match; its correct answer is Partial,
while regular says Yes. The gate needs a conditional veto.

## Implemented v36 guard

`DisagreementCoverageGate` wraps the frozen verification-only policy. It learns
short semantic support clauses separately for each tree/regular prediction pair.
Correct local and calibration decisions are protected. Only a wrong tree
replacing a correct regular answer is a rejection target. A veto falls back to
the exact regular response; it does not invent a new label or activate another
expert without support.

Bank 2's learned veto is:

```text
tree = Partial AND regular = Yes
AND the task requests an absence/removal outcome
AND all bound identity checks succeed
→ reject the tree route and use regular
```

Equivalently, accepting a Partial/Yes disagreement requires
`identity_all_true_all = false OR task_outcome_absence = false`.
This is a relative-competence condition learned from feedback; it does not assert
that identity checks alone prove edit completion. N102 also has affirmative
requested-outcome completion in its cached evidence.

The rule contains no case IDs, source membership, object names, image hashes or
exact feature-signature lookup. It keeps the locally correct removal example
N073, whose identity checks are not all satisfied, and keeps the spatial
Partial example N135. The parent expert rules and merged regions are unchanged.

The final revision protects prior correct routes for **every possible regular
label**, including judgments different from the recorded draw. An initial
bank-1 candidate failed that stronger check on two prior cases and is omitted
from the final revision. Bank 2's guard passes it; banks 1 and 3 stay unchanged.
Initial v36 prototype code and artifacts remain available; the authoritative
final run is `261020-disagreement-coverage-v36-r1`.

## Results and limits

On the cached 36 cases, now used as development data:

| Bank | Previous verified policy | v36 final revision | Regular |
|---|---:|---:|---:|
| 1 | 21/36 | 21/36 | 20/36 |
| **2** | **19/36** | **20/36** | **20/36** |
| 3 | 22/36 | 22/36 | 20/36 |

Bank 2's accepted coverage falls from 8/36 to 7/36; correct accepted decisions
remain four, so accepted accuracy rises from 50.0% to 57.1%. Its other three
wrong accepted answers remain. All other predictions on the 116 recent
development cases are unchanged. No previously correct decision is sacrificed.

**This is a development fix, not demonstrated new-source generalization.** The
guard has one harmful supporting source. With that source excluded, it is not
learned and bank 2 remains at 19/36. The 52-source replay introduces no changes
to the source-held-out parent predictions. More independent examples of this
failure pattern would be needed to establish transfer.

Verification passes:

- 144/144 local predictions and their coverage retained.
- 179 previously correct recorded routes retained.
- 685 correct prior-route/regular-label combinations retained.
- 156 source/bank folds independently refitted; 348 held predictions replayed.
- 432 real-serving-wrapper scenarios checked with stub regular responses.
- 38 focused tests pass; zero new model calls or evidence/reference changes.

## Use the revised gate

The existing `VerifiedSemanticJudge` accepts the new policy:

```python
import json
from pathlib import Path
from critical.core.calibration.disagreement_coverage_v36 import DisagreementCoverageGate
from critical.core.optimization.prompt.calitree.verified_semantic_judge import VerifiedSemanticJudge

path = Path("logs/exps/261020-disagreement-coverage-v36-r1/full/split2/gate.json")
gate = DisagreementCoverageGate.restore(json.loads(path.read_text()))
judge = VerifiedSemanticJudge(calls, gate, evidence_cache=cache, identity=identity)
```

Keep the serving wrapper's default `enable_corrections=False`; this guard was
calibrated for that mode. The wrapper obtains one regular judgment, including
on accepted inputs, and adds no model calls per node or expert.

Artifacts in the final run include `bank2_wrong_acceptances.json`,
`bank2_harmful_leaf_provenance.json`, full/source-held-out predictions, protected
retention checks and the independent `verification.json`. Reproduce with
`run/calitree_disagreement_coverage_v36r1.py` and audit with
`run/verify_calitree_disagreement_coverage_v36r1.py`.
