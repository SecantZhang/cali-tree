# Task coverage and tree references for the regular judge

The subsequent [evidence coverage path](calitree_evidence_coverage.md) preserves
144/144 local answers by executing covered frozen experts directly and reusing
content-bound upstream evidence. This page records the unchanged v19 reference-
guided experiment and its measured regressions.

**Implemented and tested; experimental, not promoted.** The approved paired run
completed all 141 requests. The hybrid improves one split overall but loses
accuracy on two original child batches, so it does not satisfy local accuracy
preservation. The regular judge remains the existing default.

The opt-in v19 gate recognizes supported task structures before visual judging.
Covered inputs receive applicable conditional tree rules as an advisory reference.
Uncovered or invalidly compiled inputs use the exact original flat-judge prompt,
payload and response schema. The final label always comes from the visual judge.

## Coverage contract

The input is an instruction and its validated compiler-v3 program. The gate uses
only requested outcome kinds and literal polarities, whether identity is required,
and whether the instruction has multiple requirements. It does not read images,
outcome observations, semantic interpretations, reference labels or case IDs.
Matching a task structure is a coarse applicability estimate, not proof that a
rule's visual conditions hold. Different object names can match the same scope;
unseen combinations of operation kinds fall back.

The offline builder visits paths in the frozen trees. A conditional rule is
eligible for a task scope only if at least two distinct sources and instructions
correctly support it in the tree's own training scope. It is excluded if another
case in the full local training pool contradicts it under the same task scope
and conditions. Constant verdicts and rules based only on instruction type are
excluded. The builder validates original tree targets and evidence provenance.

At inference, the gate selects one eligible policy using stored support, then
cross-batch support, compactness and stable identity. It supplies that policy's
supported rules for the matching task scope. It never combines incompatible
policies, truncates path conditions or presents a predicted verdict for the new
case. Oversized packets fall back instead of being truncated.

The reference includes complete Boolean path conditions, their declared meanings,
and conditional conclusions. Training IDs, example labels and correctness counts
are not sent to the model. The prompt explicitly instructs the judge to verify
conditions from the images, preserve unknowns, and use the ordinary rubric when
no rule applies or the reference conflicts with visible evidence. A reference
is not a replacement for inspecting SOURCE and EDITED.

## Calling the judge

```python
from critical.core.optimization.prompt.calitree.task_coverage import (
    TaskCoverageGate, TaskCoveredJudge,
)
from critical.core.decision.bound_compiler_v3 import BoundInstructionCompilerV3

gate = TaskCoverageGate(saved_gate)
judge = TaskCoveredJudge(calls, gate, compiler=BoundInstructionCompilerV3(calls))
result = judge.judge(instruction, evidence, case_id=case_id)
```

`calls` is the existing durable, explicitly budgeted model-call interface. Supply
`program=...` to reuse a validated compiled instruction and avoid compilation.
If no compiler/program is supplied, or compilation fails, the judge takes the
regular path. With a cached program there is one visual judge call, regardless
of coverage. Fresh compilation adds one call, and possibly its existing bounded
repair call. No physical observation or semantic-interpretation pass is required.

`request(instruction, program)` exposes the exact prompt, payload and route without
making a model call. Route metadata means a reference was offered; it does not
assert that the model actually followed a rule correctly.

## Local accuracy evaluation

The approved frozen comparison uses all three existing 48-case training splits:
144 local slots and 99 distinct cases spanning 98 source groups. There are 99 fresh regular judgments and
42 guided judgments, using GPT-6 Luna, temperature zero and no reasoning. The
102 uncovered slots reuse the exact regular response. Total caps are 141 requests
and 288,768 completion tokens, plus input tokens; no retries or final-set access.

Gate support and trees are frozen before collection. This is a local training
diagnostic, not a held-out generalization test. Cached tree predictions are a
separate comparator; passing offline routing tests cannot establish the accuracy
of the new prompted judge. The report compares baseline and hybrid accuracy for
each original child batch and against the saved tree's local accuracy, listing
each win and loss. There is no automatic promotion based on aggregate scores.

The current run is `logs/exps/261019-task-coverage-v19-r3`. Earlier preflights were
superseded before any API request: serialization normalization, a local
counterexample guard, then source-workspace credential resolution. The approved
cases, requests and caps in r2 and r3 are identical.

```bash
PYTHONPATH=. /path/to/python -m run.calitree_task_coverage \
  --source-root /path/to/original/workspace --output-dir logs/exps/new-coverage-run
# After explicit paid-call approval:
PYTHONPATH=. /path/to/python -m run.calitree_task_coverage \
  --output-dir logs/exps/new-coverage-run --live
PYTHONPATH=. /path/to/python -m run.verify_calitree_task_coverage \
  --output-dir logs/exps/new-coverage-run
```

The source workspace supplies the historical training artifacts and images; the
current worktree owns the new implementation and outputs. Preflight and audit
verify source, code, image and prompt hashes. The audit reconstructs every exact
request identity, checks saved model responses, accounts for usage and replays
all twelve per-child comparisons.

## Results from the approved run

| Split | Task-covered slots | Regular judge correct | Hybrid correct | Saved forest local correct |
|---|---:|---:|---:|---:|
| 1 | 3/48 | 33/48 | 33/48 | 48/48 |
| 2 | 17/48 | 28/48 | 31/48 | 48/48 |
| 3 | 22/48 | 37/48 | 36/48 | 48/48 |

The saved forest column uses its original cached evidence and respective training
scopes. It is a local-fit comparator, not an independent direct-image judge or a
deployable combined router. The fresh paired arms use the same images and model
settings. Their pooled training-slot totals are 98/144 and 100/144, with four wins
and two losses. These slots overlap across splits and are not independent samples.

The hard local criterion fails: split 2 G1 drops from 8/12 to 7/12; split 3 G3
drops from 8/12 to 7/12. Other original batches tie or improve. The hybrid also
does not retain the saved forest's perfect local scores. All 102 uncovered slots
reuse exactly the same baseline response, so every paired change comes from a
covered request. One draw per request does not establish repeat robustness.

Two regressions illustrate the difference between task coverage and actual rule
applicability:

- **N120, split 2:** a potato-placement request changes from correct Yes to
  Partial. Its supplied rule predicts Partial from a collateral-disappearance
  predicate. That rule does **not** match the cached feature record, despite
  matching the task scope. The guided rationale introduces a replacement or
  duplication concern. A learned collateral-only correlation is a weak semantic
  reference even when it has no known in-scope training counterexample.
- **N050, split 3:** a plate-relocation request changes from correct Partial to
  No. The packet contains the correct Partial path under the cached evidence,
  but the fresh judge describes the requested relation as absent. Supplying the
  rule does not preserve the original extractor/interpreter's feature decisions.

No rule was rewritten after observing these outcomes, no failed cases were
resampled, and no default judge or frozen tree was replaced. Improving this
approach would require a separate intervention, such as evidence-level
applicability or exclusion of rules without requested-outcome evidence, followed
by another explicit comparison.

Thirty offline tests pass. The independent audit verified all 141 exact request
identities and successful responses, all 144 local slots, all twelve child
comparisons and the 102 fallback reuses. Usage was 201,212 input tokens and 8,301
completion tokens, within the approved caps. There were no final-set predictions.
See [the compact result artifact](experiments/calitree_task_coverage_v19.json) and
[portable gate artifacts](../examples/calitree_task_coverage_v19/README.md).
