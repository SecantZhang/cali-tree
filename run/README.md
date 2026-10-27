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
| `calitree_current.py` | no | Selected AURORA inference stack, currently v112. `--describe` reports the pinned selection; `--input cached_requests.json --output-dir NEW_RUN` executes explicit cached stages. |
| `verify_calitree_current.py` | no | Replay the selected default on all915 bound cached inputs and compare predictions, coverage and source routes against verified v112. |
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

## Regularized child optimization and compressed parents (v14)

The v14 opt-in research path uses bounded semantic child fitting, explicit
predicate alternatives, class-preserving pruning, and a measured parent rule
reduction of at least 20%. It is evaluated with nested training-only folds and a
matched direct-fitting control. The v13/v14 comparison changes pruning alone;
the older v8–v12 experiments remain frozen.

```bash
.venv/bin/python -m run.calitree_supported_pruning_v14 --output-dir logs/exps/261018-supported-child-compression-v14
.venv/bin/python -m run.verify_calitree_supported_pruning_v14 --output-dir logs/exps/261018-supported-child-compression-v14
.venv/bin/python -m run.report_calitree_supported_pruning_v14 --output-dir logs/exps/261018-supported-child-compression-v14
```

All three commands are offline. See [the algorithm, explicit acceptance change,
validation boundaries and results](../docs/calitree_regularized_children.md).
The [portable candidates](../examples/calitree_supported_children_v14) contain no
training memberships or labels. A separate reserved-fifty runner defaults to
preflight; do not consume that final set without approval of its paid-call and
model protocol.

The approved frozen-fifty evaluation has now completed: v14 merged scores are
26/50, 26/50 and 25/50, versus v12's 21/50, 27/50 and 18/50. V14 matches its direct
controls on every prediction, so a merging advantage is not confirmed. Historical
sections above describe the earlier reservation state; these final outcomes are
now exposed and must not be reused for tuning a claimed fresh final result.

```bash
.venv/bin/python -m run.verify_calitree_frozen_final_v14 --output-dir logs/exps/261018-frozen-final-v14
.venv/bin/python -m run.report_calitree_frozen_final_v14 --output-dir logs/exps/261018-frozen-final-v14
```

Both commands are offline. See [the complete final result](../docs/experiments/calitree_frozen_final_v14.json).

## Local-accuracy-preserving child optimization and merging (v18)

The current opt-in path follows the revised local-fit-first objective. Each
parent preserves every child's local accuracy and removes at least one rule;
bounded search keeps a forest when a complete merge cannot pass. It uses the
full reusable feature vocabulary and cached v12 training evidence. No paid calls
or held-out predictions are made.

```bash
.venv/bin/python -m run.calitree_local_compression_v18 --output-dir logs/exps/my-local-compression-v18
.venv/bin/python -m run.verify_calitree_local_compression_v18 --output-dir logs/exps/my-local-compression-v18
```

Use a fresh output directory. The recorded run is
`logs/exps/261018-local-compression-v18-r1`: rules decrease 22→21, 18→15, 19→16;
scope-local accuracy is preserved or improves to 48/48 in all three splits.
These are partial forests with no inferred router, not complete merged roots.
See [the method and limitations](../docs/calitree_local_compression.md).

## Task coverage gate and reference-guided judge (v19)

`run.calitree_task_coverage` prepares a frozen paired local-accuracy comparison.
The gate uses compiled task structure to offer conditional tree rules; uncovered
inputs use the exact regular-judge request. It does not require the observer or
semantic interpreter. Live comparison requires `--live` and a paid-call budget;
preflight and `run.verify_calitree_task_coverage` are offline.

See [coverage semantics, inference usage and the evaluation protocol](../docs/calitree_task_coverage.md).
The approved comparison is complete: hybrid 33/48, 31/48, 36/48 versus regular
33/48, 28/48, 37/48. Two child batches regress; this remains opt-in and is not
promoted as a local-accuracy-preserving replacement.

## Evidence coverage with preserved local accuracy (v20–v22)

The newer opt-in path keeps the trained expert's verdict when observed features
pass supported guards and semantic-support checks. Otherwise it uses the regular
judge. A content-addressed evidence cache stabilizes known inputs without storing
human labels or final verdicts. Retained hierarchy children fill supported local
coverage gaps.

All 144 local slots retain their correct tree outputs, including all twelve
original child batches. The exploratory transfer diagnostic improves accepted-
prediction precision from task-only routing's 40.0% to 63.3%, with 104/150 full-
system accuracy versus 100/150 for the regular judge. Unseen errors remain.

`run.calitree_evidence_coverage_v20` learns initial guards;
`run.calitree_evidence_support_v21` adds semantic support;
`run.calitree_complete_evidence_coverage` reuses retained children.
`run.verify_calitree_complete_coverage` and `run.verify_calitree_raw_coverage`
audit the final selectors and raw-input cache replay. These runners are offline.
See [the contracts, results and inference example](../docs/calitree_evidence_coverage.md).

## Reviewed-error rejection without local regressions (v23)

`run.calitree_counterexample_coverage_v23` adds monotone rejection checks to the
frozen v22 gate. All 22 reviewed wrong acceptances are rejected, all 38 correct
transfer acceptances remain covered, and all 144 local raw-input tree predictions
remain correct. The reviewed transfer outcomes are now calibration data; the
post-fit score is not an untouched validation result.

`run.verify_calitree_counterexample_coverage` independently replays the full
comparison and protected routes. Both commands are offline. See [the method,
22-case review and limitations](../docs/calitree_counterexample_coverage.md).

## Pairwise merge development with routing checks (v24)

`run.calitree_pairwise_merge_v24` fits compact parents with correct cross-batch
support, preserves child and original-batch accuracy floors, rebuilds coverage,
and preserves the frozen system's accept/defer decisions. Existing v23 rejection
checks are unchanged. Additional short coverage clauses retain abstention behavior
when removing an expert removes a disagreement signal.

The audited first phase accepts one learned parent in split 2: experts 4→3,
terminal rules 22→19, stored Boolean conditions 476→442. All 144 local predictions
and all 294 recorded pipeline decisions are unchanged. Other candidates remain
rejected or bounded-search failures. Both the runner and
`run.verify_calitree_pairwise_merge_v24` are offline.
See [the full result and acceptance contract](../docs/calitree_pairwise_merge.md).

### Semantic merge candidate scheduling (v25)

`calitree_semantic_merge_v25.py` adds `--ordering semantic|artifact_id` and
`--fit-budget` to the offline pairwise workflow. Profiles prioritize compatible
supported task distributions, prediction agreement, and shallow predicates;
parent fitting and accuracy/coverage acceptance stay unchanged.

`compare_calitree_semantic_merge_v25.py --previous-run PATH --output-dir NEW_PATH`
runs both orderings at 4, 8, and 24 fits per split. Identical computations are
memoized across arms while each arm pays a separate logical fit budget. Run
`verify_calitree_semantic_merge_v25.py --output-dir NEW_PATH` for candidate-order,
budget, child-retention, coverage and raw-input replay audits. These commands
are offline and make no model calls. See `docs/calitree_semantic_merge.md`.

### Semantic rule regions (v26)

`calitree_semantic_regions_v26.py --parent-run PATH --output-dir NEW_PATH`
builds explicit task-and-evidence regions on the original local examples and
replays the mixed judge offline. `--verify --output-dir NEW_PATH` checks the
source/code hashes, refits the regions and replays all 294 cases. The opt-in gate
preserves local accuracy but adds three development deferrals, reducing the
recorded development score 116→115/150. Task shortlisting is separate from
final evidence coverage; the original full-bank disagreement veto stays active.
See `docs/calitree_semantic_regions.md` for the API and support limitations.

### Shared region definitions (v27)

`calitree_shared_regions_v27.py --parent-run PATH --output-dir NEW_PATH` compiles
v26 regions into canonical evidence definitions shared across supported task
scopes and, when equivalent, experts. It pools duplicate conditions, supports
exact Boolean simplification, and retains per-task support counts. `--verify
--output-dir NEW_PATH` checks symbolic equivalence, deduplicated support and
all 294 recorded predictions/routes. The audited run reduces definitions
149→63 and canonical JSON size by 10.1%, with 144/144 local predictions preserved.
Real cross-expert equivalents were not found; thin task-specific support remains.
See `docs/calitree_shared_regions.md`. No new model calls; remains opt-in.

### Semantic cross-expert region merging (v28)

`calitree_semantic_region_merge_v28.py --parent-run PATH --output-dir NEW_PATH`
relaxes exact equivalence: similar same-verdict regions from different expert
sets share common conditions and combine supported task scopes. Every candidate
must retain child local support and all recorded routes. The full-bank veto and
a supported match from a contributing expert remain required. `--verify
--output-dir NEW_PATH` reproduces the search and replays all 294 cases.
The opt-in run reduces 63→44 regions, with seven cross-expert regions and no
recorded coverage regressions. See `docs/calitree_semantic_region_merge.md`.

### Source-audited 80-output AURORA pilot (v29)

`calitree_aurora_pilot_v29.py --source-root PATH --output-dir PATH --audit`
audits original/worktree exposure and prepares the cohort. Its current protocol
uses the user's approved alternative: two tasks per category, all five editors,
prefer unused sources, and exclude 244 recent-study/declaration groups while
allowing explicitly disclosed older exposure. `--verify --output-dir PATH`
checks the sealed preflight.

`collect_calitree_aurora_pilot_v29.py --prepare --output-dir PATH` pins the execution
plan without calls. `--live` requires separate explicit user authorization;
`--report` replays completed collection. Six v27/v28 banks share extraction and
one regular response per output. The prepared pilot has 256 normal requests,
at most 272 including compiler repairs, and a 2,392,064 completion-token ceiling.
Estimated cost is approximately $0.13–$0.18; the full completion allowance alone
costs $1.196032 plus input. See `docs/calitree_aurora_pilot.md`.

The authorized v29 pilot has completed in
`logs/exps/261020-aurora-pilot80-v29-run1`. The corrected collector
`collect_calitree_aurora_pilot_v29r1.py` removes an unsupported local adapter
argument while preserving the approved Luna wire settings, and deducts the
three pre-HTTP reservations from its available budget. It does not retry any
provider request. Audit with `verify_calitree_aurora_pilot_v29.py`; derive paired
comparisons with `analyze_calitree_aurora_pilot_v29.py`. Results are in
`docs/calitree_aurora_pilot_results.md`. The run used 255 API attempts (258 counting
local failures); v28's seven extra acceptances were all incorrect.

### Ungated cached-pilot ablation (v30)

`calitree_ungated_ablation_v30.py --parent-run PATH --output-dir NEW_PATH`
freezes equal expert voting, plurality selection, and the Partial-then-No tie
rule before scoring the cached pilot. It bypasses all coverage filters; failed
extraction stays unresolved with no regular fallback. `--verify` independently
walks the expert trees and reproduces results. No model calls or fitting.
Ungated scores 43/35/27 out of 80 versus v27's 57/50/50 and regular's 53.
See `docs/calitree_ungated_ablation.md` for deferred-case and tie breakdowns.

### Rejected-case diagnostics (v31)

`diagnose_calitree_rejections_v31.py --ablation-run PATH --output-dir NEW_PATH`
measures correct-expert availability and rule/evidence disagreements on cached
rejected cases, exports six targeted review traces, and runs one isolated manual
doodle-evidence counterfactual. `verify_calitree_rejections_v31.py --output-dir PATH`
checks counts, images, source-leaf provenance and the counterfactual. Zero model
calls or fitting; causal error percentages are not inferred from oracle counts.
See `docs/calitree_rejection_diagnostics.md`.

### Guarded semantic policy development (v32–v35)

`calitree_guarded_generalization_v32.py --output-dir NEW_PATH` fits verdict
support clauses and tests semantic-obligation-preserving region merges with
all five outputs of each validation source excluded. The subsequent
`calitree_decision_warrants_v33.py`, `calitree_fallback_routing_v34.py` and
`calitree_regular_aware_v35.py` compare affirmative outcome warrants, supported
regular-judge corrections and regular-aware verdict verification, respectively.
All reuse cached evidence and regular judgments without new model calls.

`verify_calitree_guarded_development_v35.py --output-dir PATH` independently
refits the v34/v35 folds and checks held-source replay, local retention and
accepted merge proofs. `--freeze-forward` freezes supplemental v35 models for
the prepared 36-source comparison. `collect_calitree_guarded_forward_v32.py
--prepare --output-dir PATH` pins its paid execution plan; `--live` requires
separate approval for at most 36 regular calls and 73,728 completion tokens.
See `docs/calitree_guarded_development.md`. Defaults remain unchanged.

`analyze_calitree_guarded_forward_v35.py --bounds --output-dir PATH` enumerates
all possible regular labels without calls; `--report` scores the completed
matched baseline and independently reconciles its durable request/token ledger.
`verify_calitree_regular_aware_runtime_v35.py --forward-dir PATH --output-dir
NEW_PATH` replays all 432 scenarios through the real optional inference wrapper
with cached evidence and a stub regular judge. `audit_calitree_forward_cache_v35.py
--forward-dir PATH --output-dir NEW_PATH --search-root PATH` searches exact
historical flat-judge slots without reading references for scoring. See
`docs/calitree_guarded_forward_validation.md` for bounds and remaining validation.

The authorized 36-case baseline is now complete. See
`docs/calitree_guarded_forward_results.md`: regular scores 20/36, v27 scores
21/19/21 and verification-only scores 21/19/22. The optional
`VerifiedSemanticJudge` serves that predeclared verification arm by default;
new correction regions require `enable_corrections=True` because they added
false forward acceptances. It always calls regular and preserves all 144 local
routes. `verify_calitree_verified_serving.py` replays the serving default;
`verify_calitree_guarded_forward_completion.py` independently checks all 25
metric arms and the 36-attempt durable budget. No new calls are needed to audit.

### Bank-2 harmful-disagreement coverage (v36)

`calitree_disagreement_coverage_v36r1.py --output-dir NEW_PATH` diagnoses the
accepted errors and fits per tree/regular-label-pair semantic vetoes, protecting
correct prior routes under every possible regular label. All 116 recent cases
are development data for this revision. The final bank-2 guard rejects one
harmful Partial override on a removal task, restoring 19→20/36 while retaining
all 144 local routes. Banks 1/3 stay unchanged. The source-held-out replay does
not improve, so transfer is not claimed.

`verify_calitree_disagreement_coverage_v36r1.py --output-dir PATH` independently
refits all 156 source/bank guards, checks retained prior routes and replays 432
serving scenarios. Both commands are offline. Initial v36 prototype runners and
results are retained; use the `r1` run for the stronger preservation contract.
See `docs/calitree_bank2_disagreement_gate.md` for the exact rule and limitations.

### Teacher-guided semantic rubric and boosted fallback (v70–v72)

`calitree_semantic_rubric_v70.py --output-dir NEW_PATH` reconstructs short
ordered semantic clauses from the frozen visual teacher. The warranted path
adds explicit No/Partial/Yes justification requirements. Prepare its 30 local
inner teacher caches with `prepare_calitree_rubric_teachers_v70.py --output-dir
logs/exps/261023-rubric-inner-teachers-v70 --workers 3`, then run
`calitree_warranted_rubric_v71.py --output-dir NEW_PATH --correction`.

`verify_calitree_semantic_rubric_v72.py --study
logs/exps/261023-warranted-rubric-v71-r2 --output-dir NEW_PATH` checks all native
teacher caches, independently re-induces the selected rubrics, proves semantic
all/any simplification, recounts 144-slot retention and replays 915 actual bound
high-level judgments. All commands are offline; CatBoost1.2.10 is needed for
teacher fitting/auditing, not for portable rubric execution.

The selected warranted hybrid gets 223/276 versus v69's 222/276 in source-held
development, with no losses, 99/99 originals retained, unchanged coverage and
50 focused tests passing. Its final rubric is one three-condition exception;
the ensemble remains the fallback. Standalone prose-only execution and fresh
reserved validation have not been established. Serving defaults are unchanged.
See `docs/calitree_semantic_rubric_v70.md` for code, evidence and scope.

### Local evidence and semantic rubric concepts (v77–v83)

`calitree_grounded_regions_v77.py --prepare --output-dir NEW_PATH` freezes
label-free object-region plans; `--extract` runs the pinned local detector and
encoder. `calitree_region_policy_v78.py --output-dir NEW_PATH` compares explicit
physical experts and region-augmented grade learners on the fixed source folds.
Object binding can fail; an undetected object never automatically proves absence.

`calitree_caption_audit_v79.py --prepare/--extract --output-dir NEW_PATH` audits
bound visible descriptions against existing image vectors.
`calitree_caption_policy_v80.py --output-dir NEW_PATH` evaluates those scalar
comparisons without raw embedding or identifier inputs.

`calitree_nli_rubric_v81.py --prepare/--extract --output-dir NEW_PATH` maps existing
explanations to16 fixed semantic concepts using a pinned local NLI checkpoint.
Extraction uses the isolated vision environment with Metal, native safetensors
and offline model loading; it makes no API calls. NLI supports are language
claims, not image-truth confidence.

`calitree_rubric_score_v82.py --output-dir NEW_PATH` fits a small explicit
additive semantic correction using cached inner source-excluded teacher views.
Add `--with-nli` only after the fixed v81 extraction completes. The boosted score
remains an explicit offset; protected originals veto harmful strengths.
`verify_calitree_local_evidence_v82.py --kind region/caption/score --study PATH
--output-dir NEW_PATH` independently replays native model supports or explicit
score equations and all144 original training slots. Histogram controls receive
saved-support/membership/metric checks only.

`calitree_evidence_pool_v83.py --output-dir NEW_PATH` compares fixed equal-weight
class-support pools and a semantic region qualification route, retaining each
v72 correction's original teacher binding. These pools do not beat v72.
See `docs/calitree_local_evidence_v77.md` for completed results and experiment roots.

### Cached independent experts and semantic routing (v84–v87)

`audit_calitree_regular_views_v84.py --search-root PATH --output-dir NEW_PATH`
finds only exact generic regular-judge request matches, including ordered textual
SOURCE/EDITED markers. It reads no human references and makes no model calls.

`calitree_cached_sol_router_v85.py --output-dir NEW_PATH` compares fixed support
and protection choices for the optional cached Sol view; all source-held folds
and actual original local decisions remain protected. `calitree_sparse_rubric_v86.py`
tests the support change across the full existing semantic evidence.

`verify_calitree_independent_expert_v87.py --study PATH --output-dir NEW_PATH`
cold-replays36 native teachers, re-induces selected gates and runs915 bound
judgments through the exported optional-expert wrapper. The selected replay gets
225/276 with two gains/no losses,99/99 and144/144 retained, and unchanged coverage.
Only15 primary cases have valid cached Sol records; no complete fresh-Sol result
or >85% claim is made. See `docs/calitree_independent_semantic_v87.md` and
`examples/calitree_independent_semantic_v87` for the opt-in artifact and API.

### Independent contrastive-pilot accounting (v88)

`verify_calitree_contrastive_pilot_v88.py --prepared-dir PATH --output-dir NEW_PATH`
reconciles the frozen72-slot v75 plan, source exclusions, actual request hashes,
model routes, token usage/reservations and certificate validity. After collection,
add `--require-complete` to require all72 wrappers and compute paired accuracy,
class confusions and error/control strata. Failures/unresolved cases stay in the
denominator. The auditor makes no API calls or fits and refuses mock artifacts.

### Calibration fitting views and ordered visual grades (v89–v92)

`calitree_source_excluded_calibration_v89.py --output-dir NEW_PATH` separates
source-excluded inner teacher residuals from always-fitted original-source views.
It compares fixed class biases (with/without affirmative grade warrants) and
compact explicit semantic score corrections, retaining the current v72/v87
rule context and priority. The fresh v75 pilot responses never enter fitting.

`calitree_ordered_visual_rubric_v90.py --output-dir NEW_PATH` fits the existing
ordinal and within-task-relative human-score objectives to the stronger frozen
Boolean visual/semantic vocabulary. It compares fixed support blends and
affirmative-warrant controls on the unchanged source folds; ineligible local
retention arms must not be promoted.

`verify_calitree_calibration_controls_v91.py --calibration-study PATH
--ordered-study PATH --output-dir NEW_PATH` cold-loads saved native models,
replays explicit score equations and checks fitting memberships, original
slots, prior-rule priority and coverage. It makes no API/encoder calls.

`audit_calitree_collateral_cap_context_v92.py --output-dir NEW_PATH` is a
read-only logical counterfactual: ignore only material collateral in the Yes
warrant while retaining uncertainty and every other requirement. It saves no
modified evidence, fits no policy and reports no achieved accuracy gain.

### Local task/preservation evidence (v93–v97)

`calitree_prefix_experts_v93.py --output-dir NEW_PATH` audits frozen teacher
stages without fitting. The tested direct-selector oracle tops out at229/276,
so no prefix gate is fitted.

`download_calitree_local_vlm_v94.py --output-dir NEW_PATH --destination LOCAL_PATH`
retrieves the pinned public Qwen3-VL8B safetensors/config files and records hashes;
it uploads no project data. `calitree_local_observer_v94.py` prepares/collects a
12-case local observation diagnostic. `calitree_local_grammar_probe_v95.py` uses
a separately frozen native JSON-constrained profile; no old responses are repaired.

`calitree_local_review_cache_v96.py --prepare --output-dir NEW_PATH` freezes224
observations needed by fixed actual/source-excluded review regions. Collection
uses `--collect` in the isolated vision environment with Metal and offline flags.
Do not start a duplicate while its recorded process is live. Every new input
gets one attempt, and compatible smoke results are reused by exact identity.

`calitree_local_warranted_rules_v97.py --cache COMPLETE_CACHE --output-dir NEW_PATH`
refuses incomplete caches, fits bounded source-held task/preservation clauses
and protects all99 original decisions/144 slots. It scores all276 cases; absent
local evidence and cases outside review retain the existing policy. No policy
is promoted merely from the observation smoke or a partial collection.

See `docs/calitree_local_observer_v96.md` for current status, hardware/runtime
identity, preserved failures, source controls and the next fitting command.

### Local-cache verification and weighted semantic review (v98–v107)

`verify_calitree_local_review_cache_v98.py --cache PATH --output-dir NEW_PATH
--require-complete` cold-replays36 native teachers and reconciles source masks,
raw responses, exact bindings, history and budgets. Without`--require-complete`
the output is explicitly a snapshot and cannot authorize fitting.

`calitree_local_score_v102.py --cache PATH --cache-audit COMPLETE_AUDIT
--output-dir NEW_PATH` tests additive named semantic corrections. Add
`--method tree_residual` for v103:128 depth-two/three residual trees, no raw
visual vectors or IDs. Both score-only and affirmative/review-guarded arms are
measured; original99/144 decisions and all276 scoring cases remain required.

`verify_calitree_semantic_residual_v105.py --cache PATH --cache-audit PATH
--study PATH --output-dir NEW_PATH --candidate contextual_depth2_guarded`
re-induces all six selected models, merges shared weighted clauses, checks5,490
native/portable residuals and replays915 real bound judgments. The verified
guarded result is227/276, up from225. Serving defaults remain unchanged; the
strict235/276 target remains unmet. The opt-in artifact is in
`examples/calitree_weighted_semantic_v105`; its report is
`docs/calitree_weighted_semantic_v105.md`.

`verify_calitree_local_policy_v100.py` and`calitree_local_policy_pipeline_v101.py`
support the earlier compact-rule path; its best224/276 result was not promoted.
`calitree_anchored_semantic_residual_v106.py` compares original-case anchors and
primary-only fitting pools. `calitree_semantic_expert_advantage_v107.py` learns
the paired correctness benefit of an admissible alternative expert. Neither
control raises the maximum above227. All studies use complete audited caches
and make no paid/extraction calls.

### Separate higher-resolution local evidence (v108–v110)

`calitree_high_resolution_observer_v108.py --prepare --previous-cache PATH
--output-dir NEW_PATH` freezes exactly the existing224 review slots with1024
visual tokens/image and512 output tokens, the same checkpoint/prompt/schema,
one worker and no retries. Run`--collect --output-dir PREPARED_PATH` with the
isolated vision runtime, Metal and offline flags. It uploads nothing and never
reuses/replaces a record from the different256-token profile.

`verify_calitree_high_resolution_cache_v109.py --previous-cache PATH
--previous-audit PATH --cache PATH --output-dir NEW_PATH --require-complete`
checks the full profile transformation, unchanged selection, native masks and
response accounting. Omitting the final flag produces only a partial snapshot.

`calitree_high_resolution_pipeline_v110.py` waits for the recorded collector's
terminal result, audits completion and runs the frozen v103 comparison. It
independently verifies a guarded candidate only if it beats227. It never
launches/restarts an observer, changes serving defaults or completes the goal.
Inspect its protocol/state before continuing; do not duplicate a live run.

### Exact shared terms and evidence novelty (v111–v117)

`verify_calitree_semantic_polynomial_v112.py --cache PATH --cache-audit PATH
--study PATH --verified V105_AUDIT --output-dir NEW_PATH` re-induces the selected
six residuals, compiles their Boolean-lattice expansion and compares5,490 native
residuals plus915 bound judgments. The full artifact compresses100 branches to
60 shared terms with unchanged227/276 accuracy, original decisions and routing.
Its artifact is`examples/calitree_weighted_semantic_v112`, selected as the default
AURORA inference version on2026-10-25 through `CaliTreeJudge` and
`run.calitree_current`. Historical explicit-version runners remain reproducible.

`calitree_sparse_interaction_rubric_v113.py` tests12/24 selected interactions;
`calitree_semantic_abstraction_v114.py` removes rationale-word proxies. Neither
comparison beats227. They use complete audited caches and preserve99/144 local
decisions; they do not silently replace the verified artifact.

`calitree_observer_agreement_v115.py --previous-cache PATH --current-cache PATH
--output-dir NEW_PATH` compares completed bound observation fields without
human references. Partial snapshots are labeled and never authorize fitting.

`calitree_effective_image_inputs_v117.py --previous-cache PATH --current-cache
PATH --checkpoint IDENTITY_JSON --output-dir NEW_PATH` hashes every actual CPU
processor tensor under both image budgets without loading model weights or
references. It finds187/224 identical complete inputs,37 different inputs.

`download_calitree_mlx_observer_v116.py --output-dir NEW_PATH --destination
LOCAL_PATH` downloads the pinned public5.95GB Qwen3.5 MLX checkpoint without
authentication or project uploads, retaining12GiB disk headroom. This is an
untested candidate observer; no accuracy claim follows from its download.

### Native MLX semantic-observer diagnostics (v118–v127)

`calitree_mlx_observer_probe_v119.py --prepare/--collect --output-dir PATH`
freezes the same12 balanced original-training cases under the local9B MLX
profile. The successful r4 run produces12 valid records; earlier setup failures
remain separate. `verify_calitree_mlx_probe_v120.py --probe PATH
--previous-probe PATH --checkpoint IDENTITY --output-dir NEW_PATH
--require-complete` replays raw outputs, processor inputs, source bindings,
history and budgets. Its warrant-only diagnostic is4/12 versus the old5/12;
this is not pipeline accuracy or a reason to promote the model.

`calitree_evidence_first_probe_v122.py` tests two new native field-order
profiles. `verify_calitree_evidence_first_v123.py` checks their actual JSON
order,360-character limit and CPU processor replay. The two12-case arms yield
four and three correct warrants, without a policy change.

`calitree_native_sampling_probe_v125.py` compares seeded published instruct
and thinking sampling settings using one shared model. Native thinking/final
channels and all emitted token IDs are retained; unfinished thoughts never
become observations. `verify_calitree_native_sampling_v126.py` independently
replays channels, seeds, processors and budgets. Use`--require-terminal` to
audit a finished experiment that stopped early, and`--require-complete` only
when every planned slot has a response. The instruct arm remains4/12; the
thinking arm stops after three2,048-token truncations and has no accuracy claim.

`download_calitree_large_mlx_v127.py --output-dir NEW_PATH --destination
LOCAL_PATH` fetches the pinned public19.62GB32B checkpoint with12GiB disk
headroom and no task uploads. Existing runtime/records are unchanged by the
download. See`docs/calitree_observer_diagnostics_v126.md` for current status,
cache restoration and70 passing focused tests. No paid API calls are made.

### Larger observer and fixed calibration comparison (v128–v136)

`calitree_large_observer_probe_v129.py` tests the pinned32B model on the same12
training cases. The unbounded profile stops after three consecutive evidence
truncations. `calitree_bounded_large_probe_v131.py` freezes a separate1–360-char
evidence schema and completes12 valid records. `verify_calitree_large_probe_v130.py`
audits both profiles; the bounded warrant-only result is3/12 versus the old5/12,
not pipeline accuracy.

`calitree_large_review_cache_v132.py --prepare --legacy-cache PATH
--legacy-audit PATH --probe PATH --probe-audit PATH --output-dir NEW_PATH`
keeps the fixed224 input/mask union. `--collect` uses one exclusive GPU observer,
exact compatible probe reuse and no retries. `verify_calitree_large_cache_v134.py
--cache PATH --output-dir NEW_PATH --require-complete` checks new raw/native
records and hash-reuses the unchanged36-model source audit. Partial snapshots
never permit fitting.

`calitree_large_semantic_policy_v135.py --cache PATH --cache-audit PATH
--output-dir NEW_PATH` compares eight source-held residual fits and three fixed
guard/score modes. `--legacy-control` uses the old8B cache with the same fitting
algorithm. The legacy control tops out at226/276. Strengths up to2 are selected
fit-only after actual guard fallback, protecting all99/144 original decisions.

`calitree_large_policy_pipeline_v136.py` is the tracked one-shot collector wait,
complete audit and frozen comparison. It never launches/resumes an observer,
promotes a policy or completes the goal. Inspect its live state before any new
dispatch. See`docs/calitree_large_observer_v136.md`.

### Additive whole-policy control (v140)

`calitree_additive_policy_v140.py` fits InterpretML0.7.8 on the same cached source
folds, with named univariate/pairwise tables exported through
`additive_tables_v140.py`. Every915-case native/portable probability comparison
passes before scoring. The16 actual-local-retaining arms score191–213/276 and
are not promoted. Multiclass pair terms are retained explicitly despite their
omission by the library's global visualizer. This is CPU-only; no new image/API
calls are made. The incumbent remains227/276; the235 target is unmet.

### Same-architecture class-balanced training (v141–v142)

`calitree_class_balanced_v141.py --output-dir NEW_PATH --workers 3` gives each
training grade equal total weight while retaining every fitting example. It
refits the same depth8/1200-tree visual CatBoost and depth2/128-tree semantic
correction on the existing five outer source folds and30 inner teacher folds.
Original-case anchor weights are normalized within each grade, so protecting
the99 local cases does not undo equal class mass. No new model/encoder calls
or reserved sources are used.

The primary arm balances both learned layers. Separate arms balance only the
semantic head or main booster, and the unchanged control must reproduce227/276.
Older semantic/expert rules retain their original teacher context and priority.
Review routing is recomputed; missing cached local observations keep the new
base decision. Every comparison uses the same276 evaluation cases and reports
ordinary/balanced accuracy, macro F1, per-grade recall, local retention and
coverage. `--head-only` runs the two frozen-teacher arms alone.

`--reuse-teachers STOPPED_RUN` is an explicit recovery option for the initial
parent-directory race. It accepts only complete fits with identical training
contracts, weight receipts, loaded-model predictions and an AST-equivalent
fitting function after the single parent-mkdir correction. The original run
remains interrupted and no partial model is repaired or substituted.

`verify_calitree_class_balanced_v142.py --study RUN --output-dir NEW_PATH`
independently executes native classifier JSON, re-induces all semantic heads,
checks the compressed named terms, source exclusions, equal class weights,
denominators, actual routes and99/144 local protection. This is a development
comparison; it does not change serving defaults or promote a new policy.

The completed primary balanced-both-layers arm scores217/276 (78.6%),67.4%
balanced accuracy and66.6% macro F1, versus227/276 (82.2%),67.9% and70.6% for
the reproduced control. Balancing only the semantic head scores221/276 (80.1%).
All99/144 original checks and273 upstream coverage are retained. See
`docs/calitree_class_balanced_v142.md` for all seven arms and the routing audit.

### Further balanced-accuracy search (v143–v148)

`calitree_compact_balance_v143.py --output-dir NEW_PATH` optimizes final balanced
accuracy with two score offsets or two ordinal cutoffs, keeping original-case
protection and optionally requiring semantic warrants or fitting recall floors.
Its eight arms do not improve selected v112.

`calitree_balanced_patches_v144.py --output-dir NEW_PATH` learns at most four
class-normalized-gain semantic corrections, each seeded by a grade warrant.
`calitree_balanced_experts_v146.py --output-dir NEW_PATH` additionally supports
review regions selecting the existing regular judge. The independent auditor
`verify_calitree_balanced_search_v145.py --output-dir NEW_PATH` re-induces all168
small models and checks153,720 scalar/native rows across these three studies.

`calitree_tempered_balance_v147.py --output-dir NEW_PATH --workers 3` trains18
main classifiers using moderate inverse-frequency exponents0.25/0.5/0.75 with
the frozen semantic head. `verify_calitree_tempered_balance_v148.py --study PATH
--output-dir NEW_PATH` executes every main classifier/head from native numeric
JSON and checks weights, source masks, protected strengths and metrics.

These CPU-only experiments use the isolated pinned CatBoost1.2.10 dependency
at `/tmp/calitree-catboost-v143` via `PYTHONPATH=/tmp/calitree-catboost-v143:.`.
No new image/encoder/observer/API calls or reserved-source reads occur.

The best exploratory four-rule arm scores71.1% balanced accuracy and81.9%
overall accuracy, versus67.9%/82.2% for selected v112. Partial recall falls
53.6%→42.9%, so it is not selected. All99/144 original checks and273 coverage
remain intact. See `docs/calitree_balanced_accuracy_v148.md` for all37 arms,
independent audits and the distinction between reference-informed oracle
headroom and actual learned performance. The80% balanced target remains unmet.
