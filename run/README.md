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
