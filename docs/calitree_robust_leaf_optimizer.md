# Robust local leaf optimization (v3)

The implementation follows [the design](calitree_robust_leaf_optimizer_design.md). It fits one instruction and its saved source/edited images at a time. A leaf stores its decomposition **and** executable checks; loading it does not compile a new prompt or bind new images. Parent construction and cross-case generalization remain deferred.

## Runtime and public API

`critical.core.decision.robust` provides `RobustProgram`, `Node`, `Inference`, `RobustExecutor`, `RobustChecker`, and validated artifact export/restore. `critical.core.optimization.program.robust` provides `RobustLeafOptimizer`, `RobustEvaluator`, `RobustPolicy`, `NodeTextGrad`, and `StructuralProposer`.

```python
from critical.core.decision.robust.compiler import RobustCompiler
from critical.core.decision.robust import RobustExecutor, RobustChecker
from critical.core.optimization.program.robust import (
    RobustLeafOptimizer, RobustEvaluator, NodeTextGrad, StructuralProposer,
)

# calls is one CaseCalls view of a DurableCalls ledger, with search=109/final=40.
compiler = RobustCompiler(calls)
evaluator = RobustEvaluator(RobustExecutor(RobustChecker(calls), checkpoint=checkpoint))
optimizer = RobustLeafOptimizer(
    compiler, StructuralProposer(calls), evaluator, NodeTextGrad(calls),
    rubric=rubric, mode="tree", selection="pareto",
)
result = optimizer.optimize(case, reference_label, seed=seed, budget=calls)
```

`budget` is optional and, when supplied, must be the same enforced durable scope used by the compiler. Limits belong to that ledger, not a second independent counter. A call budget exhausted during optimization returns the best available program with its stop reason. Provider rejection or three consecutive transport errors stop the runner.

Use `CaliTreeBuilder.build_program_leaves(cases, reference_labels=..., optimizer_factory=..., seeds=...)` for one saved leaf per case. The v3 bundle version is `calitree-casewise-leaves-v3`; its programs use `decision-leaf-v3`. v2 bundles remain supported by their existing runtime, and mixed-version bundles are rejected.

```python
import json
from critical.core.optimization.prompt.calitree.node.program_leaf import judge_program_leaf

bundle = json.loads(open("leaves.json").read())
trace = judge_program_leaf(bundle, node_id, evidence, executor, repeat="inference/0")
```

Use the saved checker/provider/scope identity and exactly the saved evidence. Changing evidence or execution identity raises an error. New repeat names create independent inference slots. Reusing a slot replays its saved observation, including failure.

## Executable semantics

The implicit root is an ordered sequence. Nodes have a single parent, ordered siblings, explicit activation states, and separate evidence references to ancestors. Maximum total executable checks and maximum depth are both four. The node array fixes sibling order. Support nodes return `pass/fail/unknown`; requested nodes return `complete/partial/absent/unknown`.

Tree mode activates children only on their declared parent states. Flat mode evaluates the same checks without activation pruning or shortcut inferences, while retaining evidence dependencies and applicability. A negative known support result remains evidence. Unknown dependencies block their dependent checks. Independent branches continue.

Each requested outcome has one fulfillment node. Every path begins with every outcome explicitly unresolved; queried evidence, justified inference, or saved applicability accounts for it. Skipping a check does not remove its requirement. The fixed reducer returns `yes` for all complete, `no` for all absent, `partial` for other known progress, and unresolved for required uncertainty or an empty applicable set.

Transactions support adding, removing, splitting, rebinding, changing applicability, revising criteria, routing, reordering, and subtree replacement. Intermediate transaction states may contain broken references, but the complete transaction must validate atomically. Requirements and original source phrases cannot change; altered outcomes require explicit replacement mappings. A separate label-blind audit judges semantic preservation, including invented requirements and unjustified shortcuts. Audit approval is evidence, not proof.

Complete program hashes include templates and routing. Caching conservatively invalidates the whole program after any executable change. Keys also contain evidence hashes, checker configuration, scope, dependency observations, and repeat slots. This trades some reuse for straightforward isolation and correctness.

## Feedback, search, and robustness

The adapter invokes native TextGrad 0.1.8 `StringBasedFunction` and `backward` on individual node variables. It walks queried nodes in reverse execution order and carries downstream diagnostics. A separate schema-constrained proposer translates gradients into structural transactions. This is a custom hybrid using native backward propagation and a GEPA-inspired multiobjective archive; it does not invoke native GEPA or whole-graph TextGrad TGD.

The reference label is visible to backward/proposal requests, never compiler, checker, or audit requests. Runtime transport, parse, and dependency failures remain distinct from observed visual absence. The aggregate label supplies constraints, not atomic ground truth.

There are two rounds with one then two parent batches, at most two transactions per batch. Greedy batches edit the incumbent; Pareto batches sample retained parents with replacement and a positive uniform weight floor. Both arms get six proposal opportunities. One-draw screening and five-draw confirmation archives stay separate. The seed is always retained. Seed confirmation occurs before feedback, and one new candidate can receive confirmation after each round.

Pareto objectives are agreement, coverage, minimum original-requirement consistency, fewer mean queried checks, and lower mean charged completion tokens. Requirement consistency reduces all mapped outcomes back to the immutable original ledger; additional nodes cannot inflate this score. Archives retain objective extremes and normalized-space diversity, bounded to six candidates. One-draw screening cannot establish stability; robust acceptance uses confirmation and final draws.

A qualifying leaf needs an accepted semantic audit, at least four matching labels in five fresh draws, five resolved draws, canonical requirement and assessed-node consistency at least 0.8, and confidence at least 0.8 on **every queried observation**. Three eligible draws are required to assess a reached node. Failed eligible calls count against repeat consistency. Unvisited alternatives are explicitly untested. Missing confidence fails the confidence gate without necessarily making the underlying categorical observation invalid.

`confirmed_local` is provisional. Only fresh final verification can award `locally_robust`. Other statuses and acceptance reasons distinguish unresolved execution, insufficient observations, instability, mismatch, and budget limits. A stable audited mismatch is flagged as a suspected reference conflict. Reported confidence and modal consistency do not establish atomic correctness or generalization.

## Commands and experiment protocol

```bash
.venv/bin/python -m run.calitree_robust_leaf_optimization --demo --output-dir /tmp/robust-demo
.venv/bin/python -m run.calitree_robust_leaf_optimization --preflight --output-dir logs/exps/NEW-RUN
.venv/bin/python -m run.calitree_robust_leaf_optimization --live --output-dir logs/exps/NEW-RUN
.venv/bin/python -m run.calitree_robust_leaf_optimization --live --resume --output-dir logs/exps/NEW-RUN
.venv/bin/python -m run.calitree_robust_leaf_optimization --report --output-dir logs/exps/NEW-RUN
```

Preflight does not contact a model. It freezes the first two case IDs within each class from the previous comparison manifest, source pixel groups and image hashes, code snapshots, templates, dependency fingerprints, thresholds, and budgets. There are six previously observed cases and four arms: flat–greedy, flat–Pareto, tree–greedy, tree–Pareto. The common seed and its two execution views are compiled/audited without reference labels. Each arm has separate observations and selection history. Tree and flat views can coincide when no meaningful gate is compiled; inspect actual programs before interpreting the comparison.

The live runner uses the official OpenAI endpoint, GPT-6 Luna, temperature zero, reasoning `none`, and one HTTP attempt per durable slot. Model identities are recorded from responses. No fallback model, endpoint, automatic schema repair, or failed-slot resampling is allowed. All 24 selections freeze before any final draw; final feedback never changes them.

Global ceilings are 3,600 calls and 4,608,000 completion tokens. Each case-arm has 109 search/confirmation calls and 40 final calls; shared compilation/audit uses at most two calls per case. The maximum schedule is 3,588 calls. Reserve 960 final calls and 983,040 final completion tokens before search. Checker outputs cap at 1,024 tokens; compiler, auditor, gradient and proposer outputs cap at 2,048. Failed/interrupted slots retain conservative reservations. Tokens and calls are enforced independently.

A completed pilot may be negative. A stopped provider/transport run is inconclusive and keeps its checkpoints. It must not be silently reset. After explicit restart authorization, use `--prior-attempt PATH` with a new output directory: preflight subtracts the prior ledger usage from its remaining ceiling and pins both prior manifest and budget hashes. Resume automatically recovers that linkage, rejects changed prior accounting, and never rewrites the stopped attempt. Repeats are not independent cases.

## Artifacts and verification

The run directory contains `manifest.json`, `source_snapshot/`, `prepared/`, `frozen/`, `jobs/`, `observations.jsonl`, `budget.json`, `leaves.json` when available, `results.json`, `summary.json`, `report.md`, `run.log`, and `llm-histories.log`. Frozen bundles include all candidate programs, audits, edit histories, textual gradients, objective vectors, frontier decisions, and traces. Reports preserve all six cases in denominators, including compilation failures.

```bash
.venv/bin/python -m pytest tests/unit/calitree/test_robust_leaf.py -q
.venv/bin/python -m pytest tests/unit -q
```

Tests mock provider calls, including native TextGrad backward execution and end-to-end four-arm replay. They never call the live API.

## Failure-selected harder cases

`run/calitree_robust_hard_cases.py` runs the current optimizer unchanged on three cases outside the original six-case pilot. It selects the lowest prior mean seed agreement below 0.8 from the frozen twelve-case comparison, verifies image hashes and distinct source groups, and freezes the historical ranking before new calls. The subset is intentionally difficult for prior judges, previously observed, and not class-balanced. It does not estimate generalization.

```bash
.venv/bin/python -m run.calitree_robust_hard_cases --preflight --output-dir logs/exps/NEW-HARD-RUN
.venv/bin/python -m run.calitree_robust_hard_cases --live --output-dir logs/exps/NEW-HARD-RUN
.venv/bin/python -m run.calitree_robust_hard_cases --live --resume --output-dir logs/exps/NEW-HARD-RUN
.venv/bin/python -m run.calitree_robust_hard_cases --report --output-dir logs/exps/NEW-HARD-RUN
```

It retains all four arms, five confirmation/final draws, policy thresholds, and the 109 search/40 final calls per case-arm. The smaller global ceiling is 1,800 calls and 2,304,000 completion tokens, reserving 480 calls/491,520 tokens for final verification; the planned maximum is 1,794 calls. Returned topology is measured rather than assuming a tree arm compiled multiple checks. Historical runtime snapshots remain available in each old experiment directory; strict resume requires its exact original code and configuration.

Completed harder-case results: [experiment report](experiments/calitree_robust_hard_cases.md).
