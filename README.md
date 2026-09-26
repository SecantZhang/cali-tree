# Criti-Cal

Calibrated LLM/VLM-as-a-judge pipeline for video-editing outputs, with a benchmark that
measures the **agreement gap between human annotators and LLM judges**.

The distribution and command names use `criti-cal`; Python imports use `critical`.

See `CLAUDE.md` for conventions, `docs/architecture.md` for the intended system design,
and `critical/interface/interface.md` for the node interface.

## Install

From the repository root:

```bash
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
criti-cal-bench --dry-run --models peanut --projects prj-paris-2025

# 3) Smoke-test OpenAI with one tiny call (real call -> needs --live)
criti-cal-smoke --engine gpt --text "reply with the single word OK" --live

# 4) Run the gap benchmark on a tiny subset (real video judge calls -> needs --live)
criti-cal-bench --limit 2 --models peanut --projects prj-paris-2025 --judges M3,M5,M6 --live
```

**Real gateway calls are gated.** Any billable call requires `--live` (or
`CRITICAL_ALLOW_LIVE=1`). Without it, `criti-cal-bench` refuses unless `--dry-run` is set,
and `criti-cal-smoke` refuses outright. Unit tests, dry-runs, and item matching never call out.

Outputs land in `logs/exps/<YYMMDD-HH:MM:SS>-exps/`: `run.log`, `llm-histories.log`,
`run_config.json`, `gap_result.json`, `aligned_pairs.csv`, and a `gap_report.*` table/chart.

## Running the visual interface

A ComfyUI-style node-graph interface (`critical/interface/`, spec in
`critical/interface/interface.md`) includes
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

## Code architecture

| Location | Responsibility |
|---|---|
| `critical/database/` and `critical/preprocessing/` | Load evaluation data and prepare media or edit evidence. Loaders cover Peanut, VE-Bench, ImagenHub, Aurora, and EditInspector; the benchmark CLI currently targets Peanut. |
| `critical/lm_engine/` | Call model providers through a shared engine interface and record usage. |
| `critical/core/judge/`, `critical/core/prompts/`, and `critical/core/rubric/` | Define prompts and rubrics, run judges, and validate their outputs. |
| `critical/core/calibration/` | Fit and apply score and semantic calibration models. |
| `critical/core/optimization/prompt/` | Optimize prompts: CaliTree's builder, model, geometry, metrics, and routing live in `calitree/`; the TextGrad adapter lives in `textgrad/`; the GEPA frozen prompt loader and artifact live in `gepa/`. |
| `critical/evidence/`, `critical/logging/`, and `critical/checkpoint.py` | Store evidence, model call histories, run logs, and resumable judge results. |
| `critical/interface/` and `web/` | Expose the workflow as backend nodes and a browser graph editor. The calibration node executors remain in `critical/interface/node_calibration/`. |
| `critical/benchmark/`, `critical/core/eval/`, and `critical/workflow/` | Run the human agreement benchmark, compute evaluation metrics, and route judges to text or video engines. |

The offline GEPA optimizer remains in `run/gepa_baseline/`. Experiment scripts and example
workflow graphs live in `run/` and `workflows/examples/`.

The edit-aware path stores immutable clips/frames under `CRITICAL_EVIDENCE_ROOT` and
queryable manifest metadata in SQLite. Similarity retrieval remains deferred.
