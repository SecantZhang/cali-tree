# CaliTree decomposition strategies

All two-way implementations now live in **`decomposition_twoway.py`**. The
standard modular workflow exposes structured `DecompositionTwoWay` and image-pair
`DecompositionTwoWayVision`. Grounding, intent, inventory, executable aggregation
and visual calibration remain opt-in research classes in the same module. The
former `decomposition_twoway_*.py` files have been removed. Import classes from
the decomposition package or this module, and parsers from this module.

## Image-pair strategy

`decomposition_twoway.py` implements `DecompositionTwoWayVision` for real
source/edited image pairs. It uses open-vocabulary natural-language conditions
rather than restricting edits to scalar color/shape/count/left-right properties.
It is an experimental strategy; use the real-data experiment reports to assess
ground-truth agreement, not schema validity alone.

1. Compile the optimized rubric into classified units referencing every nonempty
   source line exactly once. The runtime reconstructs their text verbatim and
   restores original order, retaining exceptions and decision boundaries.
2. Decompose only the instruction into observable requirements with target,
   reference, and verbatim source phrase. Actions, additions/removals, style,
   distances and arbitrary relations are supported. Empty plans and omitted
   source content words are rejected. Source-span coverage checks text retention;
   it does not mathematically prove semantic equivalence.
3. Check each requested condition separately against SOURCE and EDITED, returning
   complete/partial/absent/unknown and explicit before/after observations. Checks
   receive no grading rubric, target annotation, case ID or overall label.
4. Independently inspect preservation, reporting scene continuity and severity
   of visible unrequested changes. Necessary effects of the requested edit are
   not supposed to count as unrequested changes.
5. Apply the verbatim rubric units to the findings using a model aggregator.
   It receives no images or ground-truth labels, and cites condition/rubric IDs.
   This strategy uses model aggregation, not the bounded deterministic DSL.

```python
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayVision

algorithm = DecompositionTwoWayVision(engine)
result = algorithm.evaluate(
    algorithm.compile(optimized_prompt),
    instruction="Remove the small gray metallic cylinder",
    evidence={"source_image": source_path, "edited_image": edited_path},
)
print(result.label, result.rationale, result.trace)
```

`judge()` accepts an instruction in `instruction` or `input.instruction` and
either the evidence mapping above, `images=[source_path, edited_path]`, or native
Aurora loader fields `input.source_image_path` and `output.edited_image_path`.
Other sample metadata and human annotations are not forwarded to the model.
Its returned label/rationale can be passed to existing CaliTree judge callbacks.
`observe()` and `aggregate()` are public stages, allowing observation failures
to be distinguished from policy/aggregation failures. `SemanticRubric` artifacts
bind the source hash and validate their verbatim units when loaded.

Five packaged templates live in `calitree_decomposition_vision_v1/`. Engines for
text and vision may be injected separately. Run-scoped checkpoints bind stage,
template text, model/settings, exact payload and both image byte hashes. Only
validated outputs are cached. Use separate runs/stores for independent repeats.
At most one schema repair is permitted; ground-truth labels never trigger a retry.

The two optional research variants, `review=True` and
`resolve_disagreements=True`, add an instruction audit/observation review or a
visual resolution of independent holistic/decomposed judgments. They are disabled
by default. The initial fifty-task experiments found lower accuracy for both;
their implementation and traces are retained for research, not recommended as
improvements. Review returns condition IDs; the runtime keeps the original
condition objects. Resolution verifies the image hashes and never receives target
annotations. The additional templates are `audit_instruction.txt`,
`review_observations.txt` and `resolve_disagreement.txt`.

Quoted instruction source text is normalized only for casing by copying from the
actual instruction. Lexical coverage allows connectors and a question wrapper,
but rejects omitted actions, targets and negation. This remains a source-coverage
check, not a proof that generated requirements preserve every semantic nuance.

Current real-data development results and limitations are recorded in
`tests/unit/calitree/reports/vision_decomposition_progress_20260926.md`.

## Source-grounded image-pair strategy

`decomposition_twoway.py` implements `DecompositionTwoWayGrounded` as a
subclass of the image-pair strategy. After instruction decomposition, an extra
stage sees only SOURCE and binds each condition to the relevant target/reference,
its initial state, and whether it is visible. These source bindings are supplied
to the subsequent image comparisons, preservation check, and aggregation. The
edited image cannot influence this initial target identification.

```python
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayGrounded

algorithm = DecompositionTwoWayGrounded(engine)
result = algorithm.evaluate(algorithm.compile(optimized_prompt), instruction,
                            {"source_image": source_path, "edited_image": edited_path})
```

The grounded templates live in `calitree_decomposition_grounded_v1/`. Instruction
conditions retain the entire original instruction as their verbatim source quote;
requirements are still generated individually. Grounding is an experimental
strategy: it can still misidentify objects or hallucinate visual changes.
Its first 64-case development ablation scored 46/64, versus frozen original
44/64 and optimized 43/64. On a second untouched, source-disjoint 64-task set,
it scored 54/64 versus original 51/64 and optimized 50/64, with no invalid
outputs. The gain is small and statistically uncertain; ten mismatches remain.

## Instruction intent and edit scope

`decomposition_twoway.py` implements `DecompositionTwoWayIntent`, another
experimental source-grounded subclass. Before generating conditions it parses
the instruction alone into operations with separate target selectors, explicit
quantity, requested delta, and permitted effects. No rubric, images or annotations
enter this scope stage. Conditions, image checks, preservation, and aggregation
share that interpretation; the original instruction remains authoritative.

For example, "remove four green hats with feathers" identifies the hats using
color and feathers but requests removal of the whole hats. "Remove the feathers
from four hats" requests a different change. The scope stage also distinguishes
movement from addition and necessary movement/style effects from unrelated edits.
It records linguistic ambiguities rather than adding unstated constraints.

`scope(instruction)` returns validated operation data, cached by instruction and
template/model settings. Scope and before/after facts remain in the final trace.
There is no hand-written label reducer. The existing verbatim optimized-rubric
aggregator still decides the label. Development scored 55/64 against grounded
54/64. A third untouched 64-task comparison scored intent 46/64, grounded 44/64,
optimized 42/64, and original 45/64. The gains are small and statistically
uncertain, with 18 intent mismatches remaining. This variant has not established efficacy;
review and holistic resolution combinations are rejected as unvalidated.
Its templates live in `calitree_decomposition_intent_v1/`.

```python
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWayIntent

algorithm = DecompositionTwoWayIntent(engine)
result = algorithm.judge(optimized_prompt, native_aurora_sample)
```

## Instruction-blind image inventory

`decomposition_twoway.py` implements `DecompositionTwoWayInventory`
as an experimental intent-scope subclass. It first describes SOURCE without the
instruction or rubric, then uses that description during SOURCE-only target binding.
It separately describes EDITED afterwards. Independent object features, counts,
alternative identifications, and uncertainty are supplied to the image comparisons,
preservation check, and original rubric aggregation. No caption is treated as
ground truth, and image-local IDs are not treated as correspondences.

The input/output callback contract is unchanged. `observations.image_inventory`
contains both descriptions in the final trace. Within-run inventory caches depend
on image bytes and template/model settings, so changing an instruction does not
recompute an unchanged image inventory. Missing inventories or changed image
contents block aggregation. Extra observation context cannot override the original
rubric or findings. Templates live in `calitree_decomposition_inventory_v1/`.

The initial development experiment scored 47/64 with zero invalid outputs,
versus intent scope's 46/64 on the same previously evaluated AURORA cases. It
still makes visual count and source-object correspondence errors. This small
net gain does not establish reliable efficacy; the strategy remains opt-in.
Use the complete real-data reports, and distinguish reused development cases
from fresh validation.

## Executable rubric strategy

`decomposition_twoway.py` implements `DecompositionTwoWayExecutable`
as a source-grounded subclass. `compile()` returns `ExecutableRubric`, containing
the verbatim source units and a model-generated program of boolean questions,
ordered rules, and an explicit default label. Questions and label boundaries
come from the optimized rubric alone. Source citations and decision/exception
coverage are required, but do not prove semantic equivalence.

`aggregate()` independently checks each question against the image observations,
without images, human labels, other question results, or candidate predictions.
`executable_policy.py` then evaluates `all`, `any`, `not`, and predicate references
using three-valued logic. The first true rule selects the output. Unknown results
that could change precedence block execution rather than silently become false.
There is no fixed mapping from fulfillment/preservation to labels. Unsupported
expressions, missing evidence, or malformed programs raise `ValueError`.

The callback and image inputs are the same as for source grounding. Compiled
artifacts support `to_dict()` and `ExecutableRubric.from_dict()` with source hash
and program validation. Holistic disagreement resolution is not supported for
this strategy. The packaged compiler and predicate templates live under
`calitree_decomposition_executable_v1/`.

This is an experimental aggregation ablation, not a selected improvement. On
earlier frozen source-grounded image findings, it scored 45/64 versus the original
source-grounded aggregation's 46/64 after compiler coverage repair. The one missing
observation was preserved as invalid in both. Deterministic execution corrected
some aggregation mistakes but did not improve net accuracy; see the progress
report for the complete traces and limitations.

Offline isolation/coverage/cache tests are in `test_decomposition_vision.py`.
Real AURORA experiments are in `test_twoway_vision_aurora.py`; development uses
seven cached substantive rewrites, validation uses 50 fixed disjoint tasks,
including 15 substantive cached rewrites. All images were verified against the
public authors' archive. Tests preserve reports before asserting ground-truth
agreement; a capability or quality failure is retained rather than hidden.

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_twoway_vision_aurora.py::test_vision_decomposition_aurora_development --calitree-live --calitree-model gpt-5.4-mini --calitree-max-tokens 4096 -v -s
```

## Structured-evidence strategy

The core two-way algorithm is in **`decomposition_twoway.py`**. Future algorithms
belong in sibling files named **`decomposition_<name>.py`**, such as
`decomposition_example.py`, and implement `DecompositionAlgorithm` from
`decomposition_base.py`. There is no hard-coded grading reducer in this package.

| File | Responsibility |
|---|---|
| `decomposition_base.py` | Abstract strategy, rubric compiler, instruction compiler, and condition evaluator contracts |
| `decomposition_twoway.py` | Structured/vision coordination, optional research subclasses, checks, traces, and CaliTree judge callbacks |
| `components.py` | Default model-backed compilers and isolated structured-value evaluator |
| `models.py` | Conditions, intent plans, atomic results, and final results |
| `policy.py` | Validated data-only rule language, persistence, and veto/base/cap execution |
| `prompts.py` | Load versioned prompt templates from package resources |

The templates live under
`critical/core/prompts/templates/calitree_decomposition_v1/`: `compile_policy.txt`,
`decompose_instruction.txt`, and `check_condition.txt`. They preserve the exact
prompts used by the preceding real-model experiments. Package data includes them.

## Two-way execution

1. Compile the rubric into supported checks, fixed criteria, guards, definitive
   vetoes, base decision rules, and conditional caps. Only the rubric is supplied.
2. Parse the instruction into requested conditions and scoped permissions. Neither
   evidence nor target labels is supplied.
3. Select the applicable checks. Fixed rubric criteria take precedence for their
   keys; unrequested checks do not contribute. A permission exempts only its
   corresponding guard, and that exemption is traced separately.
4. Check each condition independently. The default evaluator receives only the
   condition and its single observed value, returning `satisfied`, `violated`, or
   `unknown`. Identical requests are deduplicated.
5. Execute the generated policy deterministically: first matching veto, then the
   first matching base rule/default, then caps that can only lower the result in
   the order `no < partial < yes`. Return a label, rationale, and decision trace.

The language currently supports color equality/permitted light/dark shades, shape
equality, left/right-of-reference position, exact/minimum nonnegative counts, and
recognizability/identity/background guards. Unsupported rubric semantics raise
`UnsupportedDecompositionError`. Missing evidence or malformed outputs raise
`ValueError`; the algorithm does not invent a final label or silently change modes.
Historical flat policies can be loaded for inspection; the current model compiler
requires a staged policy.

## Use the algorithm

Supply an existing logged engine exposing `generate(prompt, system=...)`:

```python
from critical.core.optimization.prompt.calitree.decomposition import DecompositionTwoWay

decomposition = DecompositionTwoWay(engine, concurrency=4)
policy = decomposition.compile(rubric)
result = decomposition.evaluate(
    policy,
    instruction="Make the objects exact red. Keep identity and background unchanged.",
    evidence={
        "color": "red",
        "subject_identity": "preserved",
        "background": "preserved",
        "content_recognizable": True,
    },
)
print(result.label, result.trace)
```

For samples, `judge(prompt, sample)` and `judge_many(prompt, samples)` return the
existing `label`/`rationale` callback contract. A sample has a natural instruction
in `instruction` or `input.instruction`, plus a structured `evidence` mapping.
Other sample fields, including metadata and any annotations, are not forwarded.
Those callbacks can be injected into the existing builder:

```python
builder = CaliTreeBuilder(
    judge=decomposition.judge,
    judge_many=decomposition.judge_many,
    optimize=optimize,
    extract_components=extract_components,
    embed=embed,
    merge_prompts=merge_prompts,
)
```

This makes optimization, merge validation, root selection, and later judging use
the same decision implementation. Every new prompt is compiled independently;
rewriting/merging a prompt cannot reuse another prompt's compiled policy.
The module does not enable a new default mode in the UI/workflow executors or
modify the existing prompt-tree schema. The default evaluator consumes explicit
structured values; image-only samples need a separately validated evidence adapter.

## Persist and resume

```python
import json
from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree.decomposition import CompiledPolicy

decomposition = DecompositionTwoWay(
    engine, checkpoint=CheckpointStore(run_dir / "decomposition.jsonl"),
)
policy = decomposition.compile(rubric)
policy_path.write_text(json.dumps(policy.to_dict()))
restored = CompiledPolicy.from_dict(json.loads(policy_path.read_text()))
result = decomposition.evaluate(restored, instruction, evidence)
```

Artifacts include a format version, source rubric, SHA-256 of that rubric, and
validated rules. Exported dictionaries are defensive copies. Checkpoint keys
include the component, schema/template version, exact template text, engine/model,
and actual input. Instruction cache entries depend only on intent; atomic entries
depend on the condition and observed value. Only valid outputs are persisted.
Keep checkpoints scoped to a run; repeated robustness measurements require a
fresh instance and store to avoid collapsing draws through memoization.

Both compilers permit at most one schema repair (`schema_retries=0` disables it).
Schema attempts are recorded on `rubric_compiler.attempts` and
`instruction_compiler.attempts`. Unsupported semantics and incorrect decisions
do not trigger quality retries; atomic output errors are reported immediately.

## Extend the implementation

To replace one part of the existing two-way algorithm, subclass `RubricCompiler`,
`InstructionCompiler`, or `ConditionEvaluator` and inject that component:

```python
decomposition = DecompositionTwoWay(
    engine,
    condition_evaluator=MyConditionEvaluator(),
)
```

A custom evaluator returns `ConditionResult`. Its default `cache_key` includes
the complete evidence context, so equal scalar values from different contexts are
not conflated. Override it only when the omitted context is irrelevant.

For a different overall algorithm, implement the four abstract methods in
`DecompositionAlgorithm`: `compile`, `decompose`, `evaluate`, and `judge`. Put the
implementation in `decomposition_example.py`, export it from `__init__.py`, and
inject its judge callbacks into CaliTree. `judge_many` has a default implementation
that can be overridden for batching. Shared data types and policy execution are
available to reuse; strategy-specific orchestration stays in its named file.

## Verification

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_decomposition_module.py tests/unit/calitree/test_staged_policy.py -q
```

The module tests replay the exact recorded real-model inputs/responses for all
8 simple, 29 harder, 20 stress, and 40 unseen cases. They compare complete
judgments/traces, verify checkpoint resume without model calls, and exercise the
existing builder callbacks. These replays validate the implementation move;
they are not new model-quality experiments. Separate checks cover schema repairs,
invalid outputs, unsupported rubrics, cache separation, persistence integrity,
and custom evaluator context.

## AURORA output image boundary

The pinned human-ratings release contains source-left/output-right comparison
images for three Something-Something editors. Dataset setup now extracts the
right output panel losslessly and preserves raw images and crop provenance.
`AuroraBenchLoader` rejects legacy metadata exposing those comparison composites;
rerun setup on the dataset root to regenerate normalized metadata. This belongs
at the dataset boundary rather than in a decomposition algorithm.

For frozen experiments, `--calitree-aurora-output-panels` enables the same release
adapter for all arms. Cached direct predictions are reused only for exactly
unchanged inputs. On the previously evaluated 64-case I cohort, normalized intent
decomposition scores 47/64 with zero invalid outputs, versus original 44/64 and
optimized 41/64. It corrects the coaster false positive but leaves 17 mismatches.
These are development results; old full-composite scores remain separate.

## Opt-in image-backed grading and visual calibration

`decomposition_twoway.py` implements
`DecompositionTwoWayCalibratedVision`. It reuses the intent strategy's lossless
rubric compiler and instruction-only scope/condition compiler. It then checks
all conditions and grades the query image pair in one vision call. Those findings
are generated jointly with the decision; they are not independent observations.
Use `compile`, `decompose`, `evaluate`, or the normal `judge`/`judge_many` callbacks.
The separate parent `observe`/`aggregate` stages are intentionally unsupported
because they would bypass this strategy's image-backed grading.

Training references are optional. `VisualReference` contains an instruction,
its generated condition requirements, source/edited paths, a human label and its
0–2 mean score. `VisualReferenceBank` fits TF-IDF on training instruction and
requirement text only and retrieves one example per label, with distinct source
pixels. Query-source duplicates are excluded, including differently encoded
copies. A bank's image files must remain unchanged after fitting. Dataset splits,
annotation provenance and output-panel normalization belong to the caller/data
adapter; the core strategy does not infer them from filenames.

```python
from critical.core.optimization.prompt.calitree.decomposition import (
    DecompositionTwoWayCalibratedVision, VisualReference,
)

# Build references from a separate human-annotated training split.
# Each reference uses that split's generated condition requirements.
algorithm = DecompositionTwoWayCalibratedVision(engine, references=training_references)
policy = algorithm.compile(cached_optimized_prompt)
result = algorithm.evaluate(policy, edit_instruction, {
    "source_image": source_path,
    "edited_image": edited_path,
})
```

Omitting `references` runs the matched no-reference arm. Neither mode receives a
query human label. Generic reference IDs and explicit SOURCE/EDITED and
REFERENCE/QUERY markers appear immediately before every image. Cache keys include
prompt, full payload, model/settings and actual image contents. Resumed grading
responses are revalidated. One schema repair is allowed; quality failures do not
trigger retries. The exact experiment prompt is versioned under
`calitree_decomposition_calibrated_v1/aggregate_visual.txt`.

On 32 previously untouched sources, original/optimized/intent each scored 26/32;
both image-backed arms scored 28/32 with no invalids. References improved class
coverage but did not improve raw agreement over their matched control. The
cohort contains 25 no, six partial and only one yes example, so the 86.2% balanced
accuracy of the reference arm has limited support for full-success recall.
Four mismatches remain. This is an experimental option, and existing defaults
are unchanged. See the detailed validation report in
`tests/unit/calitree/reports/visual_calibration_holdout32_20260926.md`.
