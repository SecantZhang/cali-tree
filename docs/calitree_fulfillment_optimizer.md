# Current CaliTree fulfillment pipeline

Use `critical.core.optimization.program.create_leaf_optimizer` for new local leaf optimization and
`run.calitree_fulfillment` for experiments. Fulfillment is the default. Saved artifact versions remain
explicit; this consolidation does not introduce a new scoring version or reinterpret old leaves.

## Algorithm

1. Compile label-free, instruction-grounded conditions with observable 0/.5/1 score anchors.
2. Execute independent visual checks. Record fulfillment, confidence and failure state separately.
3. Aggregate the protected weighted fulfillment in code: >=0.9 satisfied, <=0.1 nonsatisfied,
   otherwise partial. Missing evidence is an interval, not zero. Confidence never changes weights.
4. Use native TextGrad feedback and label-blind visual discovery to propose immutable structural repairs.
5. Screen once and confirm matching candidates on five fresh draws, retaining the seed and valid intermediates.
6. Freeze selection before five fresh final-verification draws. Apply the existing confidence, consistency,
   coverage and agreement gates. Semantic auditing and model readout remain disabled.

Requirements retain equal immutable mass; seed facets divide their requirement budget and splitting conserves
root mass. Only zero-mass auxiliary checks can be removed. Execution is flat, capped at four checks. Search remains
bounded to fifteen rounds and the enforced durable call/token budget. This cleanup changes organization and defaults,
not acceptance thresholds, provider settings, prompts or scoring. Local empirical robustness is not semantic proof
or evidence of generalization.

## Public API and modules

```python
from critical.core.optimization.program import create_leaf_optimizer

optimizer = create_leaf_optimizer(calls, original, checkpoint=checkpoint)
result = optimizer.optimize(case, reference_label, seed=seed)
```

`calls` is the enforced case-scoped durable ledger; `original` carries the immutable instruction/rubric/requirements.
Omitting `scoring_mode` selects fulfillment. The explicit binary mode is retained as the paired experiment control.

| Component | Location |
|---|---|
| Current executable program, compiler, edits, aggregation | `critical/core/decision/fulfillment.py` |
| Shared flat fields, provenance validation, execution, recovery | `critical/core/decision/shared/` |
| Current optimizer/proposer/factory | `critical/core/optimization/program/fulfillment.py` |
| Shared search, metrics, recovery evaluation, backward feedback and discovery | `critical/core/optimization/program/shared/` |
| Shared exact feedback prompts | `critical/core/prompts/templates/leaf_feedback_v1/` |
| Current experiment CLI | `run/calitree_fulfillment.py` |
| Historical optimizer implementations | `critical/core/optimization/program/legacy/` |
| Historical multimode experiment implementation | `run/legacy/calitree_adaptive_leaf.py` |

Shared source pinning, reference conversion, failure replay and reporting no longer import previous experiment runners.
Public package exports are lazy. Importing the current optimizer or CLI loads no historical optimizer modules.

## Offline and live commands

```sh
.venv/bin/python -m run.calitree_fulfillment --offline-demo --output-dir /tmp/calitree-demo
.venv/bin/python -m run.calitree_fulfillment --preflight --output-dir logs/exps/NEW-FULFILLMENT-RUN
.venv/bin/python -m run.calitree_fulfillment --live --output-dir logs/exps/NEW-FULFILLMENT-RUN
.venv/bin/python -m run.calitree_fulfillment --resume --live --output-dir logs/exps/NEW-FULFILLMENT-RUN
.venv/bin/python -m run.calitree_fulfillment --report --output-dir logs/exps/NEW-FULFILLMENT-RUN
```

The experiment compares binary and fulfillment using the common graded observer, exact original twelve-case collection,
independent arm histories, and the existing v7 reservations/allowances. Preflight, demo and report make no model calls.
Live execution still requires explicit live gating and official OpenAI credentials. One attempt per durable slot and
explicit transport-stop release remain unchanged; failed slots are not silently retried.

`run.calitree_adaptive_leaf` is a compatibility entry point: new runs and its offline demo now default to fulfillment.
Historical `--scoring semantic`, `--scoring counting`, and `--scoring endpoints` remain explicit options. Stored runs
retain their recorded scoring mode. Historical prompt-based hierarchy APIs and interface templates are unaffected.

## Saved artifacts and replay

V2–v7 leaf dispatch, frozen checker identities/templates, exact bindings, program hashes, observation cache keys,
logical request slots and budget accounting remain compatible. Old optimizer import paths alias their archived modules,
including module identity for callers that patch them. Saved JSON programs are loaded without recompilation/rebinding.

Source pinning intentionally rejects resuming a historical run against changed source hashes. Use its original
`source_snapshot` and pinned replay script; do not edit its manifest to bypass validation. For the completed v7 run:

```sh
.venv/bin/python logs/exps/261009-fulfillment-v7/replay_frozen_analysis.py
```

Current-source replay can also invoke `run.calitree_fulfillment.execute` with the saved manifest and provider factories
that raise if called. Verification for this cleanup replayed current and pinned sources in temporary copies, preserving
all twelve cases, 24 arm results and accounting exactly with no API calls or changes to historical artifacts.

See [the completed report](experiments/calitree_fulfillment_v7_complete_report.md) for measurements and limitations.
V6 remains a descriptive historical benchmark; the latest v7 method did not exceed its earlier reported draw accuracy.
