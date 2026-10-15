# M1: exact bound questions and uncertainty-preserving evidence

**Date:** October 14, 2026\
**Status:** M1 implementation and development audit complete. This is an evidence representation milestone, not a trained calibration hierarchy.\
**Current implementation:** [bound_evidence_v2.py](../critical/core/decision/bound_evidence_v2.py). The earlier `bound_evidence.py` and v1 run are retained for reproducibility.

## What changed

The instruction compiler writes each physical question once. The visual observer
receives that exact program, including the question, target, reference, role,
desired polarity, applicability condition, and dependencies. Every returned
answer must match both its question hash and the ordered image-pair hash.

The deployed shape of this component is two model calls:

1. **Instruction-only compilation:** instruction → bound physical program.
2. **One visual observation:** program + SOURCE/EDITED images → answers to those exact questions.

Code validates the responses, derives physical features, and preserves unknowns.
There is no model call for the diagnostic readout and no fitting in M1.

Hashes protect attachment and version identity. They do not prove that a model's
visual observation is true or that its natural-language question is unambiguous.
That distinction is why the milestone also includes a direct image audit and
explicitly recorded disputes.

## Contracts and safeguards

The program separates six roles:

| Role | Meaning |
|---|---|
| `outcome` | A requested physical change or endpoint |
| `identity` | Correspondence to the original target when needed |
| `preservation` | A property/configuration expected to remain; never affirmative progress |
| `intermediate` | A concrete configuration toward a linked requested outcome |
| `collateral_disappearance` | An unrelated original entity disappearing |
| `collateral_deformation` | An unrelated structural size/shape/component/topology change |

Requirement membership is derived from each check's linked requirement IDs.
The model does not generate two independently editable copies of those links.
Each requirement must contain a requested outcome. Preservation-only conditions
cannot masquerade as additional requested successes.

Temporal and style requirements must include linked intermediate checks.
Intermediate geometry is kept separate from identity/preservation uncertainty;
its dependency graph cannot make observable progress disappear merely because
an identity check is unknown. All dependencies are validated for references and
cycles. Raw check answers remain available alongside derived features.

States remain `true`, `false`, `unknown`, or `not_applicable`. A required check
marked not applicable becomes an explicit applicability diagnostic and an
unknown effective state, never an automatic pass. Unknown outcomes do not
default to No. The fixed diagnostic evaluates both admissible evidence bounds
and resolves only when the label is invariant.

Absence is explicitly bound by two fields:

- `absence_when`: the answer value that asserts absence, or `never`.
- `absence_source_anchor`: whether an original entity must be identified first.

Thus “is the cylinder absent?” and “does any part remain?” receive the same
safeguard despite opposite polarities. An unsupported source binding or an
occluded/cropped relevant region converts an asserted absence to unknown while
preserving the raw answer and the rejection diagnostic. Nonappearance of a
genuinely new entity does not require identifying a nonexistent original target.

## Development run and controlled diagnostic

The run used the twelve already-observed M0 development cases, four per label,
with the same AURORA editor and GPT-6.1 Sol/high profile. The reserved fifty were
excluded from the runner's allowed cases and received no calls.

Two separately sealed development versions are retained:

| Version | Calls | Valid programs | Valid observations | Fixed diagnostic correct | Unresolved |
|---|---:|---:|---:|---:|---:|
| Initial v1 | 23 | 11/12 | 11/12 | 6/12 | 4 |
| Corrected v2 | 24 | 12/12 | 12/12 | 9/12 | 2 |

The first version revealed a negative-polarity absence-guard gap, preservation
being counted as progress, and an omitted body-pose intermediate. One compiler
graph was rejected rather than executed. V2 corrected the generic schema and
prompts; it did not edit the first run's observations or relabel cases.

Each version allows one attempt per stage and one image presentation per case.
These are two disclosed development iterations, not repeated measurements used
to claim robustness. Total new calls were 47, below the recorded 120-call
development-extraction ceiling; the second schema version has its own preflight
and budget record.

The initial M0 ceiling of 120 extraction calls described one version over sixty
development sources. Completing v2 on the remaining 48 sources would need 96
additional calls. `development_budget_revision.json` therefore explicitly
accounts for the retired v1's 23-call overhead: 143 extraction calls across both
versions, or a prospective full-study ceiling of 353 instead of 330. No such
additional collection was dispatched by M1, and the M0 seals were not changed.

To distinguish the representation change from later calibration, both legacy
v16 features and new v2 features were evaluated with the same fixed,
**uncalibrated** diagnostic readout:

| Representation under common readout | Correct | No recall | Partial recall | Yes recall | Resolved | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy v16 evidence | 9/12 | 50% | 75% | 100% | 12/12 | 0.746 |
| M1 v2 bound evidence | 9/12 | 75% | 75% | 75% | 10/12 | 0.821 |

The full-denominator accuracy is 75% for both. New feature semantics and new
observations can change decisions even under the same readout. This is a small
development comparison; it establishes neither higher held-out accuracy nor
repeat robustness. These numbers are not results from the four learned v16
policies or from a newly trained M2 policy.

V2 used 72,921 input tokens and 72,149 completion tokens. V1 used 57,972 input
tokens and 58,246 completion tokens. Reducing four stages to two does not itself
establish a proportional token-cost or latency reduction.

## Image audit and remaining limitations

All twelve SOURCE/EDITED pairs were inspected directly. Thirty-nine selected
physical checks were reviewed, including all five failure families. This was an
assistant review aware of historical references and failures, not independent
human annotation. No raw observation or dataset label was overwritten.

| Failure family | Evidence retained in v2 |
|---|---|
| Body pose | A plausible actor's raised pelvis is observed separately from uncertain original-instance correspondence |
| Collateral disappearance | The cylinder is removed, and the unrelated gray sphere is separately recorded as missing |
| Compound action | Hand/spoon displacement, coherent grip, and powder release remain distinct; visibility cannot substitute for release |
| Style progress | Photographic warmth and preserved layout do not supply crayon/painting progress; localized defining marks are checked separately |
| Collateral deformation | The newly added right-side ball and the unrelated left sphere's size reduction are separate facts |

The remaining diagnostic errors/abstentions are:

- **H03, mug:** the requested relocation is observed, but the model marks a
  tapered mug contour as failed preservation. Its physical interpretation and
  materiality are disputed. The fixed readout's blanket preservation gate gives
  Partial while the dataset reference is Yes.
- **H07, bottle:** source-instance correspondence and off-frame action evidence
  are incomplete. The record remains Unresolved rather than inventing what
  happened to the original lid and hand.
- **H08, spoon:** raw displacement and failed grip are retained. Identity
  dependencies make the fixed readout's positive-progress conclusion uncertain,
  so the output is Unresolved rather than a default No.

The visual audit also flags the certainty of a cabinet-deformation observation
and ambiguous painted-counterpart wording in an identity question. Valid hashes
do not remove those perceptual or linguistic limitations. M2 must not treat every
generated preservation question as a universally material satisfaction veto.

See the [visual audit](../logs/exps/261014-m1-bound-evidence-development12-v2/visual_audit.md)
and its [structured disputed checks](../logs/exps/261014-m1-bound-evidence-development12-v2/visual_audit.json).

## Verification

- Twelve valid v2 programs and twelve valid observations.
- Ninety bound questions independently checked against program content hashes,
  exact response questions, image-pair identities, and raw call records.
- Twelve adversarial question substitutions rejected.
- Thirty-five absence probes verified across the actual generated programs.
- Both versions replay exactly with zero new model calls.
- Sixty-seven distinct scoped tests pass, including six saved logical regression
  fixtures and M0/legacy protections. Logical fixtures are not human fact labels.
- Original v16 data and the M0 reservation remain unchanged; final-set calls are zero.

The independent audit recomputes label counts and uncertainty-aware diagnostic
decisions separately from the runtime evaluator. The payload audit verifies that
reference labels, old model outputs, and final-test cases do not enter extraction.

## Using and reproducing the component

Use the v2 API for new work:

```python
from critical.core.decision.bound_evidence_v2 import (
    BoundInstructionCompiler, BoundVisualObserver, derive_record, image_identity,
)

compiled = BoundInstructionCompiler(compiler_calls).compile(instruction)
program = compiled["program"]
observed = BoundVisualObserver(observer_calls).observe(program, image_pair)
record = derive_record(program, observed["observation"], image_identity(image_pair)[1])
```

Check IDs are local handles, not reusable model features. Future learners should
operate on physical types, roles, dependencies, and quantified states rather
than memorize check IDs, object names, instruction strings, or source hashes.

Offline reproduction:

```bash
.venv/bin/python -m run.calitree_bound_evidence_v2 --replay --output-dir logs/exps/261014-m1-bound-evidence-development12-v2
.venv/bin/python -m run.audit_calitree_bound_evidence logs/exps/261014-m1-bound-evidence-development12-v2
.venv/bin/python -m run.calitree_bound_evidence --replay --output-dir logs/exps/261014-m1-bound-evidence-development12-v1
.venv/bin/python -m run.calitree_m0_finalize --check --output-dir logs/exps/261014-semantic-hierarchy-m0-fifty-v1
```

Primary artifacts are `manifest.json`, `observations.json`, `results.json`,
`payload_audit.json`, `independent_audit.json`, `visual_audit.json`,
`iteration_accounting.json`, raw call ledgers, snapshots, and `replay.json` under
the v2 experiment directory. The initial v1 directory remains available.

## Next milestone

M2's new scalable learner and the M3/M4 baselines/router have now been implemented
and independently audited; see [their results and limitations](calitree_m2_m4_semantic_baselines.md).
The frozen historical v16 learner retains its sixteen-row limit for reproducibility.
M1 itself did not fit a new policy, build routing or merges, or evaluate the
reserved final set. No later milestone has evaluated that final reservation yet.
