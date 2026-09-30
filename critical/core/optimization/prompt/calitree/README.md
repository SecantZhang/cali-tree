# Extending CaliTree

`CaliTreeBuilder` assembles components behind abstract templates. Its defaults
preserve the existing callback API, saved `calitree-v2` tree format, validation
guards, timeline events, and inference through `route_prompt`.

## Components

| Package/module | Template | Default behavior |
| --- | --- | --- |
| `node/` | `NodeFactory` | Creates `CaliTreeLeafNode`, `CaliTreeMergeNode`, promoted leaves, and a shared `CaliTreeNode` global fallback |
| `optimization/` | `PromptOptimizer` | Validate, format feedback, rewrite, and repeat up to `max_steps` |
| `optimization/` | `LeafOptimizer` | Delegates leaf specialization to the shared prompt optimizer |
| `clustering/` | `ClusteringAlgorithm` | Semantic complete-link, or behavioral ranking with lazy transfer probes |
| `merge/` | `MergeAlgorithm` | Converts the existing `merge_prompts` callback into a `MergeProposal` |
| `merge/` | `MergeAcceptancePolicy` | Covered accuracy and balanced generalization guards |
| `root/` | `RootSelector` | Held-out root selection and additive accumulation |
| `routing_calibration.py` | `RoutingCalibrator` | Calibrates parent-to-child thresholds from instruction geometry |
| `decomposition/` | `DecompositionAlgorithm` | `DecompositionTwoWay` compiles rubric and instruction separately, checks conditions, and executes generated rules |

Leaf and merge subclasses inherit the shared node dataclass constructor and
serialized fields. Promoted leaves retain `status="promoted"`; accepted merge
nodes use `status="accepted"` or `"partial"`. To introduce a node subclass,
subclass `DefaultNodeFactory` and override the relevant construction method.

The builder owns grouping, embedding batches, merge scheduling and budgets,
topology updates, promotions, progress reporting, and final serialization.
Components own their algorithms. Prompt text templates still live in
`critical/core/prompts/templates/` and are supplied through existing callbacks.

## Default construction

This small example runs without a model provider. Replace its callback functions
with your application's judge, optimizer, extraction, embedding, and merge calls.

```python
from critical.core.optimization.prompt.calitree import CaliTreeBuilder, route_prompt

callbacks = {
    "judge": lambda prompt, sample: {"label": "yes", "rationale": "demo"},
    "optimize": lambda prompt, feedback: prompt,
    "extract_components": lambda prompt: {"criteria": [prompt]},
    "embed": lambda texts: [[1.0, 0.0] for _ in texts],
    "merge_prompts": lambda left, right: {"prompt": left + "\n" + right},
}
samples = {
    "a": {"input": {"instruction": "change the background"}},
    "b": {"input": {"instruction": "change the lighting"}},
}
targets = {"a": "yes", "b": "yes"}

builder = CaliTreeBuilder(**callbacks)
tree = builder.build(initial_prompt="Judge semantic consistency.",
                     samples=samples, targets=targets)
selected = route_prompt(tree, [1.0, 0.0])
```

All component arguments are optional and keyword-only. An injected instance
takes precedence over default component selection. Without injection,
`clustering_algorithm="semantic_complete_link"` or `"behavioral_complete_link"`
selects the existing implementations. Legacy parameters still undergo their
existing validation. Saved configuration retains its existing shape; Python
component selection belongs in the experiment's construction code.

## Custom leaf optimization

`LeafOptimizer.optimize(prompt, ids, context)` returns an `OptimizationResult`.
Replacing it changes leaf specialization while leaving the warm start and merge
refinement with the shared `PromptOptimizer`.

```python
from critical.core.optimization.prompt.calitree import LeafOptimizer, OptimizationResult

class EvaluateOnlyLeaf(LeafOptimizer):
    def optimize(self, prompt, ids, context):
        accuracy, correct_ids, predictions = context.services.validate(
            prompt, ids, context.samples, context.targets,
        )
        return OptimizationResult(prompt, accuracy, correct_ids, predictions, steps=0)

builder = CaliTreeBuilder(**callbacks, leaf_optimizer=EvaluateOnlyLeaf())
```

To change refinement across warm starts, default leaves, and merge proposals,
implement `PromptOptimizer.optimize(..., services=..., max_steps=...)` and pass
`prompt_optimizer=...`. The builder's `_optimize_for_cases` delegation remains
available for existing instrumentation.

## Custom merging with the existing guards

`MergeAlgorithm.propose(left, right, context)` returns a `MergeProposal`.
Synthesis and acceptance are independent: a new synthesis algorithm automatically
uses the shared prompt optimizer and `GuardedMergeAcceptance` unless those are
also replaced.

```python
from critical.core.optimization.prompt.calitree import MergeAlgorithm, MergeProposal

class CombinedRubricMerge(MergeAlgorithm):
    def propose(self, left, right, context):
        return MergeProposal(prompt=left.prompt + "\n\n" + right.prompt)

builder = CaliTreeBuilder(**callbacks, merge_algorithm=CombinedRubricMerge())
```

Return `MergeProposal("", conflict=True, conflict_reason="...")` to retain both
branches. An empty prompt also counts as a conflict. A custom
`MergeAcceptancePolicy.evaluate(optimization, covered_ids, context)` returns a
`MergeDecision`; rejected decisions can supply a timeline `kind` and diagnostics.
The coordinator handles equivalent static-prompt pruning and returns a
`MergeResult`; the builder applies the result to the tree.

## Context and remaining extension points

`BuildContext` supplies training and validation datasets separately, callback
services, a snapshot of validated component settings, node and embedding maps,
warm-start results, and the shared timeline. Default implementations keep probe
and rejection-cache state in this per-build context, so component instances can
be reused. `context.optimize_cases` delegates to the shared optimizer and returns
the legacy five-element tuple; wrap it with `OptimizationResult(*...)` when needed.

- **Clustering:** implement `score` returning `PairScore`. Override `prepare` and
  `refresh` for behavior profiles, `probe` for expensive candidate checks, or
  `pairs` for a different pairing algorithm. Inherited pairing preserves semantic
  premerge restrictions, blocked pairs, and deterministic greedy selection.
- **Root selection:** implement `select(context, accepted_merges=...)` returning
  `RootSelection(prompt, source, accumulated_node_id, report)`. Its source becomes
  the `global:<source>` ID. The report can supply `<source>_fit_accuracy` or
  `<source>_validation_accuracy`; otherwise the builder retains its existing
  accuracy fallback. An accumulated node ID must identify a node in the context.
- **Routing calibration:** implement `calibrate(nodes, case_embeddings, margin=...)`
  and update node thresholds in place. `route_prompt` continues to consume the
  serialized tree.

Existing imports from the package, `calitree.model`, and `critical.core.calibration`
remain available. The component templates, defaults, context, and result types
are also exported from the CaliTree package.

## Two-way decomposition

The core implementation is in `decomposition/decomposition_twoway.py`, with its
abstract contract in `decomposition/decomposition_base.py`. Future strategies
follow the `decomposition_<name>.py` naming convention. The strategy exposes judge
callbacks compatible with the existing builder, replaceable compilers/evaluators,
policy serialization, run-scoped checkpointing, and detailed decision traces.
See [the decomposition module guide](decomposition/README.md) for the API, extension
pattern, and supported structured-evidence vocabulary. Workflow defaults and the
saved prompt-tree schema remain unchanged.

## Opt-in modular trees and multi-child merges

Set `modular_mode=True` to build `calitree-modular-v1` trees with embedded policy,
instruction-plan and trace artifacts. Inject `TwoWayAdapter(DecompositionTwoWay(engine))`
or supply `decomposition_engine`; image-only cases need explicit `TwoWayVisionAdapter`.
`LeafController.build(...)` and `MergeCoordinator.merge_many(children, context)`
provide reusable operations while node dataclasses retain their existing fields.

`optimizer_plan` supports `textgrad`, `gepa`, `textgrad_then_gepa`,
`gepa_then_textgrad`, `best_of_both` and `evaluate_only`. Seeds remain candidates;
selection uses fit balanced accuracy then raw accuracy. Combined plans split a
single `max_steps` allowance and require at least two steps. Warm-start and merge
refinement use TextGrad independently of the leaf plan. Workflow engines share a
completion-token budget; Python integrations can provide `budget_available`,
`optimizer_identity`, `optimizer_usage` and bounded optimizer/reflection callbacks.

Multi-child synthesis requires `MultiMergeAlgorithm` or `merge_many_prompts`.
Increase `max_merge_children` from its default `2` for deterministic automatic
groups. Each group is synthesized once, with all prompts/policies together; it is
not folded through binary calls. Modular merges require reserved validation and
evaluate the union of descendant scopes. Rejected children and residual
assignments are preserved, and promoted accuracy is measured.

GEPA uses a package-owned RPC worker in an interpreter with `gepa==0.1.4`.
Configure `gepa_python` or use `.venv-gepa/bin/python`. Installation is explicit:

```bash
CALITREE_GEPA_PYTHON=python3.11 bash run/setup_calitree_gepa.sh
.venv/bin/python -m run.calitree_modular_demo
```

The demo accepts three children, reloads a JSON tree and executes its saved
policy entirely offline. Use `validate_tree(tree, executor)` before judging a
loaded tree with `ArtifactExecutor`. See [the complete design and configuration](../../../../../docs/calitree_structure.md)
for the portable bundle, callbacks, workflow controls and research boundaries.

## Experimental frozen decision-set observations

`FrozenCriteriaExecutor` in `decomposition/decomposition_twoway.py` executes
previously selected casewise criteria without recompilation or optimization.
It preserves unknown observations and leaves aggregation to the caller. It is
available through the decomposition package; existing strategy defaults are unchanged.

```python
from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import (
    FrozenCriteria, FrozenCriteriaExecutor, NeutralEvidence,
)

# engine, selected_prompt, instruction, and selected_plan come from your run.
# selected_plan has conditions and rubric_conflicts; each condition has id,
# requirement, source_selector, complete_when, partial_when, absent_when,
# and unknown_when. Set feedback_used to reflect the actual fitting history.
criteria = FrozenCriteria.bind(selected_prompt, instruction, selected_plan,
                               feedback_used=True, origin="saved-fit-revision")
evidence = {"source_image": "/data/source.png", "edited_image": "/data/edited.png"}
executor = FrozenCriteriaExecutor(engine, checkpoint=CheckpointStore("observations.jsonl"))

# Optional: two single-image model calls, with no instruction or grading inputs.
neutral = executor.observe_neutral([
    {"id": "q1", "property": "interaction", "object_class": "person",
     "reference_class": "curtain"},
], evidence=evidence)
# Or restore existing observations without making observer calls:
neutral = NeutralEvidence.from_dict(neutral.to_dict())

result = executor.observe(criteria, prompt=selected_prompt, instruction=instruction,
                          evidence=evidence, neutral_evidence=neutral)
# result contains checks, local_features, evidence identities, and provenance.
# It deliberately contains no final grading label.
```

Probe descriptors have fixed question renderers and stable lexical signatures;
they are not a learned concept ontology. Use generic class nouns, not desired
states. Criteria retain prompt/instruction bindings; neutral evidence retains
ordered image-byte bindings. A mismatch fails before condition calls. Labels
used to select criteria remain disclosed in provenance and are never forwarded
as a feedback field to the checker. This does not erase their influence on fitted
criteria.

Reuse the checkpoint for recovery. Use a separate checkpoint path for a fresh
repeat. Inject a budget-limited engine when running paid calls. The bounded
runner, evidence, and expansion gates are described in
[the assumption-3 report](../../../../../tests/unit/calitree/reports/assumption3_smallset_20260928.md).

The J16-specific follow-up experiments have been removed from active code.
The maintained baseline is the frozen-criteria/image-check path above, with
optional neutral observations. Experimental results remain in the historical
report; they do not add required stages to CaliTree.

## Fallible annotations and quarantine

Human-label agreement is not proof of semantic correctness. Label records may
carry `annotation_review={"status": "uncertain", "reason": "...",
"reviewed_by": "..."}` while retaining their original target. Workflow Train,
shared partitions, and Eval exclude explicitly uncertain annotations from fitting
and primary agreement metrics and expose their quarantine records. Population
prior fitting excludes them too. Official test membership remains intact in the
shared partition. An explicit `target_label="uncertain"` is quarantined too, without inventing a reviewer. Missing review metadata on ordinary grading labels is provisionally eligible `unreviewed`;
it is not certified ground truth.

Direct callers can use `annotation_quality.partition_annotations(records)` to
construct an eligible cohort, or pass `annotation_reviews={case_id: review}` to
`CaliTreeBuilder.build(...)` to reject uncertain requested fit/validation targets
before callbacks. A model mismatch is never an automatic exclusion rule. Retain
uncertain cases for adjudication, not as a fourth grading target. This is separate
from the model's unknown observations and from valid partial judgments.
