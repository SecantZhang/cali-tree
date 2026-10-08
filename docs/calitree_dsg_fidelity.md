# DSG decomposition and original-score fidelity

This experiment asks whether decomposing an instruction with Davidsonian Scene Graphs (DSG) preserves the scores of the saved original CaliTree seed program. It does not optimize questions against scores or human labels. The same 12 previously observed AURORA cases and image hashes are reused, with five fresh executions per format. Repeats are repeated measurements of 12 cases, not 60 independent examples.

The implementation adapts [Cho et al., ICLR 2024](https://arxiv.org/abs/2310.18235) and the [authors' method description](https://google.github.io/dsg/). It is an independent implementation, not a run of the official repository. Three separate text-only model calls generate semantic tuples, questions, and prerequisite dependencies. A fourth text-only call audits coverage and atomicity diagnostically. Every structurally valid graph executes regardless of audit approval. There is no score-guided repair or filtering.

Entity existence can support an attribute or relation question. Negative prerequisites assign dependent questions zero without another image call; unknown prerequisites propagate unknown. Each graph has at most four questions. Requirements are never truncated to fit the cap. A global style request can legitimately remain a single question. Exact instruction quotes and mappings to the original outcomes are saved.

Two scores are retained:

- **Native DSG fraction:** mean dependency-masked yes/no answers across all graph nodes, including supporting entity checks. Any unknown makes the fraction unresolved. The requested-only fraction is a separate diagnostic.
- **Original-rubric readout:** a text-only model sees the saved original rubric, graph, and visual observations and assigns complete/partial/absent/unknown to each original outcome. It cannot see images, the original prediction, or human labels. Fixed CaliTree aggregation then returns yes/partial/no. Supporting nodes do not count as completed edits. This readout is a CaliTree adaptation, not the published DSG aggregate.

The original arm executes the exact saved label-free seed program, with frozen bindings and templates. It is not the optimized program or the human label. Primary fidelity is exact label agreement at paired repeat slots, with unresolved draws counted as non-matches. Case modal agreement, all-five agreement, all-cross-repeat agreement, resolved coverage, and ordinal MAE (no=0, partial=0.5, yes=1) are also recorded. Numerical differences between native DSG fractions and ordinal labels are diagnostic: those scales measure different constructs. Human-reference accuracy is secondary. All summary statistics weight cases equally; resolved-only metrics exclude unavailable values and must be read with coverage.

## Run

```bash
.venv/bin/python -m run.calitree_dsg_fidelity --preflight --output-dir logs/exps/261006-dsg-fidelity-v2
.venv/bin/python -m run.calitree_dsg_fidelity --live --resume --output-dir logs/exps/261006-dsg-fidelity-v2
.venv/bin/python -m run.calitree_dsg_fidelity --report --output-dir logs/exps/261006-dsg-fidelity-v2
```

Preflight verifies the exact source case identities and image hashes and freezes implementation snapshots. All graphs are generated before either scoring arm runs. Arm order alternates by case and repeat. Model: GPT-6 Luna, temperature zero, reasoning `none`; returned identities are retained. Checker/readout outputs are capped at 1,024 tokens, generation/audit at 2,048. The approved cumulative ceiling is 450 calls / 512,000 completion tokens; the planned worst case is 418 calls / 477,184 tokens, with 370 final calls reserved before preparation. No model substitution or automatic repair is permitted.

Durable slots receive one HTTP attempt. Failures and interruptions consume budget and are never resampled. A provider rejection or three consecutive transport failures stops execution. Original execution is bounded per case; DSG execution has separate scopes per case/draw, at most four visual calls and one readout. Resume requires unchanged configuration, code, images, and saved graph identity. Already saved draws are loaded directly.

Artifacts contain the manifest, source snapshots, exact graphs and original programs, diagnostic audits, per-node observations, readouts, predictions, durable job ledger, measured usage, full provider history, and aggregate results. Tests use fake providers exclusively:

```bash
.venv/bin/python -m pytest -q tests/unit/calitree/test_dsg_fidelity.py
```

The test suite covers score semantics, dependency masking, structural validation, singleton global requests, label isolation, image access boundaries, full paired execution, interrupted slots, and zero-call resume.

## Implementation correction and retained attempts

The first snapshot (`logs/exps/261006-dsg-fidelity-v1`) rejected schema-valid hyphenated tuple IDs due to an undocumented validator restriction. The replacement snapshot removes that restriction. It retains all 57 prior attempts, completed draws, and the cumulative ledger; one interrupted readout remains unresolved and is not retried. The two rejected tuple responses are reused exactly, and only their unattempted question/dependency/audit stages continue. No prompt, scoring rule, question, or threshold was changed. `migration.json` records the old manifest and budget hashes. The original snapshot remains available.

Completed results: [DSG score-fidelity report](experiments/calitree_dsg_fidelity.md). The ID correction completed two graphs after some first-case scoring had already run; the report records this protocol deviation and all retained attempts.
