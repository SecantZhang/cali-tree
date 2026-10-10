# Local leaf optimization

## Weighted fulfillment (v7)

`--scoring fulfillment` runs a fresh paired **binary versus fulfillment** comparison with Luna-only proposals/checks.
Both arms share a newly compiled label-free decomposition, use the same anchored grading observer and have independent
optimization/repeat slots. `create_fulfillment_leaf_optimizer(...)` exposes the single-case API.

Each required condition has observable 0/.5/1 fulfillment anchors. The checker returns `fulfillment_score` and
`confidence` separately; confidence never changes the fulfillment score or its weight. Code computes a protected
weighted mean: **>=.9 satisfied, <=.1 nonsatisfied, otherwise partial**. Unknown/invalid/transport-failed observations
are unmeasured intervals [0,1], never zeros. If the complete aggregate interval belongs to one label band, that label
can resolve while atomic uncertainty remains explicit and may still fail the separate confidence/robustness gates.

Requirements receive equal immutable budgets, divided equally among their initial facets. Splitting divides the
parent mass equally, preserving its root budget; models cannot supply or edit weights. Auxiliary additions have zero
weight. Only zero-weight auxiliaries can be removed. Revisions preserve the requested endpoint; anchors and bindings
can be clarified without changing numeric scale or the .9/.1 thresholds. Literal provenance and preserved mass do not
constitute semantic proof. Four checks maximum, independent flat execution, no semantic auditor or model readout.

Artifacts are `decision-leaf-v7` / `calitree-casewise-leaves-v7`, transactions `typed-fulfillment-v1`. Saved mode,
weight roots, exact rational masses, anchors, bindings, thresholds and checker template are hashed and executed directly.
Old versions retain their own contracts. Each draw also records both deterministic labels from the same observations.
The binary comparison means score 1 is fully fulfilled; all/some/none strict endpoint votes. It is an aggregation
ablation under the new grading observer, not a literal replay of the historical v6 boolean model prompt.

```bash
.venv/bin/python -m run.calitree_adaptive_leaf --scoring fulfillment --offline-demo --output-dir /tmp/calitree-fulfillment-demo
.venv/bin/python -m run.calitree_adaptive_leaf --scoring fulfillment --preflight --output-dir logs/exps/NEW-FULFILLMENT-RUN
.venv/bin/python -m run.calitree_adaptive_leaf --scoring fulfillment --live --output-dir logs/exps/NEW-FULFILLMENT-RUN
.venv/bin/python -m run.calitree_adaptive_leaf --resume --live --output-dir logs/exps/NEW-FULFILLMENT-RUN
```

The same twelve-case limits are 3,600 calls / 4,608,000 completion tokens, 107 search / 42 final calls per case-arm,
five fresh confirmation and final draws, and one label-blind transport recovery check per report. All selections freeze
before final verification. Invalid compilation remains a recorded unresolved case. Compare final draw accuracy,
all-five-correct case ratio, raw/effective coverage, score ranges, confidence, costs and same-observation readout changes.

## Endpoint repairs and transport recovery (v6)

Use `--scoring endpoints` for the corrected counting experiment, or
`create_endpoint_leaf_optimizer(...)` from `critical.core.optimization.program.robust.counting_v6`.
Saved programs/bundles are explicitly `decision-leaf-v6` / `calitree-casewise-leaves-v6`, with `typed-counting-v2`
transactions. Older v2–v5 programs retain their own execution and hashes. Counting v5 remains available as a baseline.

- Compilation prefers two or three distinct required visual endpoints. Each declares an exact instruction/rubric quote,
  aspect, positive endpoint and necessity explanation. A single irreducible condition is allowed with an explanation;
  traces explicitly report that partial is unrepresentable. Code rejects missing/invalid provenance, duplicate aspects,
  explicit progress/attempt questions, uncovered requirements and over-cap transactions. These checks do not prove semantics.
- Repair feedback identifies all-pass/all-fail partial mismatches, missed endpoints, overly strict/permissive criteria,
  unstable conditions and nonsemantic failures. Transactions predict concrete per-condition observations. Actual screen
  results and missed predictions return in later proposer feedback. Transport/schema/interruption failures are excluded
  from native node-gradient and visual-discovery observations. No semantic audit or model readout runs.
- Seed confirmation is spent only on a resolved target-matching screen. Qualification requires **5/5 target agreement**,
  **5/5 coverage**, and the existing confidence/condition-consistency gates. Final draws never reopen search.
- Each screen/confirmation/final report may replace **one transport-failed check** in a new durable slot, chosen in saved
  order without inspecting the target label. Successful, wrong, uncertain, schema-invalid and interrupted observations
  are never replaced. Every other check remains exact. Original traces, both attempts and all token charges remain saved.
  Reports show raw and effective accuracy separately. One HTTP attempt per slot and the three-consecutive-failure stop
  remain enforced. Recovery does not automatically release a stop latch.

```bash
.venv/bin/python -m run.calitree_adaptive_leaf --scoring endpoints --preflight --output-dir logs/exps/NEW-ENDPOINT-RUN
.venv/bin/python -m run.calitree_adaptive_leaf --scoring endpoints --live --output-dir logs/exps/NEW-ENDPOINT-RUN
.venv/bin/python -m run.calitree_adaptive_leaf --resume --live --output-dir logs/exps/NEW-ENDPOINT-RUN
```

The twelve-case paired protocol keeps 3,600 calls / 4,608,000 completion tokens. It reserves 1,008 calls / 1,032,192
tokens for final verification; each arm has 107 search and 42 final calls (40 normal maximum plus two recovery slots).
Luna-only and Luna→Sol use identical endpoint/runtime rules and independent observations. Stronger proposal wording does
not resolve systematic judge errors or annotation conflicts automatically. Cropping, parent learning and UI remain deferred.

## Current default: flat counting, no semantic audit (v5)

New CLI runs default to **independent required conditions** and deterministic counting:

| Observations | Overall label |
|---|---|
| Every condition passes | `yes` — satisfied |
| Every condition fails | `no` — unsatisfied |
| Some pass and some fail | `partial` |
| Any unknown, invalid or failed observation; no applicable conditions | Unresolved |

The visual model answers each condition separately. **No semantic auditor and no model-based final readout run.**
Auditing records say `disabled` / `performed: false`; they do not fabricate an approval. Structural validation still
enforces immutable instruction/requirement provenance, requested bindings, unique IDs, complete ledger coverage and the
four-check cap. Questions must express required endpoints, with pass meaning satisfied; progress/helper questions and
conditional skipped branches are not silently counted. Old evidence programs require a new label-free compilation for
this format and are never reinterpreted automatically.

Use `create_counting_leaf_optimizer(calls, original, proposer_policy="luna_only" | "luna_then_sol", ...)`.
Luna→Sol escalation after three completed stalled rounds and the existing confidence/consistency/fresh-repeat gates remain.
`locally_robust` in this mode means **empirical gates passed without semantic review**. `partial` now means a mixture of
satisfied/unsatisfied required conditions; it is not a separate model assessment of editing progress.

Saved programs use `decision-leaf-v5` / `typed-counting-v1`; saved leaf bundles use `calitree-casewise-leaves-v5`.
All decisions execute independently, including after an earlier unknown. The count is the authoritative final result and
costs zero extra model calls. Add, remove, revise and split transactions validate atomically. Semantic preservation of
model-proposed criteria is intentionally not checked by another model.

```bash
# Three synthetic, directly checked examples; no API calls.
.venv/bin/python -m run.calitree_adaptive_leaf --offline-demo --output-dir /tmp/calitree-counting-demo

# New runs use counting by default. Freezes the original 12 identities/images and new format.
.venv/bin/python -m run.calitree_adaptive_leaf --preflight --output-dir logs/exps/NEW-COUNTING-RUN

# Explicit --live performs a NEW billed experiment; no live counting pilot is implied by the code change.
.venv/bin/python -m run.calitree_adaptive_leaf --live --output-dir logs/exps/NEW-COUNTING-RUN

# The previous audited, model-readout behavior is an explicit alternative.
.venv/bin/python -m run.calitree_adaptive_leaf --scoring semantic --preflight --output-dir logs/exps/NEW-SEMANTIC-RUN
```

Existing saved experiments retain their recorded mode and frozen sources; they are not relabeled as counting runs.
Fresh counting preparation makes one compilation call per case and zero audit calls. A new live comparison needs fresh
observations and its own recorded budget; historical v4 pass/fail helpers do not establish counting-mode accuracy.

## Historical v3 runtime

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

Legacy v3 experiment configurations use two rounds with one then two parent batches, at most two transactions per batch. Greedy batches edit the incumbent; Pareto batches sample retained parents with replacement and a positive uniform weight floor. Both legacy arms get six proposal opportunities. One-draw screening and five-draw confirmation archives stay separate. The seed is always retained. Seed confirmation occurs before feedback, and one new candidate can receive confirmation after each round. The current typed optimizer uses the fifteen-round schedule described below.

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

## V4 independent evidence and adaptive proposer

The v4 optimizer fixes uncertainty propagation without changing historical saved execution. Use
`create_adaptive_evidence_optimizer(..., proposer_policy="luna_only" | "luna_then_sol")`, or the typed factory with
`protocol="typed-evidence-v2"`. An adaptive factory requires `sol_calls=RoutedCalls(primary_case_calls, "sol-proposer")`
(the typed factory calls this argument `proposer_calls`). Both routes must share the same case scope and durable ledger.

V4 saves `decision-leaf-v4` programs in `calitree-casewise-leaves-v4` bundles. `dependencies` supplies advisory context;
`required_dependencies` specifies known prerequisites. Support activation has an earlier `check_id` and explicit
`pass`/`fail`/`unknown` states. Code owns the ordered chain. Unknown advisory evidence does not block independent image
inspection; skipped or blocked questions do not automatically prevent the image-free readout from executing.

The optimizer may safely revise, insert, replace, remove, reorder or conditionally activate supports. It preserves the
requested outcome and original requirement ledger. It does not cut an instruction requirement because its answer is
uncertain. Conditional omission/removal requires a semantic audit; unvisited alternatives are reported as untested.
An executed unknown or invalid answer still fails strict robustness even when other evidence resolves the final label.

Luna performs preparation, visual checks, native TextGrad feedback, discovery and audits. The adaptive arm switches only
the proposer to Sol after three completed stalled rounds, permanently for that case. Sol uses medium reasoning without
temperature; Luna uses temperature zero/default reasoning none. Both proposal caps are 4,096 completion tokens.
Five-draw confirmation and fresh final verification must pass the original agreement, coverage, consistency, confidence
and activation thresholds before a leaf earns `locally_robust`.

```bash
# Offline synthetic example: uncertainty does not block endpoint inspection.
.venv/bin/python -m run.calitree_adaptive_leaf --offline-demo --output-dir /tmp/calitree-v4-demo

# Freeze the exact original twelve cases, settings, code and dependencies.
.venv/bin/python -m run.calitree_adaptive_leaf --preflight --output-dir logs/exps/261009-adaptive-leaf-v4

# Only this mode contacts official OpenAI; maximum 3,600 calls / 4,608,000 completion tokens.
.venv/bin/python -m run.calitree_adaptive_leaf --live --output-dir logs/exps/261009-adaptive-leaf-v4

# Resume unattempted work. Completed, failed and interrupted slots are retained.
.venv/bin/python -m run.calitree_adaptive_leaf --live --resume --output-dir logs/exps/261009-adaptive-leaf-v4

# Regenerate the report from saved results without API calls.
.venv/bin/python -m run.calitree_adaptive_leaf --report --output-dir logs/exps/261009-adaptive-leaf-v4
```

Each case-arm has at most 109 search calls and 40 final calls. Up to two shared preparation calls per case are outside
the arm scopes but inside the global ceiling. Reserve 960 final calls / 983,040 tokens before search. Budget exhaustion
can end a case before all 15 rounds. A provider rejection or three consecutive transport failures stops the whole run.
An explicit subsequent request to continue a transport-stopped run may use `--live --resume --release-transport-stop`;
this records one authorization, clears only the stop latch, and preserves all attempted slots and charges. Do not use
that flag for automatic retries or a provider rejection.

Results include exact programs, edits, audits, fresh traces/confidences, route decisions, source snapshots, per-class
metrics, model usage and a report. `selection_freeze.json` is immutable on replay. Current-code resume refuses changed
configuration, images or source hashes. Repeats remain within-case measurements, not extra examples; the data is
previously observed and all labels guide only their own leaf's fitting.

For saved inference, use `judge_program_leaf(bundle, node_id, evidence, executor, repeat="inference/fresh-0")` with
`EvidenceExecutor(EvidenceChecker(case_calls))`. The caller must retain the saved checker identity/scope and exact image
hashes. The controller dispatches v2, v3 and v4 explicitly; it never compiles a replacement or silently rebinds a leaf.

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

### Twelve-case typed comparison

`run/calitree_typed_twelve.py` compares criterion-only and nested-required on the exact frozen twelve-case collection. It verifies image hashes and distinct source groups, then compiles a common label-free seed per case with exactly two supports and one readout. This leaves one executable-check slot for insertion. The compiler's count and requirement IDs are constrained in its response schema; invalid compilation is recorded without retry or invented feedback.

```bash
.venv/bin/python -m run.calitree_typed_twelve --preflight --output-dir logs/exps/NEW-TWELVE-RUN
.venv/bin/python -m run.calitree_typed_twelve --live --output-dir logs/exps/NEW-TWELVE-RUN
.venv/bin/python -m run.calitree_typed_twelve --live --resume --output-dir logs/exps/NEW-TWELVE-RUN
.venv/bin/python -m run.calitree_typed_twelve --report --output-dir logs/exps/NEW-TWELVE-RUN
```

Two case workers share a concurrent durable ledger; HTTP calls can overlap while accounting stays serialized. Native TextGrad backward calls are serialized separately. All 24 selections freeze before final execution. The global ceiling is 3,600 calls / 4,608,000 completion tokens, including 960 reserved final calls / 983,040 tokens. Each arm allows 109 search calls and 40 final calls, with up to fifteen rounds. Resume never retries attempted slots or releases a provider/transport stop latch automatically. Code and configuration must match the frozen manifest.

The [first twelve-case attempt](experiments/calitree_typed_twelve.md) stopped at 684 calls after three consecutive TLS failures. Nine scopes froze, but no final verification occurred; confirmation success is provisional and final accuracy remains unmeasured.

After explicit authorization to continue a transport-stopped twelve-case run, use the partial-search continuation driver:

```bash
.venv/bin/python -m run.calitree_resume_typed_twelve --preflight --source logs/exps/STOPPED-TWELVE-RUN --output-dir logs/exps/AUTHORIZED-TWELVE-CONTINUATION
.venv/bin/python -m run.calitree_resume_typed_twelve --live --source logs/exps/STOPPED-TWELVE-RUN --output-dir logs/exps/AUTHORIZED-TWELVE-CONTINUATION
```

This copies the complete durable state into a separate directory and releases one transport stop. It permits unfinished fitting while keeping every existing selection frozen, including invalid-seed outcomes. Failed slots, charges, observation prefixes and per-scope limits carry forward unchanged. New calls remain inside the original ceiling and final reservation. The driver verifies image, source, program and TextGrad hashes and executes the exact saved runtime; credential settings stay outside the artifact. Reinvoking the same continuation does not release a later stop. Provider rejection cannot be released. `initial_budget.json` records inherited usage; subtract it for incremental continuation costs.

The replay adapter preserves the original failure diagnostic as well as its durable slot. This prevents error-text differences from changing downstream feedback hashes and resampling an already-attempted proposal. The continuation driver itself is hash pinned in `continuation_snapshot/`. The first continuation exposed this defect and repeated seven nested-mug proposal slots; all charges remain and that scope is explicitly flagged. It stopped at 1,413 combined calls with 17 frozen outcomes and no final draws. See the [continuation report](experiments/calitree_typed_twelve.md) for the recorded deviation and repair.

The repaired continuation also guards inherited logical slots before dispatch, stopping if their payload hash changes. Its snapshot and replay protocol are pinned independently of the unchanged scoring manifest. Inherited deviations carry forward and cannot be erased by a later successful resume. The completed twelve-case run used 2,364 combined calls. Criterion-only reference matches improved from 17 to 31 out of 60 scheduled final draws, with four locally robust leaves; nested-required improved from 16 to 24, with no leaf passing all gates. Two common seeds failed compilation. Nested comic and chalk matched 5/5 final draws but lacked qualifying confirmation after transport failures. Exact final outputs and caveats are in the [completed report](experiments/calitree_typed_twelve.md).

### Proposer-only model comparison

`run/calitree_sol_proposer.py` compares fresh Luna and GPT-6.1 Sol proposal arms on the saved jacket, paper/cup and frog seeds. Every checker, native backward call, visual-discovery call and label-blind semantic audit stays on GPT-6 Luna. Only the Sol arm's typed repair proposer uses the frozen Sol route. That route must share the primary durable ledger and case scope, so changing models cannot create an independent budget or lose failures.

Sol uses supported `medium` reasoning and omits temperature. Luna retains temperature zero and reasoning `none`. Both proposers have a 4,096-token completion cap; reasoning tokens count toward the Sol cap. This compares those two supported model configurations. Fifteen rounds, two transactions per batch, the forced-insertion constraint and all robustness gates remain fixed. Old feedback, historical audits and old observations are not supplied to the new optimizer.

```bash
.venv/bin/python -m run.calitree_sol_proposer --preflight --output-dir logs/exps/NEW-SOL-COMPARISON
.venv/bin/python -m run.calitree_sol_proposer --live --output-dir logs/exps/NEW-SOL-COMPARISON
.venv/bin/python -m run.calitree_sol_proposer --live --resume --output-dir logs/exps/NEW-SOL-COMPARISON
.venv/bin/python -m run.calitree_sol_proposer --report --output-dir logs/exps/NEW-SOL-COMPARISON
```

Global ceilings are 900 calls / 1,152,000 completion tokens, including 240 reserved final calls / 245,760 tokens. At most 45 calls use Sol. All six selections freeze before final draws. Failed slots are preserved and transport/provider stops remain latched. Model identities, source/runtime hashes, role routes, exact programs, audits, edits, observations and accounting are persisted.

The [completed proposer-only comparison](experiments/calitree_sol_proposer.md) used 739 calls, including 37 Sol requests. Sol had 9/11 transactions semantically approved versus Luna's 1/37, but selected final matches were only 1/15 versus 0/15, and neither arm produced a robust leaf. Saved traces identify unknown context blocking follow-up execution, inconclusive completion questions, and stable frog/reference disagreement. Stronger proposals alone did not repair these runtime and evidence problems.

Recommended subsequent work, kept separate from this model comparison:

1. Version the transaction format so one explicit combining rule can be provided for the complete transaction; validate that rule after all actions, without inventing missing semantics.
2. Freeze instruction-grounded complete/partial/absent definitions and require review rejections to cite the original requirement and defective program clause. Separate objective graph/coverage checks from model judgments; flag contradictory semantic reviews explicitly.
3. Allow valid existing-check repairs to qualify in production. Keep mandatory insertion as an experimental restriction, rather than making program growth a prerequisite for success.
4. Prioritize coordinated repairs of defective original checks and readout rules. An addition alone cannot repair an inconsistent foundation.
5. Report transport-unavailable evidence separately from semantic mismatch. Preserve failed-slot accounting and end-to-end coverage; evaluate a revised confirmation policy in a new artifact version rather than changing completed experiments.

### Deterministic typed evidence edits

`create_typed_evidence_optimizer(...)` enables the versioned `typed-evidence-v1` semantic proposal interface. It retains the existing v3 executable format and checker contract. `apply_typed_transaction(parent, transaction)` returns an `AppliedProgramEdit` containing the immutable program and construction details: parent/child hashes, expanded executable changes and exact requirement provenance. Search records these alongside the original typed transaction.

Each action supplies all schema fields; unused strings are empty and unused `evidence_from` is `[]`. The operation-specific fields are:

| Operation | Required semantics |
|---|---|
| `insert_support` | Existing `after`/`before` edge; unique `new_check_id`; `requirement_id`, question, criteria, binding, evidence context; explicit `readout_criteria` |
| `replace_support`, `revise_support` | Existing `target_id`; complete question/criteria/binding, requirement ID and evidence context; optional readout criteria |
| `revise_readout` | Existing readout `target_id` and new criteria |
| `remove_support` | Existing support `target_id` and explicit remaining readout criteria; revise surviving context references in the same transaction |

Code owns parent relationships, all-state activation, support/requested roles, outcome IDs and execution order. Insertion on `n2 → n3` generates `n2 → n4 → n3` and appends `n4` to readout dependencies. Replacement preserves identity/position; splitting combines replacement and insertion. Validation applies to the final compound transaction. The original ledger/outcome/binding/aggregation/template stay frozen, with at most four checks/depth four. Typed mode initially accepts all-state evidence chains. No support observation earns completion credit or receives an automatic positive interpretation.

`TypedEvidenceCompiler` accepts two or three ordered support specifications containing a requirement ID, question, criteria, binding and `evidence_from` (one-based earlier support indices). Code assigns `s1…sN` and `fulfillment`, builds ancestry, and saves the specification, expanded program and provenance in `constructions/`. Invalid output remains a retained failure, not a request for automatic repair.

`GraphValidationError` is a `ValueError` subclass with `to_dict()` providing code, message, node, dependency and relationship. Search forwards these diagnostics to subsequent proposals. Missing dependencies and sibling consumption are distinguished from depth, cycles and semantic rejection.

```python
from critical.core.optimization.program.robust import create_typed_evidence_optimizer

optimizer = create_typed_evidence_optimizer(
    calls, original, profile="nested-required", checkpoint=checkpoint, max_rounds=15,
)
result = optimizer.optimize(case, reference_label, seed=saved_seed)
```

Profiles are `general`, `criterion-only`, and `nested-required`. Criterion-only rejects structural actions. Nested-required may explore criterion intermediates, but selection requires a new support with ancestor evidence context; without one it reports structural failure and retains the seed. Confirmation shortlisting also respects that constraint. Legacy factories and saved programs retain their behavior.

Fresh one-case runner:

```bash
.venv/bin/python -m run.calitree_typed_evidence --preflight --output-dir logs/exps/NEW-TYPED-RUN
.venv/bin/python -m run.calitree_typed_evidence --live --output-dir logs/exps/NEW-TYPED-RUN
.venv/bin/python -m run.calitree_typed_evidence --live --resume --output-dir logs/exps/NEW-TYPED-RUN
.venv/bin/python -m run.calitree_typed_evidence --report --output-dir logs/exps/NEW-TYPED-RUN
```

The current runner uses the original saved three-check chalk seed, a separate label-free ordered compilation probe and one fresh shared seed audit. Both greedy arms have independent observations and up to **fifteen repair rounds**, one parent batch and at most two transactions per round (thirty proposal opportunities). Five fresh confirmation and final draws retain the current thresholds. Local robustness additionally requires complete qualifying confirmation; the nested arm must execute its added evidence-context check at least three times. Both selections freeze before any final call.

A failed confirmation becomes the next repair parent, with its five-draw report and explicit rejection reasons forwarded to the proposer. This includes an added check that consistently passes while the full program remains mismatched. If no distinct valid repair is proposed, search keeps that failed parent for subsequent rounds. Repeated unchanged candidates are recorded as duplicates and are not resampled for another chance at acceptance. Empty or rejected proposals do not terminate search early.

Search stops when a semantically audited, structurally eligible candidate passes all complete confirmation gates, when fifteen repair rounds complete, or when an enforced budget/provider stop is reached. Confirmation success is provisional; fresh final verification still determines local robustness and cannot reopen optimization. `max_rounds` accepts 1–15. Optional `stop_on_confirmation=False` permits an explicitly configured full-round exploration; legacy factories retain their original two-round behavior. Lineage records planned batches, rounds started/completed and whether a parent was selected for failed-confirmation follow-up.

The approved ceiling is 300 calls / 384,000 completion tokens: 109 search calls per arm, two shared calls and 80 reserved final calls / 81,920 tokens. It uses GPT-6 Luna, temperature zero, reasoning `none`, one HTTP attempt per durable slot and no substitution. The manifest pins the pushed checkpoint SHA, saved seed, images, sources, templates and dependencies. Historical failures/proposals are preserved; no older experiment is resumed under the new protocol.

The fifteen-round limit does not raise those allowances: a round includes backward/discovery, proposal, audit, screening and possibly confirmation calls, so the budget may end search before all fifteen rounds. New manifests use `typed-evidence-chalk-pilot-v2` and freeze the full schedule and stopping/follow-up settings. The saved two-round live run remains unchanged and must be replayed with its frozen runtime. No live experiment was run during the scheduler implementation itself.

The later [same-case fifteen-round rerun](experiments/calitree_typed_evidence_15_rounds.md) used 224 calls. Nested-required qualified in round four and matched the partial reference in 5/5 fresh final draws; its added check returned fail in every draw, identifying photographic detail beneath the chalk-like treatment. Criterion-only completed eleven rounds, exhausted its search allowance in round twelve, and matched 0/5 final draws with 3/5 resolved coverage. Both actual completed rounds and stop reasons are reported; this was not fifteen completed rounds per arm.

The [fresh live report](experiments/calitree_typed_evidence_chalk.md) records 140 calls. The inserted `n4` check executed in all five final draws with correct ancestry and consumed evidence, but the nested program matched the partial reference in 0/5 draws; criterion-only matched 2/5, with three unresolved draws. Neither qualified. The separate live compilation probe returned only one support and was rejected. Mechanical construction success is reported separately from scoring correctness.

### Alternative reviewer families

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
