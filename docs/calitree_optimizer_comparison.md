# GEPA and TextGrad decision-program adapters

These adapters optimize the same executable leaf graphs as the custom casewise
optimizer. They can add or remove checks, change decomposition and bindings, and
revise criteria. They do not merely rewrite a monolithic judgment prompt.

## What runs

- **Custom:** existing typed-transaction beam search, two rounds, beam width two,
  at most two transactions per parent. Its implementation is unchanged.
- **GEPA 0.1.4:** native `gepa.optimize` in the repository's isolated `.venv-gepa`
  environment, with a custom evaluator, Pareto candidate selection, strict
  improvement acceptance, and at most six proposals. There is one case in both
  training and validation; these are local fitting scores, not holdout evidence.
  Merging is disabled. Pareto selection has limited diversity on one case.
- **TextGrad 0.1.8:** the entire graph is a trainable `Variable`.
  `StringBasedFunction` evaluates the executable graph, its native backward pass
  generates textual feedback, and `TGD.step()` updates the graph. At most six
  update steps are allowed. This is graph-level textual differentiation; it does
  not backpropagate separately through every individual checker node.

Both official libraries use their native prompts and algorithms through adapters;
all their model calls are routed through CaliTree's logged, capped provider. No
package directly contacts a model provider. The existing old prompt-only adapters
are left unchanged. Package versions and hashes of installed package source files
are frozen in the comparison manifest.

## Shared execution contract

The trainable genome contains exactly `requirements`, `outcomes`, and `checks`.
The instruction, rubric, aggregation and checker template remain frozen in the
seed. Each replacement must preserve its parent requirements and exact provenance,
cover every requirement, use one requested fulfillment check per outcome, obey the
four-check limit, and maintain valid supporting dependencies. Outcome mappings and
added/removed/changed nodes are saved in the candidate lineage.

A label-blind audit checks semantic preservation. Model checkers never receive
reference labels or optimization feedback. The native optimizer's reflection,
backward and update calls receive the reference label, original instruction,
execution feedback, schema constraints and both images.

Valid programs receive one screening draw. An audited matching program receives
three fresh confirmation draws. The best confirmed eligible candidate is retained
under the common local ranking; the seed is always available. Search stops early
when an audited candidate matches all three confirmation draws. Invalid candidates
remain diagnostic records, never executable replacements. Frozen candidates get
three additional fresh final draws. `locally_fitted` requires an accepted audit and
three matching final labels with full coverage.

These are constrained library integrations, not untouched defaults. GEPA and
TextGrad replace serialized graphs; custom search applies typed transactions.
Their proposal interfaces and exploration strategies differ, so this experiment
compares complete integrations rather than isolating only the search algorithm.

## Run

```sh
# Verify dependencies, freeze identical seeds and the existing twelve-case cohort:
.venv/bin/python -m run.calitree_optimizer_comparison --preflight --output-dir RUN_DIRECTORY
# Run or resume the frozen comparison:
.venv/bin/python -m run.calitree_optimizer_comparison --live --resume --output-dir RUN_DIRECTORY
# Rebuild tables without provider calls:
.venv/bin/python -m run.calitree_optimizer_comparison --report --output-dir RUN_DIRECTORY
# Offline tests invoke the actual pinned libraries with deterministic model replies:
LITELLM_LOCAL_MODEL_COST_MAP=True .venv/bin/python -m pytest -q tests/unit/calitree/test_program_backends.py
```

The live protocol uses the twelve original casewise-pilot seeds, not its optimized
programs. Seed compilation was label-free and its cost is excluded equally from
all three arms. Every method gets the same instruction, images, seed and reference
label. Cases remain separate; no candidate or observation cache is shared between
methods. Method order rotates by case. All three selections for a case are frozen
before its final comparisons begin. Existing experiment artifacts remain intact.

The authorized maximum is 1,800 calls and 2,304,000 completion tokens. Each
case-method gets at most 26 search calls and 24 final calls, yielding at most 600
calls per method. Reserve 864 possible final checker calls and 884,736 completion
tokens before search. Checker outputs cap at 1,024 tokens; all other calls cap at
2,048. The completion-token ceiling is shared across methods. Every request has one
HTTP attempt; failures and interruptions remain durably charged. Provider rejection
or three consecutive transport failures stops the comparison without substitution.

There are separate fresh seed and selected comparisons for each method. Repeated
judgments are not independent cases. All cases are previously observed and their
reference labels guide local optimization, so the results do not measure
cross-case generalization. The report includes final agreement, successful local
fits, structural versus criterion changes, coverage, repeat variability and usage.

The implementation is under `critical/core/optimization/program/backends/` and uses
the existing program-leaf builder and saved-leaf execution API.

For a single case, construct `GepaProgramOptimizer(compiler, evaluator)` or
`TextGradProgramOptimizer(compiler, evaluator)` and call
`optimize(case, reference_label, seed=program)`. Both implement `LeafOptimizer`
and return the same `LeafResult` as the custom optimizer. Pass either through
`CaliTreeBuilder.build_program_leaves(..., optimizer_factory=..., seeds=...)`
to save a normal executable program leaf. Use separate durable call scopes and
observation stores when comparing methods, as the comparison runner does.

Dependencies are optional: install the repository's `textgrad==0.1.8` dependency
in the main environment, and use `run/setup_calitree_gepa.sh` for the isolated
`gepa==0.1.4` environment. The adapters validate these versions before optimization.

Completed results: [twelve-case comparison](experiments/calitree_optimizer_comparison.md).
