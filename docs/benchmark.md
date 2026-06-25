# VEJudge Benchmark Pipeline

The benchmark measures the **agreement gap between human annotators and LLM/VLM judges**
on AI-edited videos. It runs the judges on the same rendered outputs humans rated, aligns
each judge signal to the matching human dimension, and reports correlation / error metrics
per dimension and per category.

See `data.md` for the inputs and `architecture.md` for the package layout.

---

## Stages

```
 dl_human_annotations            dl_peanut_eval
 (load + aggregate 287 files)    (resolve rendered video + curate text inputs)
            │                                │
            └──────────── match on item_id ──┘      item_id = "project::prompt_idx::model"
                              │
                              ▼
                   workflow.run_judges_for_sample
                   (text M1/M3 → GPT, video M2/M4/M5/M6 → Gemini, via lm_engine)
                              │
                              ▼
                   postprocessing.align
                   (judge field → human dimension; derive_overall for pairwise)
                              │
                              ▼
                   core.eval.metrics
                   (Spearman, Kendall, MAE, QWK, pairwise; per-category)
                              │
                              ▼
                   benchmark.report  +  logging.exp_logger
                   (gap_result.json, aligned_pairs.csv, gap_report.xlsx/chart)
```

Driver: `vejudge/benchmark/human_gap/runner.py` (`HumanGapBenchmark`), exposed as the
`vejudge-bench` CLI.

1. **Match.** Load + aggregate human annotations (filtered to the model), enumerate
   judge-able items from the rendered-output tree, take the intersection, apply `--limit`.
2. **Judge.** For each item build a `JudgeSample` and run the selected judges. Text judges
   see the instruction + transcript + assembly plan; video judges get the rendered MP4
   (whole video, base64 — Strategy A). Each judge call is parsed and validated (1–5 range,
   required fields, non-empty rationale) with failures flagged, not defaulted.
3. **Align.** Map each judge output onto the human dimension it measures (table below) and
   build tidy `(item_id, dimension, human, judge_raw)` rows.
4. **Score the gap.** Per dimension: Spearman, Kendall, MAE, QWK — overall and broken down
   by `use_case` and `model`. Pairwise preference accuracy from `overall_ranking`.
5. **Report + log.** Write everything to a timestamped experiment run dir.

The per-item and per-judge views can be (re)built for any past run without gateway calls:
`python -m vejudge.benchmark.per_item logs/exps/<run>-exps` (reads `aligned_pairs.csv`,
writes `per_item_gap.csv` + `per_judge_gap.csv` + `per_judge_summary.csv`, and prints both a
per-video and a per-judge table). The per-item means average over the 9 human dimensions, so
they over-weight M5 (which backs 5 of them); the **per-judge-signal** view counts each judge
once and is the fairer per-judge read. M1/M2 gates and M4 are reported when
`judge_outputs.json` is present (runs from this version on).

A `tqdm` progress bar tracks the item loop (showing the current item, the judge in
flight, and the running aligned-pair count). Per-item/per-judge INFO detail goes to
`run.log` so it doesn't clobber the bar; the bar prints to the console.

---

## Human ↔ judge alignment

| Human dimension | Judge signal |
|---|---|
| `video_addresses_prompt` | M3 `score_1_to_5` |
| `voiceover_matches_visuals` | M6a `voiceover_visual_match.score_1_to_5` |
| `abrupt_cutoffs_voiceover` | M6b `voiceover_continuity.score_1_to_5` |
| `abrupt_cutoffs_video` | M6c `visual_continuity.score_1_to_5` |
| `story_flow_voiceover` / `story_flow_visuals` | M5 `score_1_to_5` |
| `section_placement_opening/middle/closing` | M5 `score_1_to_5` |
| `overall_ranking` (pairwise) | `derive_overall` = mean(M3, M4, M5, M6 overall) |

Defined in `vejudge/postprocessing/align.py`.

---

## Running it

Real (billable) gateway calls are **gated**: pass `--live` or set `VEJUDGE_ALLOW_LIVE=1`.
Without authorization, the benchmark refuses unless `--dry-run` is set.

```bash
# Estimate scope/cost — no gateway calls, no auth needed
vejudge-bench --dry-run --models peanut --projects prj-paris-2025

# Real run on a tiny subset (requires --live)
vejudge-bench --limit 2 --models peanut --projects prj-paris-2025 --judges M3,M5,M6 --live

# Text-only (cheap; no video upload)
vejudge-bench --projects prj-paris-2025 --judges M1,M3 --skip-video --live
```

| Flag | Purpose |
|---|---|
| `--models` | model to evaluate (v1: `peanut`) |
| `--projects` | comma list of `prj-*` (default: all) |
| `--judges` | comma list e.g. `M3,M5,M6` (default: all M1–M6) |
| `--limit N` | cap items — the cost guardrail |
| `--skip-video` | run text judges only (no video upload) |
| `--dry-run` | resolve items + estimate calls, no gateway |
| `--live` | authorize real calls |
| `--concurrency N` | parallel **text** judge calls (1 = sequential); also the video default |
| `--video-concurrency N` | parallel **video** judge calls (defaults to `--concurrency`; ~4–8) |

## Parallelism & rate limits

Judge calls are independent and stateless, so the runner can fan them out across a thread
pool (`--concurrency N`). The engine uses blocking `requests` (releases the GIL on I/O), the
history writer is lock-guarded, and engines are shared read-only across threads — so thread
concurrency is safe; no multiprocessing needed.

Measured gateway limits (via `run/probe_endpoint.sh`, a LiteLLM v3 proxy):

| Limit | Value |
|---|---|
| Per-user requests | 600 / min (`x-ratelimit-user-limit-requests`) |
| Provider requests | 5000 / min |
| Provider tokens | 5,000,000 / min |
| Observed clean concurrency | 16 (no 429s, p50 ~1.3s) |

**Endpoint health:** the primary endpoint is intermittently down (returns 401 / connection
reset). Before running, each benchmark probes both endpoints with one tiny call each and
reorders to a **working endpoint first** (`vejudge.lm_engine.health`; opt out with
`--no-health-check`); the per-call failover remains the safety net. Check manually with
`run/check_endpoints.sh`.

The base run is only ~102 calls, so the **rate limit is not the bottleneck**. The real
limiters for video judges are **upload bandwidth** (~4 GB of base64 across re-uploads) and
**memory** (base64 of large MP4s). Because text and video have different ideal concurrency,
the runner uses **two independent thread pools that run simultaneously**: `--concurrency`
caps text judges (can be high, e.g. 8) and `--video-concurrency` caps video judges (keep
modest, ~4). The transport retries **transient failures** — HTTP 429/408/5xx and network
errors (connection reset / read timeout) — on the same endpoint with backoff before failing
over to the mirror; large video payloads occasionally trigger upstream 502/503 from the
proxy, which this recovers. With these settings the ~45–75 min sequential estimate drops to
roughly ~10–20 min.

`run_base_benchmark.sh` defaults to `--concurrency 8 --video-concurrency 4`.

---

## Outputs (per run)

Written to `logs/exps/<YYMMDD-HH:MM:SS>-exps/` (Experiments logging convention):

| File | Contents |
|---|---|
| `run.log` | pipeline execution log |
| `llm-histories.log` | one JSONL line per LM call (model, prompt hash, tokens, latency) |
| `run_config.json` | exact run config (models, judges, limit, prompt versions) |
| `gap_result.json` | per-dimension + per-category metrics, pairwise accuracy |
| `aligned_pairs.csv` | tidy `(item_id, project, model, use_case, dimension, human, judge_raw)` |
| `per_item_gap.csv` | one row per video: mean human/judge, signed + abs gap, per-dimension gap (worst first) |
| `per_judge_gap.csv` | one row per (video, distinct judge signal) — each judge counted once (M5 not over-weighted) |
| `per_judge_summary.csv` | one row per judge signal across items: mean human/judge, gap, MAE, Spearman |
| `judge_outputs.json` | slimmed parsed output + validation per (item, judge), incl. M1/M2/M4 not in the crosswalk |
| `gap_report.xlsx` / `.csv` | dimension-level metrics table |
| `chart_gap_by_dimension.png` | Spearman + MAE bars (if matplotlib present) |
| `dry_run.json` | (dry-run only) matched items + estimated call counts |

`gap_result.json` shape:
```json
{
  "benchmark_id": "...", "config": {...}, "n_items": N,
  "per_dimension": {
    "<dim>": {"judge_signal": "...", "n": K,
              "spearman": .., "kendall": .., "mae": .., "qwk": ..,
              "by_category": {"use_case": {...}, "model": {...}}}
  },
  "pairwise_preference_accuracy": {"overall": .., "n_pairs": ..},
  "calibration_error": null, "aligned_pairs_path": "aligned_pairs.csv"
}
```

---

## Robustness grid (`vejudge-robust`)

To separate **judge sampling randomness** from **small-n correlation noise**, the robustness
harness sweeps a grid of sampling **temperature** (rows) × **repeats** (columns), running the
full base benchmark per cell (`vejudge.benchmark.robust`; wrapper `run/run_base_benchmark_robust.sh`).
`vejudge-bench` itself gained `--temperature`.

Per temperature × judge signal it reports (`robust_summary.csv`):
- `human_spearman_mean` / `human_spearman_std` — how the human-agreement Spearman moves across repeats
- `within_item_std_mean` — mean per-item std of the judge's score across repeats (0 = repeatable)
- `run_to_run_spearman_mean` — mean pairwise rank agreement of the judge with itself across repeats

`robust_grid.csv` adds, per cell, a **bootstrap 95% CI** on the Spearman (resampling the ~13
items). Reading it:
- within-item std ≈ 0 at temp 0 but > 0 at higher temp ⇒ swings are **sampling-driven**
- within-item std low but human-Spearman std high / CI wide ⇒ **small-n noise** (need more items)
- run-to-run Spearman ≈ 1 ⇒ the judge ranks videos the same each run; ≈ 0 ⇒ re-rolled each time

**Fail-fast:** if a cell's judge calls *all* error (e.g. auth/credit/gateway death), the run
raises `AllJudgeCallsFailed` rather than writing an empty cell; the grid then aborts the
remaining cells (continuing would just repeat the failure for hours), still writes the
analysis for completed cells, and flags the abort in `robust_report.md` (exit code 1).

Default grid: temperatures {0.0, 0.3, 0.7, 1.0} × 5 repeats = 20 cells (~3.5 h, ~2040 calls).
Outputs: `logs/exps/<ts>-robust/` (`robust_grid.csv`, `robust_summary.csv`, `robust_report.md`,
`cells.json`) with each cell **nested inside** as `<ts>-robust/temp<T>_rep<N>-exps/` (its own
full per-cell artifacts). Gated by `--live`; `--dry-run` estimates cost.

## Resuming interrupted runs (`--continue`)

Long runs can drop partway when the gateway is unstable. Every run **checkpoints each
completed judge call** to `<run_dir>/judge_results.jsonl` (generic `vejudge.checkpoint.
CheckpointStore`), persisting only successful calls. `--continue [PATH]` re-opens a run and
reuses those, redoing only the missing units:

```bash
vejudge-bench --continue                      # resume the most recent benchmark run
vejudge-bench --continue logs/exps/<ts>-exps  # a specific run
vejudge-robust --continue                     # resume the most recent grid
vejudge-robust --continue <dir> --dry-run     # show how many cells remain (no calls)
```

- For a single run, resume skips already-judged `(item, judge)` pairs and only calls the
  engine for the rest; the run config is read from `run_config.json` (CLI grid flags ignored).
- For the grid, resume skips complete cells (a cell is complete when its
  `per_judge_summary.csv` has data) and **resumes a half-finished cell's own checkpoint**, so
  it doesn't redo ~100 calls; the analysis is rebuilt over all complete cells on disk.
- Checkpoints are **run-scoped** — robustness repeats are separate run dirs, so they stay
  independent (never collapsed by a shared cache). Failed calls are not checkpointed, so they
  retry on the next `--continue`.

## Scope & limitations (v1)

- **peanut model only.** Other models need fuzzy prompt↔folder resolution.
- **Raw gap, no calibration.** `LinearCalibrator` is scaffolded; fit it after reviewing raw
  numbers (only ~17 matched items, so a train/test split is tight). `calibration_error`
  stays `null` until then.
- **Pairwise accuracy is `n_pairs=0`** in v1: it needs ≥2 competing outputs per cell, which
  requires multiple models. The code lights up automatically once they're added.
- **Whole-video upload (Strategy A).** Large videos (e.g. 77 MB) base64-upload slowly;
  frame/clip sampling (`preprocessing/` templates) is a future input-strategy variant.
- **Sparse human labels.** Only ~29% of annotations are complete; per-dimension `n` varies
  because empty annotator scores are dropped before averaging.
