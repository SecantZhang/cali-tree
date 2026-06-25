# VEJudge — Video Editing Judge

## Project Purpose

VEJudge is a calibrated LLM/VLM-as-a-judge pipeline for video editing outputs. Given source assets, a user edit instruction, and the final edited video, the system predicts a human-aligned quality score and produces a grounded, structured rationale. The core challenge is not video generation — it is evaluation: making a multimodal judge reliable, human-aligned, cost-efficient, and usable at scale.

The main research objective is **calibration** — mapping raw judge outputs to human evaluator scores with high agreement, low bias, and interpretable failure modes.

See `../intro/overview.md` for the full problem statement and `../intro/lm_judge_video_tutorial.md` for the implementation tutorial.

---

## Documentation Map

Reference material lives in `docs/` to keep this file focused on conventions:

- **Architecture & systems design** → `docs/architecture.md` — intended package structure, storage/system components, and testing & benchmarking conventions.
- **Data description** → `docs/data.md` — source data, rendered outputs, and human annotations, with their schemas and join keys.
- **Benchmark pipeline** → `docs/benchmark.md` — the human-vs-judge gap pipeline, CLI, call gating, and outputs.
- **Evaluation rubric & data schemas** → `docs/rubric.md` — scoring schema and rubric definitions.
- **Research notes** → `docs/research.md` — judge input strategies, evaluation metrics, common failure modes, and the first-experiment checklist.
- **References & background reading** → `docs/references.md` — bibliography and in-repo background docs.

---

## Running the Benchmark

Use the wrapper scripts in `run/` (each passes extra flags through to the CLI; see
`run/README.md` for the full table). First-time order:

```bash
./run/setup_env.sh            # once: create .venv + install (no gateway calls)
./run/run_tests.sh            # free: mocked unit/integration suite
./run/smoke_test_gateway.sh   # one cheap real call: validate gateway/creds/failover
./run/estimate_cost.sh        # free dry-run: matched items + estimated call counts
./run/run_base_benchmark.sh   # the base benchmark: full raw gap, M1–M6, all peanut items
```

Cheaper iteration: `run/run_text_only.sh` (text judges, no video upload) or
`run/run_quick_subset.sh --limit 1` (full pipeline, tiny subset).

**Robustness:** `run/run_base_benchmark_robust.sh` sweeps a temperature × repeats grid
(`vejudge-robust`; `vejudge-bench` also takes `--temperature`) and reports judge
self-consistency + bootstrap CIs to separate judge sampling variance from small-n
correlation noise. The default grid is ~20 full runs (~3.5 h) — dry-run first, run in
background. Outputs go to `logs/exps/<ts>-robust/`.

**Parallelism:** judge calls are independent and run in two simultaneous pools —
`--concurrency` caps text judges, `--video-concurrency` caps video judges (defaults to
`--concurrency`). The base script uses `--concurrency 8 --video-concurrency 4`. The Pluto
gateway allows ~600 req/min per user and handled concurrency 16 cleanly in probing, so the
rate limit isn't the bottleneck for these small runs — video judges are bound by upload
bandwidth/memory, hence ~4–8 there. The transport retries transient failures (HTTP
429/408/5xx and connection reset / read timeout) on the same endpoint with backoff before
failing over to the mirror — large video payloads occasionally trigger upstream 502/503 from
the proxy, which this recovers. Use `run/probe_endpoint.sh` to (re)measure the gateway's limits.

**Endpoint health:** the primary endpoint is intermittently down (401/connection reset). Each
benchmark probes both endpoints first and **prefers a working one** (skipping a dead primary)
via `PlutoCreds.preferred`; failover stays the safety net. Disable with `--no-health-check`;
check manually with `run/check_endpoints.sh` (`vejudge.lm_engine.health`).

**Progress:** a real benchmark shows a `tqdm` progress bar over judge tasks (current
item + judge, running count). To keep the bar readable, per-item/per-judge INFO logging is
routed to `run.log` rather than the console.

**Resume (`--continue`):** every run checkpoints each successful judge call to
`<run_dir>/judge_results.jsonl` (generic `vejudge.checkpoint.CheckpointStore`). `vejudge-bench
--continue [PATH]` / `vejudge-robust --continue [PATH]` re-open a run (default: the most
recent of that kind) and redo only the missing units — single runs skip done `(item, judge)`
pairs; the grid skips complete cells and resumes a half-finished cell's checkpoint. Checkpoints
are run-scoped (repeats stay independent); failed calls aren't checkpointed, so they retry.

**Call gating:** real (billable) gateway calls require `--live` (or `VEJUDGE_ALLOW_LIVE=1`).
`vejudge-bench` refuses a non-dry-run without it; `vejudge-smoke` refuses outright. Dry-runs,
item matching, and the test suite never call out. Always `estimate_cost.sh` before a real run —
the base run is the slow/expensive path because video judges base64-upload each rendered MP4.

Outputs land in `logs/exps/<YYMMDD-HH:MM:SS>-exps/` per the Logging Conventions below;
see `docs/benchmark.md` for the result schema.

---

## Module Conventions

### Templates / Abstract Bases

Every module family (database loaders, LM engines, preprocessors) has an abstract template. New implementations subclass the template — never bypass it. This ensures components are swappable without changing downstream code.

### LM Engine (`lm_engine/`)

- All engines expose a unified `generate(prompt, media_inputs, schema) -> dict` interface.
- Media inputs are preprocessed references (frame paths, clip paths, transcript strings), never raw video bytes.
- All calls log model name, version, prompt hash, and token counts to `llm-histories.log`.

### Preprocessing (`preprocessing/`)

- All preprocessing artifacts are cached by `(item_id, preprocessing_config_hash)`. Never re-extract frames or transcripts that already exist.
- Supported artifact types: sampled frames, keyframes, short clips, ASR transcript, OCR text, captions, shot boundaries, audio event labels, blur/flicker metrics.
- The `eval/` subdir holds scripts that measure preprocessing quality (e.g., keyframe coverage, transcript WER).

### Judge (`vejudge/judge`)

- Validates all LM outputs: JSON validity, score ranges (1–5), required fields, non-empty rationale.
- Invalid or missing fields are flagged, not silently defaulted.
- Segment-level aggregation formula:
  ```
  overall_score = min(weighted_avg(segment_scores), severe_error_cap)
  ```
  The cap prevents catastrophic segments from being hidden by many good ones.

### Calibration (`vejudge/calibration`)

- Default first baseline: linear regression over judge sub-scores + per-category bias term.
- Always trained on data disjoint from the held-out test set.
- Every calibration model is versioned in a calibration registry.
- Supported models: linear regression, ordinal regression, isotonic regression, Platt-style (binary), Bradley-Terry (pairwise), ensemble stacking, Bayesian (small data).
- Recommended first baseline formula:
  ```
  calibrated_score =
    w0 + w1*overall + w2*instruction_alignment + w3*source_preservation
    + w4*temporal_consistency + w5*visual_quality + category_bias[edit_category]
  ```

### Prompts (`vejudge/prompts/`)

- Templates are versioned files, not inline strings. Every experiment records prompt name + version.
- Absolute multi-dimensional scoring is the default template.
- For pairwise runs, swap A/B order and aggregate both directions to reduce position bias.

### Workflow (`workflow/`)

- Connects modules as a DAG. Each node corresponds to one module (db loader, preprocessor, judge, calibration).
- Maps directly to the ComfyUI-style nodes in `interface/`.

---

## Logging Conventions

### Experiments logging

Log files go in `logs/exps/<YYMMDD-HH:MM:SS>-exps/`. Each run directory must contain:
- `run.log` — pipeline execution log
- `llm-histories.log` — full LLM request/response history (prompt, response, token counts)

Experiment configs (model name, prompt version, preprocessing config, calibration version) must be saved alongside logs so any run is fully reproducible.

### Updates logging

Lives in `logs/updates/`. Every change a coding agent makes to the codebase writes to both tiers. One **update** = one coherent unit of work (a feature, fix, or refactor), not one file edit — group related edits into a single entry sharing one timestamp id.

- **`logs/updates/updates_summary.md`** — append-only. One compact block per update (newest first), never edited retroactively. Each block links to its detail file and contains:
  ```
  ## 260501-22:00:04 — <short title of the change>
  - Type: feature | fix | refactor | docs | chore
  - Scope: <modules / files touched>
  - What: <one or two lines on what changed>
  - Why: <one line on the motivation>
  - Details: logs/updates/details/260501-22:00:04-updates.md
  ```
- **`logs/updates/details/<YYMMDD-HH:MM:SS>-updates.md`** — the full record of one update. Use this structure:
  ```
  # 260501-22:00:04 — <short title of the change>

  ## Motivation
  <what prompted the change; the problem or request it addresses>

  ## Changes
  - <file/module>: <what changed>
  - ...

  ## Design decisions
  <key choices made and the alternatives rejected, with reasons>

  ## Verification
  <how the change was checked: tests run, commands, manual checks>

  ## Follow-ups
  <known gaps, TODOs, or risks left for later — or "none">
  ```
  Write an entry for every change, including ones that were reverted or left incomplete (record why).

#### Rules

- `updates_summary.md` is an **index**, not a store: keep the full record in the detail file, one block per update in the summary.
- Never reuse a timestamp id; never overwrite an existing detail file or summary block.
- Append newest entries at the top of `updates_summary.md` so the latest state is visible first.