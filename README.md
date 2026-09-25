# VEJudge

Calibrated LLM/VLM-as-a-judge pipeline for video-editing outputs, with a benchmark that
measures the **agreement gap between human annotators and LLM judges**.

See `CLAUDE.md` for conventions and `docs/` for architecture, rubric, and research notes.

## Install

```bash
cd projects/vejudge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,interface,video]"
./run/check_video_deps.sh
```

## Credentials

The judge clients use the **official OpenAI and Google Gemini APIs** directly.
Configure either or both providers with environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export GEMINI_API_KEY="your-google-ai-studio-key"
```

Alternatively, copy `.env.example` to `.env` in this project, or open **Settings → API
Credentials** in the web interface and save a separate key for each provider. The default
URLs are `https://api.openai.com/v1` and
`https://generativelanguage.googleapis.com/v1beta`; no company endpoint is needed.
`GOOGLE_API_KEY` is accepted as an alias for `GEMINI_API_KEY`.

The `gpt` engine uses OpenAI; `gemini` uses Google's native GenerateContent API, including
image/video inputs. AURORA judge and optimizer clients infer the provider from their model
IDs. Tree embeddings use their own model's credentials (OpenAI for `text-embedding-*`).
Existing experiment model IDs and historical results are unchanged.

Old proxy env vars, unscoped saved credentials, and `.env-raw` are **ignored by default**.
See [provider configuration](docs/providers.md) for resolution rules, model compatibility,
media limits, endpoint overrides, and explicit legacy mode.

## Quickstart

```bash
# 1) Unit tests — no creds, no network
pytest tests/unit -q

# 2) Estimate cost without calling the gateway (no auth needed)
vejudge-bench --dry-run --models peanut --projects prj-paris-2025

# 3) Smoke-test OpenAI with one tiny call (real call -> needs --live)
vejudge-smoke --engine gpt --text "reply with the single word OK" --live

# 4) Run the gap benchmark on a tiny subset (real video judge calls -> needs --live)
vejudge-bench --limit 2 --models peanut --projects prj-paris-2025 --judges M3,M5,M6 --live
```

**Real gateway calls are gated.** Any billable call requires `--live` (or
`VEJUDGE_ALLOW_LIVE=1`). Without it, `vejudge-bench` refuses unless `--dry-run` is set,
and `vejudge-smoke` refuses outright. Unit tests, dry-runs, and item matching never call out.

Outputs land in `logs/exps/<YYMMDD-HH:MM:SS>-exps/`: `run.log`, `llm-histories.log`,
`run_config.json`, `gap_result.json`, `aligned_pairs.csv`, and a `gap_report.*` table/chart.

## Running the visual interface

A ComfyUI-style node-graph interface (`vejudge/interface/`, spec in `interface.md`) includes
the whole-video path plus an edit-aware path: **Edit Decomposition → Area Judge → Area
Aggregation → Eval/Edit-Aware Calibration**. It is dry-run by default; every real Judge or
Area Judge call still needs `--live`.

```bash
pip install -e ".[interface,video]"
./run/check_video_deps.sh
./run/run_interface.sh          # backend: http://127.0.0.1:8000

cd web && npm install && npm run dev   # frontend: http://127.0.0.1:5173 (see web/README.md)
```

Graph runs land in `logs/exps/<ts>-exps/` exactly like a CLI run (tagged
`"benchmark": "interface_graph"`), and saved workflows live under `workflows/`. See
`workflows/examples/quick_eval.json` for the whole-video path and
`workflows/examples/edit_aware_calibration.json` for the decomposed path. The interface
recursively mirrors these folders; save a graph as `folder/name` to organize it under
`workflows/folder/name.json`.

## What it does

1. **lm_engine** (`vejudge/lm_engine/`) — reusable engines over the official provider APIs
   (`generate(prompt, media_inputs, schema) -> dict`), Gemini default for video, GPT for
   text, with endpoint failover and per-call history logging.
2. **judges** (`vejudge/core/`) — the 6 metrics M1–M6 (assembly/render failure, prompt
   completeness, visual alignment, edit coherence, AV sync), wrapping `lm_engine`.
3. **loaders** (`vejudge/database/`) — peanut rendered-output samples + human annotations.
4. **benchmark** (`vejudge/benchmark/`) — aligns judge signals to human dimensions and
   reports per-dimension / per-category Spearman, Kendall, MAE, and QWK.

The edit-aware path stores immutable clips/frames under `VEJUDGE_EVIDENCE_ROOT` and
queryable manifest metadata in SQLite. Similarity retrieval remains deferred.
