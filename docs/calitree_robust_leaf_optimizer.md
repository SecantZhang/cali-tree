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

## Missing and nested visual evidence repair

The 2026-10-08 opt-in path implements [the architecture addition](calitree_robust_leaf_optimizer_design.md#missing-and-nested-evidence-repair). It can add a missing instruction-grounded support or refine a broad support into a nested visual question. A passing parent does not imply its finer child passes. The same original requested outcome is judged from all saved support evidence; support checks do not become additional requested edits.

`nested-evidence-readout-v1` permits support checks to inspect the images with ancestor evidence as context. Its requested readout remains image-free and must acknowledge every dependency. It preserves the instruction, rubric, ledger, sole requested outcome, target/reference and applicability. A maximum of two or three supports plus one readout fits the unchanged four-check/depth cap. Every changed support needs an exact node-to-requirement source mapping in the transaction. Structural validation and a fresh label-blind semantic audit remain mandatory.

```python
from critical.core.optimization.program.robust import create_evidence_refinement_optimizer
from critical.core.decision.robust.refinement import promote_decomposition

# calls is the existing durable CaseCalls scope. original is the original
# label-free broad program; saved_decomposition is an independent-support v1 seed.
optimizer = create_evidence_refinement_optimizer(
    calls, original, checkpoint=checkpoint, selection="greedy",
)
seed = promote_decomposition(saved_decomposition)  # explicit new template/hash
result = optimizer.optimize(case, reference_label, seed=seed, budget=calls)
```

If no seed is supplied, this factory compiles a fresh label-free evidence program from the supplied original. Promotion never reuses an old audit as approval for a new contract. Export and reload use the existing v3 container, complete program hash, exact bindings and saved checker identity. Historical independent-support contracts retain their original behavior.

An audit-rejected but structurally executable parent receives at most one diagnostic program draw per hash. The stored `diagnostic` report is used for visual discovery and native TextGrad backward feedback, and is excluded from both frontiers, confirmation and acceptance. Compilation errors still produce unresolved leaves without fabricated visual feedback. Each parent batch invokes bounded visual discovery before backward/proposal work; a failed backward call is recorded and does not discard valid discovery hypotheses. The proposer sees the label and diagnostics; the discovery reviewers, compiler, checker and audit remain label-blind. Discovery gets observations, never agreement metrics, labels, gradients or prior rejection feedback.

The new runner mode is a fresh experiment, not a continuation of the completed comparisons:

```bash
.venv/bin/python -m run.calitree_forced_decomposition --preflight --chalk-only --evidence-refinement --output-dir logs/exps/NEW-REFINEMENT-RUN
.venv/bin/python -m run.calitree_forced_decomposition --live --chalk-only --evidence-refinement --output-dir logs/exps/NEW-REFINEMENT-RUN
.venv/bin/python -m run.calitree_forced_decomposition --live --resume --chalk-only --evidence-refinement --output-dir logs/exps/NEW-REFINEMENT-RUN
```

Remove `--chalk-only` to prepare the three saved cases. This runner compares broad–greedy with refined decomposition–greedy, uses the primary GPT-6 Luna model for discovery, retains 109 search and 40 final calls per case-arm, reserves final verification before search, and never spends additional allowances automatically. Preflight freezes the new templates, source hashes, images, reviewer configuration and policy; historical manifests cannot be resumed under it. `--prior-attempt` format-only continuation is incompatible with the refinement flag. Initial behavior was verified with synthetic images and mocked responses; the later [one-case live test](experiments/calitree_nested_evidence_small.md) found evidence-gap discovery but no valid executed nested insertion, and the selected decomposition failed robustness gates.

For the smaller chalk-only test, add `--small-pilot`: the cumulative ceiling is 150 calls / 192,000 completion tokens, with 50 calls / 51,200 tokens reserved for both final comparisons. The budget may stop search before full confirmation. A controlled saved-seed follow-up can explicitly promote a historical label-free seed and deduct one completed first attempt under the same ceiling:

```bash
.venv/bin/python -m run.calitree_forced_decomposition --preflight --chalk-only --evidence-refinement --small-pilot --output-dir logs/exps/NEW-SMALL-RUN
.venv/bin/python -m run.calitree_forced_decomposition --live --chalk-only --evidence-refinement --small-pilot --output-dir logs/exps/NEW-SMALL-RUN
.venv/bin/python -m run.calitree_forced_decomposition --preflight --chalk-only --evidence-refinement --small-pilot --decomposition-seed PATH-TO-SAVED-LEAF-BUNDLE --previous-small-attempt logs/exps/NEW-SMALL-RUN --output-dir logs/exps/NEW-SEEDED-RUN
```

Only the original seed is loaded, never its reference label, optimization feedback, final traces or old audit approval. A fresh audit is required. Seed/case image hashes and prior manifest/budget hashes are pinned. A provider-stopped attempt cannot be silently restarted, and a corrective attempt cannot become the parent of another automatic follow-up. The first compilation failure remains recorded; there is no failed-slot resampling or schema normalization. Compiler guidance explicitly requires an ancestor chain even for independent evidence supports, and empty support outcome IDs.

### Configuring alternative model families

The library API accepts one or two explicitly named `VisualReviewer` objects. Configure existing provider clients in caller-owned engine factories and register all alternative identities before creating the ledger. Model choices and provider credentials remain explicit; there is no automatic fallback or model substitution. The CLI above uses a single primary-model reviewer; multiple families are available through the API:

```python
from critical.core.decision.calls import DurableCalls, CaseCalls, RoutedCalls
from critical.core.optimization.program.robust import VisualReviewer, create_evidence_refinement_optimizer

# primary_factory and each route's engine_factory construct existing get_engine
# clients with explicit model/credentials, output cap, and max_http_attempts=1.
# configured_routes maps reviewer names to {"identity": {...}, "engine_factory": ...}.
# Each identity includes its explicit model, provider, family and execution settings.
ledger = DurableCalls(
    output, primary_factory, identity=primary_identity, routes=configured_routes,
    max_calls=300, max_completion_tokens=384000,
    reserve_calls=40, reserve_tokens=40960,
    scope_limits={"search": 109, "final": 40},
)
calls = CaseCalls(ledger, case.id)
reviewers = [
    VisualReviewer(name, route["identity"]["family"], RoutedCalls(calls, name))
    for name, route in configured_routes.items()
]
optimizer = create_evidence_refinement_optimizer(
    calls, original, reviewers=reviewers, checkpoint=checkpoint,
)
```

All reviewer scopes must share the same ledger and case identity. Model routes are included in frozen budget limits and durable slot hashes. Requested identities, raw findings, execution references, returned identities and usage remain in jobs/history; accepted discovery hypotheses and validation failures are also stored in optimizer lineage. Transport failures never count as absent evidence, failed slots are never retried, provider rejection stops the shared ledger, and final reservations apply across families. Findings cannot be substituted for executed observations or scored as independent votes. Different model families may share blind spots.

```bash
.venv/bin/python -m pytest tests/unit/calitree/test_evidence_refinement.py -q
```

The synthetic chalk test starts with two passing proxies and an audit-rejected seed. Native backward feedback and visual discovery propose an instruction-grounded extent check. Its negative observation establishes incomplete progress; an audited four-check program passes fresh confirmation and exact reload execution. Additional tests cover provenance/cap rejection, unknown propagation, legacy contracts, cache invalidation, two-family accounting, failed-slot replay, backward-failure recovery, reserved budgets, and freeze-before-final verification.

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

## Forced evidence decomposition

`run/calitree_forced_decomposition.py` compares the exact saved broad seeds on the three harder cases with an enforced evidence decomposition. Both arms use greedy local optimization. The opt-in guard keeps the broad control at one direct visual check, and keeps the decomposition at two or three focused support checks followed by one requested fulfillment readout. They share the exact original instruction, rubric, requirement ledger and requested outcome. Supporting facts do not become extra requested edits.

Each support independently inspects both images and reports pass/fail/unknown, evidence and confidence. All supports execute, including after negative or unknown support observations. The readout receives only their saved observations and no images; it must acknowledge every dependency in saved order. Known negative evidence is usable. Unknown required evidence makes the result unresolved. Structural guards enforce this contract on every repair before the label-blind semantic audit. The audit assesses meaningful atomic separation and whether the saved facts suffice for the original scoring rubric; its approval is evidence, not proof.

This first decomposition test uses an ordered evidence chain with all-state activation, rather than conditional shortcut branches. It changes both check granularity and the readout's access to images, so differences cannot be attributed to granularity alone. Agreement with the broad score and agreement with the reference label are reported separately. All cases were previously observed; repeats are measurements within cases.

```bash
.venv/bin/python -m run.calitree_forced_decomposition --preflight --output-dir logs/exps/NEW-DECOMPOSITION-RUN
.venv/bin/python -m run.calitree_forced_decomposition --live --output-dir logs/exps/NEW-DECOMPOSITION-RUN
.venv/bin/python -m run.calitree_forced_decomposition --live --resume --output-dir logs/exps/NEW-DECOMPOSITION-RUN
.venv/bin/python -m run.calitree_forced_decomposition --report --output-dir logs/exps/NEW-DECOMPOSITION-RUN
```

The approved full run uses GPT-6 Luna at the official OpenAI endpoint, temperature zero, reasoning `none`, and a ceiling of 900 calls / 1,152,000 completion tokens. Each of six case-arm scopes allows 109 search/confirmation calls and reserves 40 final calls; shared preparation uses at most two calls per case. The planned maximum is 900 calls. Before search, reserve 240 final calls / 245,760 completion tokens. Five fresh seed and five fresh selected executions occur only after every selection is frozen. The same single-attempt durable ledger, no-substitution rule and three-consecutive-transport-failure stop apply. Failed compilation remains a recorded unresolved arm and never supplies fabricated semantic feedback.

Artifacts retain the v3 program/leaf format with the explicit checker contract `forced-evidence-readout-v1`. To execute a saved decomposed leaf, construct `RobustExecutor(DecompositionChecker(CaseCalls(ledger, saved_scope)))`, then call `judge_program_leaf(...)` with the saved images. The controller verifies the saved checker identity, program hash and evidence hashes; the ordinary image-aware checker cannot silently replace this readout. The execution guard also requires the frozen decomposition template. Strict resume pins its exact code/template/dependency snapshots. Historical pilots remain unchanged.

If a completed forced run reveals the root-activation proposal-format failure, use a new, separately frozen format-only follow-up:

```bash
.venv/bin/python -m run.calitree_forced_decomposition --preflight --prior-attempt logs/exps/COMPLETED-RUN --output-dir logs/exps/FORMAT-FOLLOWUP
.venv/bin/python -m run.calitree_forced_decomposition --live --resume --output-dir logs/exps/FORMAT-FOLLOWUP
```

This copies only the exact prepared seeds/audits, adds explicit root-versus-child routing guidance, and deducts the completed ledger's calls and charged tokens from the original ceiling. It does not read old final traces into feedback or alter old selections. Both attempts remain separate experiments, using previously observed data. The follow-up manifest pins the prior manifest, budget and preparations and refuses changed accounting on resume. At most one follow-up is supported. The remaining global allowance can cap search below the sum of all per-scope maxima; final allowances are reserved first. Ordinary failed-slot resume still never resamples an attempted slot.

New preflights use artifact version `forced-decomposition-pilot-v2` and explicit routing guidance by default: the root has `active_on []`, children have all-state activation, and `node_order []` preserves ordering. A nonempty ordering lists every post-edit node, including unedited nodes. These proposal-format instructions do not modify aggregation or automatically repair invalid returned proposals. Completed and stopped historical attempts remain tied to their frozen source versions.

After a code update, replay a historical completed run using its exact frozen sources, rather than silently accepting the changed configuration. The original forced run includes `replay_frozen_snapshot.py`, which restores pinned sources in a temporary checkout and verifies a zero-call replay. Current-code resume intentionally rejects stale snapshots.

An explicit user request to continue after a transport stop can resume only unattempted final checks:

```bash
.venv/bin/python -m run.calitree_resume_frozen --preflight --source logs/exps/STOPPED-FROZEN-RUN --output-dir logs/exps/AUTHORIZED-CONTINUATION
.venv/bin/python -m run.calitree_resume_frozen --live --source logs/exps/STOPPED-FROZEN-RUN --output-dir logs/exps/AUTHORIZED-CONTINUATION
```

The source must be stopped by three consecutive transport failures and every case-arm selection must already be frozen. Provider rejections cannot be released. The driver copies the complete ledger, jobs, observations, frozen selections and source snapshots into a separate directory and records the explicit authorization in `continuation.json`. It releases only the transport-stop latch and consecutive-failure counter. All charges, per-scope counts and attempted slots carry forward; failed or interrupted slots are never retried. New calls remain under the original limits and a new three-failure stop. Reinvoking the same continuation never releases a second stop automatically. Existing-source changes, altered frozen assets or rollback of inherited accounting are rejected. The exact saved runtime runs in a temporary checkout; credentials are read from the original private settings, never copied into the experiment. Search stays closed, and previously failed draws remain in final metrics.

The continuation ledger includes inherited calls: subtract `initial_budget.json` when reporting incremental continuation usage. Do not add the stopped parent ledger again when calculating the combined ceiling.

Offline verification:

```bash
.venv/bin/python -m pytest tests/unit/calitree/test_forced_decomposition.py -q
.venv/bin/python -m pytest tests/unit -q
```
