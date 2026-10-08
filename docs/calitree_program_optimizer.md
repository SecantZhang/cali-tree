# Casewise CaliTree leaf optimizer

The v2 optimizer fits one instruction/image pair at a time. Each case's reference
label guides its own repair; no other case supplies feedback or selects the leaf.
Parent construction, shared rules, routing, and generalization are deferred.

## Executable leaf

`ProgramSpec` saves the original instruction, rubric, immutable requirement ledger
with exact instruction quotes, editable outcome decomposition and bindings, checks,
dependencies, applicability, and frozen checker template. Its canonical hash covers
all executable fields. Each outcome has exactly one requested fulfillment check;
optional supporting checks provide evidence without counting as requested progress.
A negative supporting result is informative; required unknowns propagate unresolved.

Applicable outcomes aggregate deterministically: all complete → `yes`; all absent
→ `no`; otherwise known progress → `partial`. Unknown applicability, invalid or
missing required observations, and an empty applicable set remain unresolved.
Each graph is limited to four total checks; requirements are never truncated.

The requirement ledger preserves explicit provenance, not a proof of semantic
completeness. A label-blind model audit compares the entire graph with the original
instruction and can reject invented or omitted requirements, weakened criteria,
answer-coded rules, or unjustified non-applicability. It does not certify visual
correctness. Atomic consistency is measured separately from label agreement.

## Local repair API

```python
from critical.core.decision.compiler import ProgramCompiler
from critical.core.decision.executor import ModelChecker, ProgramExecutor
from critical.core.optimization.program import (
    Case, CasewiseOptimizer, ModelEditProposer, RepeatedEvaluator,
)

# calls is a CaseCalls view of a shared DurableCalls ledger.
executor = ProgramExecutor(ModelChecker(calls), checkpoint=checkpoint)
optimizer = CasewiseOptimizer(
    ProgramCompiler(calls), ModelEditProposer(calls), RepeatedEvaluator(executor),
    rubric=rubric,
)
case = Case("example", instruction, {
    "source_image": source_path, "edited_image": edited_path,
})
result = optimizer.optimize(case, reference_label="partial")
```

Compilation receives only the instruction and rubric. Checkers receive the relevant
instruction, outcome, check, dependency observations and images. They never receive
the reference label or optimization metadata. The repair proposer receives the
label, both images, traces and diagnostic feedback. Audits receive neither the
reference label nor the target-conditioned repair rationale.

Transactions contain one to four immutable edits: add, remove, split, rebind,
applicability change, and checker revision. Binding and criterion changes can occur
in one atomic transaction. A split records old-to-new outcome mappings. Newly
recognized requirements can be added with exact source quotes; existing requirement
records cannot be deleted or rewritten. Final graph validation rejects uncovered
requirements, broken dependencies, cycles, orphan supports and over-cap programs.

Search retains the seed and uses two rounds, beam width two, and at most two
transactions per parent. Valid neutral intermediates can enter the next round.
Invalid edits become diagnostics instead of ending the first round. Candidates
receive one screening draw; matching audited candidates receive three fresh
confirmation draws. Confirmed candidates are ranked by agreement, coverage, final
consistency, fewer checks, then measured completion-token cost. A speculative repair
cannot replace the seed without confirmation evidence. Budget-limited runs preserve
the best available result and all durable attempted observations.

## Saved CaliTree leaves

```python
from critical.core.optimization.prompt.calitree import CaliTreeBuilder
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf

bundle = CaliTreeBuilder.build_program_leaves(
    cases,
    reference_labels={case.id: label for case, label in labeled_cases},
    optimizer_factory=make_case_optimizer,
)
# JSON save/load does not recompile, rebind, or optimize.
result = judge_program_leaf(bundle, "leaf:example", evidence, executor)
```

The bundle format is `calitree-casewise-leaves-v2`; programs use `decision-leaf-v2`.
Each leaf stores its one-case fit scope, exact selected program, search lineage,
metrics, audit and executor identity. The pilot adds final comparisons and support
status. Direct execution verifies evidence hashes and executor settings: a fitted
local leaf cannot silently receive a different case. Failed compilation remains a
recorded leaf without an executable program.

Old v1 program bundles are rejected explicitly. The old pilot and source snapshots
remain archived, while committed prompt-leaf and hierarchy APIs keep their formats.

## Run and resume

```sh
.venv/bin/python -m run.calitree_program_optimization --demo --output-dir .cache/casewise-demo
.venv/bin/python -m run.calitree_program_optimization --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_program_optimization --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_program_optimization --report --output-dir RUN_DIRECTORY
.venv/bin/python -m pytest -q tests/unit/calitree/test_program_optimizer.py
```

Preflight verifies the exact twelve prior-pilot cases and image hashes, four per
class and twelve distinct source-pixel groups. All twelve are fitting cases; the
fresh seed/selected comparisons measure repeat execution on those same cases, not
held-out generalization. The manifest freezes code hashes, images, model settings,
limits and source snapshots. Code or evidence changes require a new run.

GPT-6 Luna uses temperature zero and the repository's `none` reasoning setting.
Every request has one HTTP attempt; there is no schema retry or model substitution.
Provider rejection or three consecutive transport failures stops the run. Failed
and interrupted slots remain attempted after resume. Valid cached replies can be
read without making another request. Final comparisons cannot re-enter search.

The shared cap is 600 requests and 768,000 completion tokens: at most 26 search
requests and 24 final requests per case. Reserve all 288 possible final checker
requests and 294,912 completion tokens before search. Checker caps are 1,024 tokens;
other stages cap at 2,048. Crashed requests retain their reserved token charge.
The sequential ledger supports one runner per output directory.

A leaf earns `locally_fitted` only when its selected program has an accepted audit
and all three fresh final draws match the reference label with full coverage.
Successful confirmation during search is `confirmed_local`, a provisional status.
Negative and inconclusive outcomes are preserved and are valid experimental results.
