> Provider migration: configure `OPENAI_API_KEY` and/or `GEMINI_API_KEY` in your shell,
> project `.env`, or the interface. Scripts named `gateway`/`endpoints` now use official
> provider settings by default. See [providers](../docs/providers.md). Historical run
> instructions and results below retain their original model IDs.

# `run/` — benchmark run scripts

Convenience wrappers around the Criti-Cal CLIs. Each script resolves the project dir,
activates `.venv` if present, and silences the harmless LibreSSL warning. All extra
flags are passed straight through to the underlying CLI, so anything documented in
`docs/benchmark.md` works (e.g. `--projects`, `--judges`, `--limit`).

Run from anywhere:

```bash
./run/<script>.sh [extra flags]
```

## Cost & safety

Real (billable) gateway calls are **gated**. Scripts that make real calls pass `--live`
for you; the free ones never do. When unsure what a run will cost, use
`estimate_cost.sh` first — it never calls the gateway.

## The scripts

| Script | Calls gateway? | Use case |
|---|---|---|
| `setup_env.sh` | no | **Run once.** Create `.venv` and install dev/interface/video Python deps. |
| `setup_imagenhub.sh` | no gateway calls (downloads public data) | Materialize and hash the 179-task ImagenHub + eight publicly available editor outputs with resumable downloads. See `docs/calitree.md`. |
| `setup_aurora_bench.sh` | no gateway calls (downloads public data) | Materialize and hash AURORA-Bench's 2,000 human-rated outputs (400 prompts × five editors), extract the right output panel from the 150 known comparison composites while preserving raw images, then write task-grouped 20/80 calibration splits. |
| `run_aurora_prompt_repair.sh` | no by default; yes only with explicit `--live` | Sample a task-disjoint, label-balanced AURORA set; measure `gpt-5.4-mini` repeat stability; and independently repair incorrect/unstable cases with TextGrad and GEPA. |
| `robust_prompt_repair_50.py` / `robust_prompt_repair_50_parallel.py` | no by default; yes only with explicit `--live` | Compare single-draw and repeated-evaluation GEPA repair on 50 task-disjoint AURORA test cases, with 15 frozen-prompt final judgments per case and arm. See `docs/experiments/robust_prompt_repair_50.md`. |
| `setup_editinspector.sh` | no gateway calls (downloads public data) | Materialize pinned, nested EditInspector development/calibration/final partitions with resumable image downloads and SHA-256 manifest. |
| `run_editinspector_rubric_lite.sh` | no by default; yes only with explicit `--live` | Dry-run or execute the frozen Rubric-Lite external workflow. Live runs also require an explicit `--model`; supports partition selection, verifier disablement, and checkpoint seeding. |
| `run_imagenhub_rubric_lite.sh` | no by default; yes only with explicit `--live` | Dry-run or execute frozen Rubric-Lite v4 on all 1,200 ImagenHub held-out cases. Supports compatible checkpoint seeding and reports the exact remaining live-call count. |
| `run_imagenhub_calitree.sh` | no by default; yes only with explicit `--live` | Dry-run or train+evaluate Cali-Tree on ImagenHub. The prediction-conditioned branch uses `--leaf-grouping residual_context --clustering-algorithm behavioral_complete_link`; add `--pilot` for a bounded 12-train/24-test check. Pilot train/test ratios, task grouping, and test-group offset are configurable for disjoint confirmations. Leaves and accumulated roots require held-out routing/root guards. The runner defaults to `gpt-4o`; pass `--embedding-model text-embedding-3-small` for routing. |
| `check_video_deps.sh` | no | Verify the external `ffmpeg`/`ffprobe` binaries required by Edit Decomposition. |
| `run_tests.sh` | no | Fast correctness check (mocked engines). Run after setup and after code changes. |
| `estimate_cost.sh` | no (`--dry-run`) | See which items match and how many video/text calls a run would make. **Run before any real benchmark.** |
| `smoke_test_gateway.sh` | yes (1 tiny call) | Validate creds / endpoint / failover / logging with a single cheap text call. |
| `probe_endpoint.sh` | yes (cheap text) | Measure the gateway's concurrency / rate-limit ceiling to pick a safe `--concurrency`. |
| `check_endpoints.sh` | yes (2 tiny pings) | Report which gateway endpoint(s) are up. Benchmarks auto-switch to a working one; this shows you why. |
| `run_text_only.sh` | yes (text only) | Cheap real gap using only the text judges (M1, M3) — no video upload. Good for iterating. |
| `run_quick_subset.sh` | yes (text + video) | Small end-to-end run (default 2 items, M3/M5/M6) to validate the full pipeline incl. video. |
| `run_base_benchmark.sh` | yes (all judges, all items) | **The base benchmark:** full raw human-vs-judge gap, M1–M6, all peanut items. Slow/expensive. |
| `run_base_benchmark_robust.sh` | yes (grid of full runs) | **Robustness grid:** temperature × repeats, with judge self-consistency + bootstrap CIs. Very slow (default ~3.5 h). |
| `run_interface.sh` | no (backend only; a Judge Node run still needs `--live` from the UI) | Launch the FastAPI backend for the node-graph interface (`critical/interface/`). Pair with `cd web && npm install && npm run dev` for the React frontend. |
| `run_e2e_tests.sh` | no (mock gateway) | Real-browser (Playwright) end-to-end test of the interface: builds `web/`, runs a real FastAPI backend + real Chromium against a mock LM gateway. See "Testing the Interface (End-to-End)" in `CLAUDE.md`. |

## Recommended order (first time)

```bash
./run/setup_env.sh            # 1. install
./run/run_tests.sh            # 2. confirm everything imports & passes (free)
./run/smoke_test_gateway.sh   # 3. confirm the gateway works (one cheap call)
./run/estimate_cost.sh        # 4. see scope/cost of the full run (free)
./run/run_base_benchmark.sh   # 5. run the baseline (real, the expensive one)
```

Iterating on prompts/alignment? Prefer `run_text_only.sh` or
`run_quick_subset.sh --limit 1` to keep cost down.

## AURORA individual prompt repair

Prepare a free, deterministic 100-case sample and inspect the upper-bound call count:

```bash
./run/run_aurora_prompt_repair.sh all
```

The command prints its run directory. Set up the isolated GEPA dependency once, then
resume that exact directory for the staged live baseline and repair run:

```bash
./run/aurora_prompt_repair/setup_gepa_venv.sh
./run/run_aurora_prompt_repair.sh all --live --run-dir <run-dir> --resume
```

The defaults are the CaliTree v2 rubric verbatim, `gpt-5.4-mini`, seed 44, 10 fresh
temperature-0.3 repeats, a 7/10 empirical-stability threshold, five repair rounds,
and both independent optimizer tracks. Use `sample`, `baseline`, `repair`, or `report`
instead of `all` to run one resumable stage. Outputs include the sample and clean
1,500-output holdout manifests, raw predictions, optimizer traces, prompt files/diffs,
per-case reports, and JSON/CSV/Markdown summaries. Live runs display a baseline call bar
and a repair-track bar with the active method, case, round, and gate; pass `--no-progress`
when redirecting output to a system that supplies its own progress display.

The `report` phase also writes a standalone `report.html`. It includes all sampled cases,
source/edited images, baseline calls, and complete TextGrad/GEPA prompt progressions with
screen and repeated predictions. Open it directly in a browser. To generate or refresh the
same report for another compatible experiment directory without rerunning metrics:

```bash
python -m run.aurora_prompt_report logs/exps/<run-dir>
```

The page can also load another run interactively: select or drop its
`baseline_predictions.jsonl`, optional `repair_traces.jsonl`, `summary.json`,
`run_config.json`, and `sample_manifest.json` files. Selecting the entire run folder also
loads its seed prompt when present.

To test whether optimized natural-language rubrics retain their behavior after conversion
to structured semantic decisions, run the checkpointed equivalence stage:

```bash
python -m run.aurora_structured_decision_test \
  --run-dir logs/exps/<completed-prompt-repair-run> --live --resume
```

It evaluates every screen-correct progression, treating accepted robust prompts as the
primary cohort. The regenerated HTML nests the extracted decision JSON, compiled prompt,
screen prediction, ten-repeat distribution, and preservation statistics under its original
prompt round.

## Parallelism

Judge calls are independent and run in two simultaneous pools, so text and video scale
separately:

- `--concurrency N` — text judges (cheap; gateway allows ~16)
- `--video-concurrency N` — video judges (defaults to `--concurrency`; bandwidth/memory-bound, so ~4–8)

`run_base_benchmark.sh` defaults to `--concurrency 8 --video-concurrency 4`. The Pluto
gateway allows ~600 req/min per user (not the bottleneck for these small runs), and the
transport retries any 429 with `Retry-After` backoff. Run `probe_endpoint.sh` to re-measure.

```bash
./run/run_base_benchmark.sh --concurrency 12 --video-concurrency 6   # override defaults
```

## Robustness grid

`run_base_benchmark_robust.sh` runs the base benchmark across a **temperature × repeats**
grid to tell apart *judge sampling randomness* from *small-n correlation noise*:

- per-cell human-vs-judge Spearman/gap/MAE **plus a bootstrap CI** (is a swing real on ~13 items?)
- **judge self-consistency** across repeats: per-item score std + run-to-run rank agreement
  (human labels are fixed, so this isolates judge variance)

Default grid = temperatures {0.0, 0.3, 0.7, 1.0} × 5 repeats = **20 full runs (~3.5 h,
~2040 calls)**. Always dry-run first, then launch in the background:

```bash
./run/run_base_benchmark_robust.sh --dry-run                 # free estimate of cells/calls/time
nohup ./run/run_base_benchmark_robust.sh > robust.out 2>&1 & # the real grid (hours)
./run/run_base_benchmark_robust.sh --temperatures 0.0,1.0 --repeats 3 --skip-video  # cheap subset
```

Outputs land in `logs/exps/<ts>-robust/`: `robust_grid.csv`, `robust_summary.csv`,
`robust_report.md`, `cells.json` — with each cell nested inside as
`<ts>-robust/temp<T>_rep<N>-exps/` (its own inspectable per-cell artifacts).

### Resuming (`--continue`)

If a run drops partway (unstable endpoint), resume instead of restarting — every run
checkpoints each successful judge call, so `--continue` redoes only the missing work:

```bash
./run/run_base_benchmark.sh --continue                  # resume the most recent benchmark run
./run/run_base_benchmark_robust.sh --continue           # resume the most recent grid
./run/run_base_benchmark_robust.sh --continue <dir>     # a specific run folder
./run/run_base_benchmark_robust.sh --continue --dry-run # show pending cells (free)
```

On resume the grid is read from the run's config, so the script's default grid flags are
ignored. The grid skips complete cells and resumes a half-finished cell's checkpointed calls.

## Where results go

### CaliTree shared decision-rule pilot

Fit and evaluate a shallow CART program on saved five-repeat decomposition
observations, with no model calls:

```bash
.venv/bin/python -m run.calitree_shared_tree
```

The default source is `logs/exps/260930-10:51:35-exps`. Use `--source PATH` to
select a compatible frozen snapshot and `--output-dir PATH` for a new output
directory. Historical J cases train the program; grouped training-only validation
selects depth/support; later N cases evaluate it. Unknown and failed draws remain
unresolved. The fixed role mapper is an auditable scaffold, not a learned ontology.
The report compares a fixed reducer, majority baseline, pooled tree, semantic-role
tree, and a tree selected with a repeat-disagreement penalty. See
[`calitree_shared_tree_pilot.md`](../docs/experiments/calitree_shared_tree_pilot.md)
for results and the next experiment.

To run the exploratory class-balanced, fraction-feature and guarded-rule
refinements on the same frozen cohort:

```bash
.venv/bin/python -m run.calitree_tree_refinement
```

This comparison includes the fixed reducer as an eligible training-validation
candidate and keeps source/instruction support separate from class weights.
The evaluation cases have already been inspected; this is an exploratory follow-up.
See [`calitree_tree_refinement.md`](../docs/experiments/calitree_tree_refinement.md).

Every real/dry run writes a fresh `logs/exps/<YYMMDD-HH:MM:SS>-exps/` directory
(`gap_result.json`, `aligned_pairs.csv`, `gap_report.xlsx`, `chart_gap_by_dimension.png`,
`run.log`, `llm-histories.log`, `run_config.json`). See `docs/benchmark.md` for the schema.

For the manual leaf/merge canvas path, use `workflows/examples/calitree_aurora_canvas.json`. Run its shared partition first, then select each leaf’s fit cases in the Data tab. `.venv/bin/python -m run.calitree_canvas_demo` exercises three-child merging, JSON reload, and direct saved-policy judging entirely offline.

## Casewise CaliTree leaf optimizer

Fit one executable decision program per case, with structural and binding repairs:

```sh
.venv/bin/python -m run.calitree_program_optimization --demo --output-dir .cache/casewise-demo
.venv/bin/python -m run.calitree_program_optimization --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_program_optimization --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_program_optimization --report --output-dir RUN_DIRECTORY
```

See [the casewise runtime and API guide](../docs/calitree_program_optimizer.md).
The fresh pilot uses all twelve prior-pilot cases as independent local fits, with
GPT-6 Luna, 600 total requests and 768,000 completion tokens. Final comparisons are
reserved before search. Failed/interrupted requests are never resampled. Saved v2
leaves execute their exact decomposition and checks; parent merging is deferred.

## Compare custom, GEPA and TextGrad leaf optimization

All three methods can optimize executable decision rules on the same twelve cases:

```sh
.venv/bin/python -m run.calitree_optimizer_comparison --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_optimizer_comparison --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_optimizer_comparison --report --output-dir RUN_DIRECTORY
```

Uses pinned GEPA 0.1.4 and TextGrad 0.1.8, identical saved seeds, and equal per-case
call allowances. The full comparison cap is 1,800 calls and 2,304,000 completion
tokens, with final comparisons reserved in advance. See the
[adapter and protocol guide](../docs/calitree_optimizer_comparison.md).

The completed twelve-case results and limitations are in
[`docs/experiments/calitree_optimizer_comparison.md`](../docs/experiments/calitree_optimizer_comparison.md).

### Paired visual-check execution test

Compare the same frozen visual criteria in one combined prompt versus individual
image checks followed by text-only fulfillment:

```sh
.venv/bin/python -m run.calitree_check_ablation --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_check_ablation --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_check_ablation --report --output-dir RUN_DIRECTORY
```

See the [protocol](../docs/calitree_check_ablation.md) and
[completed pilot](../docs/experiments/calitree_check_ablation.md).

### DSG decomposition score fidelity

Compare the original saved seed scorer against DSG-style tuples, atomic questions,
prerequisite masking, and a text-only readout of the original rubric:

```sh
.venv/bin/python -m run.calitree_dsg_fidelity --preflight --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_dsg_fidelity --live --resume --output-dir RUN_DIRECTORY
.venv/bin/python -m run.calitree_dsg_fidelity --report --output-dir RUN_DIRECTORY
```

Native DSG fractions are retained separately from the yes/partial/no comparison.
Questions are frozen before scoring; there is no label-guided optimization.
See the [protocol](../docs/calitree_dsg_fidelity.md) and
[experiment report](../docs/experiments/calitree_dsg_fidelity.md).

### Robust local leaf optimizer (v3)

`python -m run.calitree_robust_leaf_optimization --preflight --output-dir logs/exps/NEW-RUN` freezes a six-case flat/tree × greedy/Pareto experiment. Use `--demo` for offline repair, `--live` for the explicitly gated OpenAI pilot, `--live --resume` for unattempted slots, and `--report` to regenerate the report. See [v3 usage](../docs/calitree_robust_leaf_optimizer.md). Old leaf runners and artifact formats remain available.

`python -m run.calitree_robust_hard_cases --preflight --output-dir logs/exps/NEW-HARD-RUN` freezes three prior-failure cases outside the six-case v3 pilot. Use `--live` to run the same four optimizer arms with a 1,800-call/2,304,000-completion-token ceiling, `--live --resume` for unattempted slots, or `--report` for saved results. Selection evidence and image hashes are pinned; runtime, prompts and thresholds are unchanged. See [v3 usage](../docs/calitree_robust_leaf_optimizer.md#failure-selected-harder-cases).

## Current CaliTree leaf optimizer

Use `.venv/bin/python -m run.calitree_fulfillment --offline-demo --output-dir /tmp/calitree-demo`
for the default fulfillment pipeline. See [usage and compatibility](../docs/calitree_fulfillment_optimizer.md).
Historical optimizer modes are retained behind compatibility APIs in `run/legacy/` and `critical/core/optimization/program/legacy/`.

## Single-call evidence judge

Use `.venv/bin/python -m run.calitree_single_call --preflight --output-dir logs/exps/NEW-EVIDENCE-RUN`,
then the same command with `--live` to benchmark explicit evidence checks plus a
fixed Python label policy against the saved flat twelve-case baseline. `--replay`
verifies the saved results without new API calls. Each case gets one shared model
response, using GPT-6.1 Sol high and one SOURCE-first image presentation. This is
an opt-in comparison; the default optimizer is unchanged. See the
[protocol and policy](../docs/calitree_single_call_evidence.md).

For a separate 36-case class-balanced calibration fit, use
`.venv/bin/python -m run.calitree_batch_calibration --preflight --output-dir logs/exps/NEW-CALIBRATION-RUN`,
then `--live`, then `--replay`. The layer fits on official training sources and
compares the same twelve cached records with flat and fixed-policy baselines,
without new evaluation model calls. See the
[batch calibration protocol](../docs/calitree_batch_evidence_calibration.md).

For **local fitting on the same twelve cached cases**, use
`.venv/bin/python -m run.calitree_local_calibration --preflight --output-dir logs/exps/NEW-LOCAL-RULE-RUN`,
then `--fit` and `--replay`. This makes no API calls and learns a bounded,
monotone tree over anonymous categorical evidence only. See the
[reusable-rule constraints and local fitting protocol](../docs/calitree_local_evidence_calibration.md).

For richer label-blind observations on those same twelve cases, use
`.venv/bin/python -m run.calitree_rich_local_calibration --preflight --output-dir logs/exps/NEW-RICH-LOCAL-RUN`,
then `--live` and `--replay`. This makes twelve new single-response image calls,
keeps the depth/support limits, and includes fresh-base controls against the
previous 10/12 local fit. See the [rich evidence protocol](../docs/calitree_rich_evidence_calibration.md).

For a matched **36-case flat versus frozen rich-evidence CaliTree** comparison,
use `.venv/bin/python -m run.calitree_benchmark36 --preflight --output-dir logs/exps/NEW-BENCHMARK36`,
then `--live` and `--replay`. It uses 36 source-disjoint evaluation cases, 72 calls
maximum, the same model/presentation in both arms, and no policy refitting. See
the [comparison protocol](../docs/calitree_benchmark36.md).

For **corrected three-label local calibration**, use
`.venv/bin/python -m run.calitree_recalibrate --preflight --output-dir logs/exps/NEW-V3-LOCAL`,
then `--fit` and `--replay`. This reuses the 36 cached records, learns No/Partial/Yes,
and resolves uncertainty only when it cannot affect the learned decision. No API
calls are made. The preceding benchmark commands pin historical v2 policies;
see the [v3 contract and usage](../docs/calitree_evidence_rules_v3.md) for corrected fits.

For **class-balanced optimization that prevents Partial collapse**, use
`.venv/bin/python -m run.calitree_recalibrate_balanced --preflight --output-dir logs/exps/NEW-V4-LOCAL`,
then `--fit` and `--replay`. V4 maximizes macro-F1 and requires two correctly
recognized sources per class while retaining v3's evidence and rule limits.
See the [v4 objective and usage](../docs/calitree_evidence_rules_v4.md).

To repeat v4 local fitting on **four disjoint balanced twelve-case groups**, use
`.venv/bin/python -m run.calitree_four_groups --preflight --output-dir logs/exps/NEW-FOUR-GROUPS`,
then `--live` and `--replay`. It samples 48 separate cases, makes at most 96
matched baseline/extraction calls, fits only within each group, and reports any
infeasible three-class fits without resampling. See the [four-group protocol](../docs/calitree_four_groups.md).

For the **fixed-group richer-check and clustering comparison**, replay the saved
evidence with `.venv/bin/python -m run.calitree_semantic_evidence --replay --output-dir logs/exps/261014-semantic-contract-evidence-v5`,
then run `.venv/bin/python -m run.calitree_visibility_calibration --output-dir logs/exps/261014-semantic-visibility-calibration-v6`
and `.venv/bin/python -m run.audit_calitree_semantic`. These commands use caches
and make zero API calls. Shared and clustered policies reach 10/12, 12/12, 10/12,
10/12 on the same fixed groups, with four failed requests retained. See the
[semantic evidence, observability, budgets, and limitations](../docs/calitree_semantic_calibration.md).

For the **approved fast-model comparison on those same fixed 48 cases**, replay
`.venv/bin/python -m run.calitree_small_models --replay --models luna mini --output-dir logs/exps/261014-fast-models-four-groups-v2`,
then run `run.calitree_small_models_calibration` and `run.report_calitree_small_models`
as Python modules with the same `--output-dir`. All replay/fitting/report commands
make zero API calls. See [fast-model settings, results, and formatting diagnostic](../docs/calitree_fast_models.md).

For the **instruction-dependent interaction prototype**, run
`.venv/bin/python -m run.calitree_instruction_rules --replay --output-dir logs/exps/261014-instruction-interactions-v7`
and `run.report_calitree_instruction_rules` as a Python module with the same
`--output-dir`. Required checks are noncompensatory, and train-group policies
are frozen before scoring other groups. This cached experiment adds zero API
calls and is not promoted as an accuracy improvement. See the
[rule semantics, transfer protocol, and negative results](../docs/calitree_instruction_interactions.md).

For **learned-policy → semantic-rule translation**, use
`run.calitree_policy_translation --certify` or `--replay` with
`--output-dir logs/exps/261014-policy-semantic-translation-v8`, then
`run.calitree_semantic_refinement --replay` and `run.report_calitree_policy_translation`
with `--output-dir logs/exps/261014-policy-semantic-refinement-v9` (all as Python
modules). These commands add zero API calls. Exact condition compilation and
refined prose-only execution preserve the learned Sol local result, 42/48.
See [semantic rule compilation, boundary refinement, and limits](../docs/calitree_policy_translation.md).

For **instruction-grounded semantic rule induction**, replay the three cached
stages with `run.calitree_observable_facts`, `run.calitree_postconditions`, and
`run.calitree_intermediate_facts`, then run `run.calitree_instruction_distillation`
and `run.report_calitree_instruction_distillation` with
`--output-dir logs/exps/261014-instruction-semantic-distillation-v16` (all as Python
modules). Teacher-only physical-rule distillation matches 42/48 local accuracy;
it uses physical postconditions and witness evidence rather than renamed grades.
See [the pipeline, exact replay commands, and limitations](../docs/calitree_grounded_semantic_distillation.md).

For **frozen semantic-rule transfer to new cases**, use
`.venv/bin/python -m run.calitree_semantic_transfer --replay --output-dir logs/exps/261014-frozen-semantic-transfer12-v1`
and `.venv/bin/python -m run.audit_calitree_semantic_transfer logs/exps/261014-frozen-semantic-transfer12-v1`.
Replay and audit make zero model calls. The original live run used 48 shared
extraction calls and restored four v16 policies without fitting. New accuracies
were G1 6/12, G2 9/12, G3 9/12, and G4 8/12; Partial transfer remains weak.
`--preflight` prepares a sealed protocol and `--live` explicitly enables calls.
The sample seed and cohort are fixed; failures are retained and never resampled.

For **M0's reserved fifty-case semantic-hierarchy protocol**, run
`.venv/bin/python -m run.calitree_m0 verify --output-dir logs/exps/261014-semantic-hierarchy-m0-fifty-v1`
and `.venv/bin/python -m run.calitree_m0_finalize --check --output-dir logs/exps/261014-semantic-hierarchy-m0-fifty-v1`.
Both are offline. The sealed split is 48 training / 12 development / 50 final;
the final set has 17 No / 17 Partial / 16 Yes and no overlap with development.
Historical project exposure is explicitly disclosed, so it is not globally
untouched. No final-test model calls were made. See the
[M0 protocol, audit limits, and future budgets](../docs/calitree_m0_fifty_case_protocol.md).

For **M1 exact-question physical evidence**, replay
`.venv/bin/python -m run.calitree_bound_evidence_v2 --replay --output-dir logs/exps/261014-m1-bound-evidence-development12-v2`
and audit with `.venv/bin/python -m run.audit_calitree_bound_evidence logs/exps/261014-m1-bound-evidence-development12-v2`.
The current component is `critical.core.decision.bound_evidence_v2`; the initial
v1 implementation/run is retained. V2 has twelve valid development records and
90 checked question bindings. Its fixed, uncalibrated diagnostic scores 9/12
with two unresolved cases. No final-set calls or policy fitting occurred.
See [M1 contracts, visual disputes, and scope](../docs/calitree_m1_bound_evidence.md).

For **M2–M4 scalable semantic baselines and instruction-only routing**, replay
`.venv/bin/python -m run.calitree_semantic_baselines_v3 --replay --output-dir logs/exps/261014-m2-m4-semantic-baselines-v3`
and audit with `.venv/bin/python -m run.audit_semantic_baselines logs/exps/261014-m2-m4-semantic-baselines-v3`.
Training evidence replays through `run.calitree_hierarchy_collect --replay` with
`--output-dir logs/exps/261014-m2-m4-bound-training48-v1`. These commands make no
new model calls. Current APIs are `features_v2`, `rule_search_v3`, and `routing_v3`
in `critical.core.calibration.semantic_hierarchy`. Grouped OOF accuracy is pooled
16/48 and routed 18/48; the prototype is not deployment-qualified. The reserved
fifty remain unqueried. See [milestone verification and negative findings](../docs/calitree_m2_m4_semantic_baselines.md).
# M2 v4 local fitting and conflict-aware regrouping

The opt-in `calitree_m2_conflict_v4` runner uses frozen M1 observations and makes
no model calls. It removes mandatory label vetoes, retains richer role/kind
distributions, reports feature conflicts, and learns semantic groups with local
rule subtrees. Full training accuracy is 47/48; one missing observation remains
unresolved. Held-out-group accuracy is 23/48, so the result is experimental.

```bash
.venv/bin/python -m run.calitree_m2_conflict_v4 --output-dir logs/exps/261014-m2-conflict-regrouping-v4 --replay
.venv/bin/python -m run.audit_calitree_m2_v4 logs/exps/261014-m2-conflict-regrouping-v4
```

See [the detailed v4 report](../docs/calitree_m2_conflict_regrouping_v4.md) for
scope predicates, frozen artifacts, tests, and the distinction between fitting
capacity and semantic generalization. The reserved fifty remain unevaluated.

# M2 v8: portable semantic rules

The portability-first M2 learner excludes case/object/instruction literals,
image coordinates, raw check cardinalities and majority thresholds. Its reviewed
policy scores 44/48 (91.7%) with fourteen rules. This follows the user's clarified
rule-reuse objective; it is not a statistical-generalization claim.

```bash
.venv/bin/python -m run.calitree_m2_portable_v8 --replay --output-dir logs/exps/261014-m2-portable-semantic-v8
.venv/bin/python -m run.calitree_m2_portable_review_v8 --output-dir logs/exps/261014-m2-portable-semantic-v8
.venv/bin/python -m run.audit_m2_portability_v8 --output-dir logs/exps/261014-m2-portable-semantic-v8
```

Use `deployment_policy.json` with `PortableRuleExecutor` for execution;
`reviewed_policy.json` retains training provenance separately. Fresh-case input
currently uses two M1 model calls plus one text-only semantic interpretation.
All model calls for the recorded study are cached. See
[the v8 report](../docs/calitree_m2_portable_semantic_v8.md) for rule definitions,
verification, the preserved transfer failures, and limitations.

# M3–M7: portable semantic hierarchy experiments

`calitree_semantic_hierarchy` extends the frozen M2 v8 evidence with local
alternatives, instruction-only routing, semantic/behavioral merge proposals,
cross-batch-supported parent fitting, and bounded iterative promotion. It is
offline and opt-in. The recorded study rejects all thirteen parent proposals
and retains pooled M2 at 44/48 locally; grouped development is 24/48 and the
separate twelve-case development score is 9/12. The final fifty remain reserved.

```bash
.venv/bin/python -m run.calitree_semantic_hierarchy --stage all --replay --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m run.audit_calitree_semantic_hierarchy --stage hierarchy --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
.venv/bin/python -m run.audit_calitree_hierarchy_invariance --output-dir logs/exps/261015-semantic-hierarchy-m3-m7-v9.2
```

Omit `--replay` and choose a new output directory for a new study using the same
local cached input artifacts. Replay forbids new fits and model calls.

The deployment-only package is `examples/calitree_semantic_hierarchy_v9`.
Its CLI authenticates bound upstream outputs and executes without training logs,
reference labels, refitting, or model calls:

```bash
.venv/bin/python -m run.calitree_semantic_hierarchy_predict --bundle examples/calitree_semantic_hierarchy_v9 --evidence /path/to/bound_evidence.json
```

See [the M3–M7 report](../docs/calitree_m3_m7_semantic_hierarchy.md) for gates,
the preserved routing failure, the complete parent results, and the distinction
between tested algorithm behavior and a useful learned hierarchy.

# Router-free M5–M7: union merging and child-predicate reuse

The opt-in `calitree_union_merge` control and `calitree_union_reuse` learner
skip M4. Each parent is fitted and accepted on the complete original-reference
union of its children. Eight semantic six-case groups form a 48-case root through
seven accepted merges. The selected root scores 46/48 locally and 10/12 on the
separate historical development cohort, with fourteen rules. It uses only its
immediate children's predicates; five lower-level merges require full-grammar
repair. No model calls or final-fifty predictions were made.

```bash
.venv/bin/python -m run.calitree_union_reuse --run semantic8_reuse --replay --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m run.audit_calitree_union_merge --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m run.audit_calitree_union_invariance --output-dir logs/exps/261015-union-reuse-v11
.venv/bin/python -m run.calitree_union_predict --package examples/calitree_union_reuse_v11 --evidence /path/to/bound_evidence.json
```

The deployed package contains one policy and no router or training memberships.
The existing three upstream model passes are unchanged; final rule execution
makes zero model calls. See [the detailed report](../docs/calitree_router_free_union_merging.md)
for the seven selected merges, cold-refit controls, and honest reuse/transfer limits.
