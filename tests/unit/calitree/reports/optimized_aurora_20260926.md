# Two-way decomposition of actual cached optimized prompts

The current module does **not** establish faithful decomposition of the cached
AURORA optimized prompts. It accepts policies and instruction plans that lose
essential semantics, and its default evaluator cannot consume image pairs.

## Experiment

Seven materially rewritten TextGrad prompts were selected from the existing
focal-only optimization run: C01, C03, C04, C07, C08, C09, C10. The three unchanged
prompts were excluded. The fixture preserves the exact prompt text, source
hashes, original rubric, human labels, and image hashes.

Each optimized prompt was evaluated on its focal image pair and the next two
other task groups in a fixed cyclic order. Each pairing received three fresh
independent model calls at temperature 0.3. Thirty original-prompt draws were
reused as comparators, alongside 63 optimized-prompt draws: **93 image calls**,
all with valid labels. Original comparator reuse does not create independent
new examples. No labels were given to the model.

The compiler and instruction probes used temperature 0. All calls used
`gpt-4.1`; the historical optimizer used `gpt-5.4-mini`. Production source and
template hashes stayed unchanged throughout the run. There was no new
optimization, substitute handwritten grading reducer, or quality retry.

| Cohort | Original | Cached optimized | Current two-way |
|---|---:|---:|---|
| Seven focal cases, three draws each | 9/21 (42.9%) | 13/21 (61.9%) | Not executable on image pairs |
| Fourteen transfer comparisons, three draws each | 17/42 (40.5%) | 18/42 (42.9%) | Not executable on image pairs |

Original/optimized label agreement was 14/21 on focal comparisons and 30/42 on
transfer comparisons. These small selected cohorts and repeated draws do not
establish a general improvement. Transfer tasks were excluded from each
focal-only optimization search, but come from an existing selected diagnostic,
not a new representative dataset. Scores from this model are not directly
comparable with historical scores from another model.

## Decomposition findings

All **7/7 rubrics produced schema-valid policies**. This is parsing success,
not semantic fidelity. The vocabulary only supports color, shape, left/right
position, count, and three preservation guards.

Instruction decomposition parsed **6/7** inputs, with these observed problems:

| Request | Actual generated plan | Lost meaning |
|---|---|---|
| Grab yellow cup with hand; move toward pot | Yellow color and cup shape | Grasping, movement, and relation to pot |
| Transform car into red sports car | Red color and shape `sports` | No explicit object/category or target binding |
| Make it into Conceptual Art | Empty edits; identity change permitted | The requested style transformation |
| Convert white keyboard into black keyboard | Black color | Binding the change to the keyboard |
| Move candles close to each other | Empty edits | Relative spacing and grouping |
| Remove small gray metallic cylinder | Gray color and cylindrical shape | Removal, size, material, and target selection |
| Put small cat on top of bus | Rejected after schema repair | Unsupported `position` value |

For example, merely seeing a yellow cup cannot establish that a hand grabbed
and moved it. Checking whether a gray cylinder exists is not a check that the
cylinder was removed. An empty candle plan cannot distinguish the requested
movement from an unchanged image.

Policy compilation also dropped distinctions. The C09 optimized rubric directs
`partial` for meaningful unintended alterations when the scene remains mostly
intact. Its compiled policy only checks recognizability as a preservation guard.
A post-run deterministic audit supplied a satisfied removal/count check and
recognizable scene: the policy returned `yes` and had no condition for an
unintended alteration elsewhere. This audit is an illustrative policy
counterexample, **not** a scored image prediction or replacement grading rule.

All **7/7 image-only boundary probes failed** with:

> Two-way judging requires structured evidence; image evaluation needs a separate adapter

Accordingly, decomposition image accuracy and direct/decomposed image agreement
are **unmeasured**, not zero accuracy. Both live tests intentionally failed
their capability assertions after saving the complete artifacts.

## Reproduce and inspect

From the repository root, choose a fresh report directory:

```sh
.venv/bin/python -m pytest tests/unit/calitree/test_optimized_aurora_prompts.py tests/unit/calitree/test_optimized_aurora_instruction_coverage.py --calitree-live --calitree-model gpt-4.1 --calitree-max-tokens 4096 --calitree-report-dir .cache/calitree-tests/optimized-aurora-new-run -v -s
```

The first run is preserved under
`.cache/calitree-tests/optimized-aurora-20260926/`:

- `optimized_aurora_manifest.json`: frozen inputs, model settings, source hashes.
- `optimized_aurora_results.json`: all 93 fresh judgments, rationales, and metrics.
- `optimized_aurora_compilations.json`: generated policies and compiler attempts.
- `optimized_aurora_instruction_coverage.json`: seven generated instruction plans/errors.
- `optimized_aurora_compilation_calls.json` and
  `optimized_aurora_instruction_calls.json`: exact compiler request/response traces.
- `optimized_aurora_semantic_audit.json`: deterministic post-run policy counterexample.
- `public_image_provenance.json`: public archive hash and 20 pixel-exact matches.

Images were verified against the authors' publicly linked
[human-rating archive](https://github.com/McGill-NLP/AURORA#human-ratings), SHA-256
`8a3430a01cda0139d4c99835a75dca98e16ec6ccc486fa30afa4504f3f18c69f`.
All 20 cached PNGs matched the decoded archive images pixel for pixel.

Normal offline validation: **57 passed, 15 skipped** for `tests/unit/calitree`.

## Implication

Earlier synthetic-rubric successes do not transfer automatically to these
optimized prompts. Before a faithful three-arm image comparison is possible,
the decomposition needs explicit actions, target binding, relational/style
conditions, preservation severity, semantic coverage validation, and a vision
condition evaluator. Expanding only the image adapter would leave the observed
instruction and policy losses unresolved.
