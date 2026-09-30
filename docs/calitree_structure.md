# CaliTree structure: modular leaf and multi-child merge nodes

CaliTree separates durable node state from execution. A **leaf** specializes an
input prompt with a selectable optimizer and exports its decision artifacts. A
**merge** accepts two or more leaf/merge nodes, synthesizes one joint parent, and
exports the same artifacts. Accepted parents can participate in later merges,
including groups containing leaves and parents of unequal depths.

The implementation is opt-in through `modular_mode=True`. Its portable tree
version is `calitree-modular-v1`. The default remains the legacy `calitree-v2`
callback path; the existing node dataclass fields and serialization stay intact.
Modularity is an engineering capability, not evidence of improved model accuracy.

## 1. Relationship to existing work

The design follows [CaliTree goal](calitree_goal.md), [experiments](calitree.md),
[version status](calitree_status.md), and the
[worktree comparison](calitree_worktree_comparison_report.md): specialize leaves,
compress bottom-up, retain branches when merging fails, and assess generalization
separately from fit. Existing experimental snapshots are not accuracy claims for
this implementation.

[Prompt-tree reconstruction](prompt_tree_reconstruction.md),
[AURORA reproducibility](aurora_prompt_tree_reproducibility.md), and
[prompt distillation](calibration_prompt_distillation.md) motivate exporting
executable decisions and reusable criteria rather than parsing narrative rationale
or replaying item-specific answers. A compiled representation must be measured;
compilation alone does not establish equivalence to the original prose.

The calibration hierarchy is separate from the decision program for one sample.
A leaf's atomic checks do not automatically become separately optimized tree leaves.

## 2. Package structure and APIs

```text
critical/core/optimization/prompt/calitree/
├── builder.py                    # legacy entry point and explicit modular dispatch
├── modular.py                    # modular grouping, topology, promotion and exports
├── context.py                    # services, validated settings and per-build state
├── node/
│   ├── base.py                   # unchanged durable dataclass
│   ├── node_leaf.py              # leaf/promoted-leaf state
│   ├── node_merge.py             # merge state
│   ├── factory.py                # replaceable construction
│   ├── leaf_controller.py        # LeafController.build(...)
│   └── artifacts.py              # companion snapshots and validate_tree(...)
├── optimization/
│   ├── base.py                   # PromptOptimizer and LeafOptimizer
│   ├── feedback.py               # legacy callback defaults
│   ├── composite.py              # bounded plans and measured candidate selection
│   ├── textgrad.py               # existing TextGrad adapter integration
│   ├── gepa.py                   # credential-free subprocess transport
│   └── gepa_worker.py            # package-owned GEPA 0.1.4 worker
├── decomposition/
│   ├── artifacts.py              # adapter contract and ArtifactExecutor
│   ├── decomposition_twoway.py    # structured/vision executors and research subclasses
│   ├── models.py                 # instruction plans, conditions and results
│   └── policy.py                 # compiled structured policy and deterministic rules
├── clustering/                   # pair ranking, transfer probes and grouping
├── merge/
│   ├── base.py                   # binary and native sequence synthesis contracts
│   ├── callback.py               # callback adapters and concatenation baseline
│   ├── acceptance.py             # fit and reserved-validation guards
│   └── coordinator.py            # merge(...) and merge_many(...)
├── root/                         # validated global prompt selection
├── routing_calibration.py
├── routing.py
├── evaluation.py
├── geometry.py
└── metrics.py
```

`CaliTreeLeafNode` and `CaliTreeMergeNode` hold durable results. They contain no
engines, callbacks or optimizer instances. `NodeFactory` constructs them;
controllers run algorithms; the builder owns scheduling and topology changes.

- `LeafController.build(initial_prompt, ids, context, *, node_id, semantic_groups=None)`
  returns `LeafBuildResult(node, snapshot, optimization)`.
- `MergeCoordinator.merge_many(children, context)` returns a `MergeResult` without
  changing topology. `merge(left, right, context)` retains its legacy behavior.
- `MultiMergeAlgorithm.propose_many(children, context)` synthesizes a sequence in
  one operation. Its inherited binary interface delegates to that operation.
- `ArtifactExecutor` compiles, evaluates, exports and restores the selected
  decomposition. `validate_tree(tree, executor)` checks the portable bundle and
  loads its policies before inference.

See the [package extension guide](../critical/core/optimization/prompt/calitree/README.md)
and [decomposition guide](../critical/core/optimization/prompt/calitree/decomposition/README.md)
for the underlying component contracts.

## 3. Durable state and portable decision artifacts

The tree embeds `artifacts` inside `prompt_tree`; deployment does not need the
training run's artifact directory. The bundle contains:

| Collection | Contents |
| --- | --- |
| `nodes` | Versioned companion snapshots, scope/assignment measurements, evaluation references and provenance |
| `policies` | Compiled policy payloads indexed by exact final prompt SHA-256, strategy and compiler identity |
| `evaluations` | Structured labels, rationale, instruction plans, applicable checks and execution traces |

The companion snapshot keeps the existing dataclass stable. Important fields are:

| Field | Meaning |
| --- | --- |
| `id`, `kind`, `revision` | Node identity; leaf, merge or global; snapshot revision |
| `prompt_sha256`, `policy_ref` | Exact prompt identity and authoritative compiled policy |
| `children` | Empty for leaves; every input child ID for a parent |
| `scope_ids` | Full fit scope represented by the node and descendants |
| `served_ids` | Current cases assigned to the node after acceptance/compaction |
| `correct_ids` | Cases actually measured correct over the scope |
| `evaluation_refs` | Case-to-evaluation references for plans, checks and traces |
| `fit`, `validation` | Measured fit report and, when available, routing validation cohort |
| `strategy_manifest`, `provenance` | Resolved strategy identities, candidate history and child/source lineage |

A leaf's scope is its fit group. A parent's scope is the deduplicated union of
**all** child scopes; it is never reconstructed from correct or served cases.
The legacy `covered_ids` field carries modular current assignments, while the
companion `scope_ids` preserves the full denominator.

Every rewritten prompt compiles independently. A policy binds to its exact final
prompt hash, not a normalized string. Loading rejects mismatched prompt/policy
bindings, unresolved references, duplicate children and ancestry cycles. Node
snapshots and policy payloads remain JSON-compatible, independent of Python
strategy objects.

## 4. Modular decomposition

`DecompositionAdapter` defines `inputs`, `compile`, `evaluate`, `export`, `restore`,
`identity` and `evidence_identity`. Applications can inject custom Python adapters
with their own executable policy format and data-only exports.

Both supported executors and the retained opt-in research subclasses live in
`decomposition_twoway.py`. The former suffixed modules have been removed;
imports use the decomposition package or this consolidated module.

The packaged adapters are:

| Strategy | Executor and input boundary |
| --- | --- |
| `two_way` | `TwoWayAdapter(DecompositionTwoWay(...))`: compile the rubric separately from the instruction, evaluate structured observations, then execute the compiled rules |
| `two_way_vision` | `TwoWayVisionAdapter(DecompositionTwoWayVision(...))`: compile the rubric/instruction, observe SOURCE and EDITED images, and aggregate semantic observations |

The modular Python default is structured `two_way`, constructed from
`decomposition_engine` when no adapter is injected. Structured evidence uses the
existing supported vocabulary, including color, shape, position, count,
recognizability, subject identity and background. Image-only samples require an
explicit vision adapter/strategy. Both boundaries reject incompatible or missing
evidence before any compilation/model call; labels and unrelated annotations are
removed from compiler and observation inputs.

The same executor handles optimization, transfer checks, merge acceptance, root
selection and inference. Exports use structured plans/checks/traces directly,
without recovering decisions from rationale strings. Vision review and
resolution variants are outside the initial portable adapter.

Cache identities include strategy, templates, model settings, final prompt,
instruction and allowed evidence. Image evaluation identities include image-byte
hashes, so replacing bytes at the same path invalidates observations. Checkpoints
restore valid compiled policies and measured candidates; inference uses persisted
policies with a new instruction plan and current evidence.

## 5. Leaf execution and optimization

A leaf controller:

1. Validates its nonempty, unique fit group and evidence boundary.
2. Evaluates the seed with the selected decomposition executor.
3. Runs the selected optimizer plan using only the fit group.
4. Selects a measured candidate and materializes its final decision artifacts.
5. Measures final fit accuracy, extracts clustering criteria and embeds the node.
6. Returns durable node state, its snapshot and optimization report.

The supported `optimizer_plan` names are:

| Plan | Behavior |
| --- | --- |
| `textgrad` | Existing TextGrad 0.1.8 textual-gradient update adapter |
| `gepa` | GEPA 0.1.4 reflective search in an isolated interpreter |
| `textgrad_then_gepa` | GEPA starts from the selected TextGrad candidate |
| `gepa_then_textgrad` | TextGrad starts from the selected GEPA candidate |
| `best_of_both` | Each method starts from the seed; select among independent candidates |
| `evaluate_only` | Measure and export the input prompt without optimizer updates |

All plans retain the seed. Candidate selection orders **fit balanced accuracy**,
then raw accuracy, keeping the earlier candidate on ties. A worse rewrite cannot
force a regression. Reports include candidate/stage history, allowances, usage
when supplied by the runtime, GEPA lineage and stop reason.

`max_steps` is the total proposal/update allowance for one optimization operation.
Combined plans require at least two steps. The first stage gets `max_steps // 2`;
the second gets the remainder. Warm-start and merge refinement use TextGrad by
default, independently of the leaf plan. Injected `LeafOptimizer` and
`PromptOptimizer` instances retain precedence over these defaults.

The workflow shares one optimizer completion-token budget across methods,
reflection, stages, synthesis and extraction. It checks the remaining budget
before calls and clamps call limits. Exhaustion returns the best measured
optimization candidate. A synthesis without budget preserves its children.
Compilation/observation calls are tracked separately as judge usage. Standalone
Python callers provide `budget_available`, `optimizer_usage` and an appropriate
bounded engine when they need the same budget accounting.

GEPA runs through a package-owned JSON-lines RPC worker using the actual installed
library. The worker receives case references and requests evaluation/reflection;
the parent executes those calls using its logged engines, decomposition and
checkpoints. Provider credentials are absent from the worker environment.
Reflective feedback contains leaf fit data only. Reserved validation and final
test labels never enter GEPA search. Worker errors fail explicitly; budget
exhaustion is handled by measured candidate retention.

## 6. Multi-child merge execution

A merge accepts any distinct sequence of at least two leaves and/or merge nodes,
including mixed types and unequal depths. Its depth is `1 + max(child depths)`.
All child IDs remain in lineage. Duplicate children, unresolved ancestry and
merging a node with its descendant are invalid.

Synthesis and acceptance are independent:

- `CallbackMergeAlgorithm` preserves pair callbacks for two-child operations.
- `CallbackMultiMergeAlgorithm` passes all child prompts and compiled policy
  payloads to `merge_many_prompts` in one request.
- `ConcatenateMergeAlgorithm` is a transparent baseline that joins distinct
  prompts; it still requires compilation and acceptance.
- Custom native algorithms implement `MultiMergeAlgorithm.propose_many`.

A pair-only algorithm is rejected for larger groups. Multi-child synthesis is
never an implicit binary fold. The workflow's joint synthesis template is
`calitree_modular_v1/merge_many.txt`. Policy alignment and alternative conditional
executors can be research plugins; they are not packaged defaults.

### Automatic grouping

`max_merge_children` defaults to `2`. For larger values, the clustering strategy
seeds a group with the highest-scoring eligible pair. It repeatedly adds the
candidate with the highest minimum similarity to every current member, stopping
at the size limit or threshold. Node IDs break ties deterministically. Existing
semantic restrictions apply to every pair. All pairwise transfer probes must
pass before a joint proposal is attempted.

A failed pair remains blocked. Rejection blocks that exact child group from
repeated proposals; it does not delete children or preclude different groups.
Each joint proposal counts once against `max_merge_attempts`, regardless of arity.

### Proposal, validation and assignments

1. Validate children and derive full scope `S = union(scope(child))` and current
   assignments `A = union(served(child))`, deduplicated by stable case ID.
2. Require reserved validation for modular acceptance. Without it, retain branches.
3. Synthesize once from copied child state; conflicts/empty proposals retain children.
4. Refine the proposed prompt, then compile its final policy independently.
5. Evaluate the selected executor over all of `S` and apply the existing configured
   fit objective, thresholds and reserved-validation generalization guard.
6. On acceptance, assign correctly handled cases from `A` to the new parent.
7. Promote residual assignments using their source leaf, freshly measuring their
   correctness. Preserve full scope and every child's lineage in the parent.

No accepted parent may have an empty served set. A partial merge's fit denominator
remains `S`, even after residual promotion or another partial merge. For example,
a parent correct on four of five scope cases reports 80% fit; those four current
assignments may move to it while the fifth remains on a measured promoted leaf.
The parent's later merges still account for all five scope cases.

Merge status `partial` describes incomplete fit coverage; prediction label
`partial` is a separate sample-level output. A parent is not automatically the
global fallback simply because its merge was accepted.

## 7. Python and workflow configuration

Application callbacks and engines remain injected. For example:

```python
from critical.core.optimization.prompt.calitree import (
    ArtifactExecutor, CaliTreeBuilder, DecompositionTwoWay,
    TwoWayAdapter, route_prompt, validate_tree,
)

adapter = TwoWayAdapter(DecompositionTwoWay(judge_engine))
builder = CaliTreeBuilder(
    judge=adapter.algorithm.judge,
    optimize=optimize_callback,       # e.g. the existing textgrad_update adapter
    extract_components=extract_callback,
    embed=embed_callback,
    merge_prompts=binary_merge_callback,
    merge_many_prompts=joint_merge_callback,
    modular_mode=True,
    decomposition=adapter,
    optimizer_plan="textgrad_then_gepa",
    reflect=reflection_callback,
    gepa_python=".venv-gepa/bin/python",
    max_steps=4,
    max_merge_children=3,
)
tree = builder.build(
    initial_prompt=rubric,
    samples=fit_samples, targets=fit_targets,
    validation_samples=reserved_samples, validation_targets=reserved_targets,
)

# After a JSON save/load, construct an executor with the same adapter contract.
executor = ArtifactExecutor(adapter)
validate_tree(tree, executor)
node = route_prompt(tree, instruction_embedding)
result = executor.judge(node["prompt"], new_sample)
```

GEPA resolves an explicitly configured interpreter or the repository's existing
`.venv-gepa/bin/python`. It checks Python >= 3.10 and exactly `gepa==0.1.4`, failing
clearly before fit judging if unavailable. Training never installs dependencies.
Explicit setup and the deterministic offline example are:

```bash
CALITREE_GEPA_PYTHON=python3.11 bash run/setup_calitree_gepa.sh
.venv/bin/python -m run.calitree_modular_demo
```

The example builds three leaves, accepts one joint parent, round-trips the tree
through JSON, and judges using a saved policy without models or credentials.
The sibling frozen-prompt `gepa/` package remains separate from the new optimizer.

Matching backend/frontend workflow controls expose `modular_mode`,
`optimizer_plan`, `decomposition_strategy`, `merge_strategy`,
`max_merge_children` and `gepa_python`. Merge strategy choices are
`prompt_synthesis` and `concatenate`. The workbench displays child counts,
resolved strategies, compiled policies, instruction plans, checks and traces.
Dry runs validate configuration and estimate the new stages without model calls.

The initial modular workflow supports hierarchical **replacement** specialization.
Modular/additive, modular/flat and the legacy residual cascade are explicitly
rejected. A declarative YAML registry and per-node strategy overrides are future
extensions; the current public configuration is the constructor/workflow controls
and Python strategy injection.

## 8. Inference, validation and compatibility

Routing uses instruction embeddings and permitted observable metadata, never the
unknown target. It executes the selected node's persisted policy with a fresh
instruction plan. A validated global fallback remains available, and the active
forest survives unsuccessful compression. Workflow inference dispatches by tree
version; legacy and frozen-prompt paths remain supported.

Fit and reserved-validation IDs must be disjoint. Optimization consumes fit
labels; acceptance, root selection and routing eligibility consume reserved
validation. Final test labels do not influence search or reflective feedback.
Repeated selection on reserved validation can overfit it and does not replace
final evaluation.

The portable bundle carries source bindings and compiler/strategy provenance.
Checkpoint keys include model settings and exact inputs; optimizer identity and
usage can also be supplied by Python callers. Unsupported compilation and
malformed exports fail explicitly rather than silently changing algorithms.

Legacy mode preserves its callback judging, binary merge behavior and historical
fit-only validation fallback. Modular acceptance requires reserved validation and
measures promoted leaves, avoiding the legacy perfect-score placeholder.

## 9. Offline acceptance and research extensions

Offline tests cover durable node compatibility; leaf export and checkpoint reuse;
prompt/policy invalidation; save/load and artifact inference; structured/vision
boundaries; seed retention, stage allowances and budget stops; actual TextGrad and
GEPA with deterministic parent callbacks; worker errors; validation isolation;
three-or-more children, mixed types and unequal depths; overlapping scopes,
repeated partial merges and measured promotions; deterministic grouping,
compatibility, rejection and attempt limits; workflow controls, dry runs and
workbench rendering. Frontend type checking and production build are included.

Remaining research extensions include policy-level alignment, conditional parent
executors, mixed decomposition conversion, declarative strategy registries,
per-node overrides and controlled model ablations. Compare flat, leaf-only and
merged systems under matched budgets; report raw/balanced accuracy, per-class
recall, coverage, compression, fallback rate, latency and token use. Paid model
experiments and accuracy claims are outside this implementation.

## Manual canvas nodes and frozen stages

The Criti-Cal canvas now supports `aurora_source`, `calitree_partition`,
`calitree_leaf`, and `calitree_merge` alongside automatic `calitree_train`.
Manual connections define the hierarchy; no routing hierarchy is inferred.

The local AURORA source uses `AuroraBenchLoader` with repeat, task-family, and
editor/model filters. It never downloads data, including in dry runs. Missing
metadata, splits, or images identify `./run/setup_aurora_bench.sh` as the setup
command. AURORA is also available in dataset browsing and uses the existing
source/edited image preview.

Connect AURORA's `raw_dataset` and `raw_labels` to Dataset, then Dataset's
`samples` and `labels` to the shared partition. The partition preserves official
test cases and applies the existing task-grouped training split with validation
fraction **0.25** and seed **44**. Its `partition` output carries a content-derived
identity, fit/reserved/test IDs, samples, and labels. `test_samples` and
`test_labels` feed Judge and Eval. Leaves require explicitly selected fit IDs;
reserved validation and test cases are never valid leaf selections.

Each leaf/merge publishes a portable `calitree-node-v1` artifact through `node`.
It includes the final prompt and hash, partition identity, scope/served/correct
IDs, every child identity, ancestors, depth, case fingerprints, available policy,
instruction plans, observations, predictions, optimization provenance, stage
references, and validation state. Merge's `children` socket accepts **two or more**
leaf/merge artifacts. Candidate children without policies are valid; synthesis
receives their prompts without implicitly compiling their missing policies.
Duplicate children, ancestor/descendant inputs, cycles, mismatched partitions, and
conflicting case records fail before synthesis. Scope overlap is deduplicated.

Separate `optimized_prompt`, `decision_sets`, and `calitree_report` sockets expose
requested results. `output_mode` (`raw_prompt`, `decision_sets`, or `both`) and
`run_until` are independent. A stopped optimization can publish a candidate raw
prompt without compiling a policy. Unavailable optional outputs are disabled in
the canvas; attempting to consume one produces a missing-output error. A policy
available inside a node is bound to that node's final prompt hash.

| Leaf stage | Merge stage | Persisted result |
| --- | --- | --- |
| `optimization` | `synthesis`, then `refinement` | Measured prompt candidates, selected prompt, history, budgets/usage |
| `compilation` | `compilation` | Prompt-bound compiled policy |
| `instruction_decomposition` | `instruction_decomposition` | Per-case instruction plans |
| `evidence_checks` | `evidence_checks` | Evidence-bound observations |
| `aggregation` | `aggregation` | Decomposed predictions/traces, optional raw predictions, merge baseline predictions |
| `validation` | `validation` | Fit/reserved metrics, measured correct IDs, merge acceptance |

Manual nodes default to TextGrad, `optimization_evaluator=raw_prompt`, and
explicit `decomposition_strategy=two_way_vision`. Structured `two_way` and
`optimization_evaluator=decomposed` remain selectable. Python controller defaults
are unchanged. Optimizer plans and completion-token budgets use the existing
bounded candidate-selection implementation. Merge refinement defaults to
TextGrad and shares the operation budget with joint synthesis. Optimization uses
only selected fit labels. Reserved-validation and test labels never enter
optimization/reflection. Final decomposition and raw-prompt measurements are
stored separately from optimization measurements. Merge validation evaluates the
full descendant scope and shared reserved set, applying the configured fit,
generalization-floor, and baseline-regression guards. A rejected proposal remains
inspectable and never deletes its children.

`LeafController.optimize(...)`, `MergeCoordinator.propose_many(...)`, and
`MergeCoordinator.assess(...)` expose reusable prompt-stage boundaries; existing
`build(...)`/`merge_many(...)` APIs retain their composed behavior. Decomposition
adapters expose `decompose`, `restore_plan`, `observe`, and `aggregate`, so evidence
checks can be reused independently of judgment. The canvas uses `StageRunner` to
compose these boundaries with immutable artifacts.

The secondary panel has **Data**, **Stages**, **Optimization**, **Decision Sets**,
and **Validation** views, in addition to generic Inputs/Outputs/Timing tabs. Data
provides a searchable task/case picker and image previews. Stages provides Run
through, Rerun from, Freeze, Unfreeze, and original-artifact inspection. Live
previews include stage/case progress, candidate history, plans, observations, and
predictions. Only a completed stage with an immutable artifact reference can be
frozen; previews cannot be pinned.

Freezing stores an exact stage reference in `params.stage_pins`, without locking
canvas ancestors. Completed predecessor references are saved in
`params.stage_cache`. A pinned optimization prompt can be applied to newly
selected fit data while retaining its original optimization provenance and
showing changed inputs. Compilation pins must match the prompt, strategy, and
engine/template identity. Instruction pins must match instructions; observations
must match plans, policy, and actual image bytes. Predictions and validation pins
have corresponding observation/target/guard bindings. Missing or incompatible
pins stop before model calls and identify the stage needing attention; they are
never silently regenerated.

One-shot actions use `RunRequest.stage_requests[node_id]` with `run_from`,
`run_until`, and `action` (`run`, `metrics`, or `fresh`). **Recompute metrics**
reuses completed predictions and makes no model calls. **Fresh evaluation**
reruns evidence checks and aggregation in a new cache namespace; execution-stage
pins must be explicitly unfrozen first. Each action has a persisted execution
identity so interrupted actions can resume completed stages without confusing
another fresh evaluation with that action.

Stage artifacts are content-addressed JSON under managed run storage. References
contain only run ID, node ID, stage, and digest. The artifact retrieval endpoint
validates those identities and verifies content hashes. Run results retain full
output data in managed artifacts even when their index summarizes large values.
Disk hydration and scoped seeding work after server restart; reopening a pinned
manual node restores the saved run for inspection and subsequent stage actions.

CaliTree Judge accepts exactly one of `prompt_tree` and `calitree_node`. The latter
executes that exact node's published raw prompt or persisted policy, compiling a
new instruction plan for each downstream case without re-compiling the saved
policy. `both` publishes raw-prompt inference while exposing its decision artifacts
for inspection. Candidate/rejected nodes can be judged explicitly, and their
validation state is included in the existing CaliTree Eval-compatible result.
The Train/tree path retains automatic routing.

The saved workflow `workflows/examples/calitree_aurora_canvas.json` connects
AURORA → Dataset → shared partition → three leaves → joint merge → Judge → Eval.
First run the partition, select each leaf's fit cases in its Data view, and choose
engine configurations; the template intentionally contains no guessed case IDs.
The fully deterministic implementation example is:

```bash
.venv/bin/python -m run.calitree_canvas_demo
```

It builds three leaves, accepts a joint parent, reloads its JSON artifact, and
judges through the saved policy without network calls or credentials. Research
extensions remain custom decomposition/merge adapters, automatic suggestions for
manual grouping, and paid empirical comparisons of optimization evaluators;
these are separate from the implemented canvas execution contracts.
