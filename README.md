# VEJudge

Calibrated LLM/VLM-as-a-judge pipeline for video-editing outputs, with a benchmark that
measures the **agreement gap between human annotators and LLM judges**.

See `CLAUDE.md` for conventions and `docs/` for architecture, rubric, and research notes.

## Install

```bash
cd projects/vejudge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Credentials

The LLM judges call the Adobe **Pluto** OpenAI-compatible gateway. Credentials are read
from the repo-root `.env-raw` automatically, or from env vars (which take precedence):

```bash
export CHAT_GPT_API_KEY=sk-...
export OPENAI_COMPAT_BASE_URL=https://.../   # primary endpoint
export LLM_PROXY_MIRROR_URL=https://.../      # optional failover
```

## Quickstart

```bash
# 1) Unit tests — no creds, no network
pytest tests/unit -q

# 2) Estimate cost without calling the gateway (no auth needed)
vejudge-bench --dry-run --models peanut --projects prj-paris-2025

# 3) Smoke-test the gateway with one tiny call (real call -> needs --live)
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

A ComfyUI-style node-graph interface (`vejudge/interface/`, spec in `interface.md`) is
available with 3 of its 8 planned node types wired to real data: **Dataset**, **Judge**,
**Eval**. It's a visual front-end over the same CLI — dry-run by default, and a real Judge
Node run still needs `--live` (a confirm dialog in the UI authorizes it).

```bash
pip install -e ".[interface]"   # fastapi/uvicorn/pydantic/websockets — not a base dependency
./run/run_interface.sh          # backend: http://127.0.0.1:8000

cd web && npm install && npm run dev   # frontend: http://127.0.0.1:5173 (see web/README.md)
```

Graph runs land in `logs/exps/<ts>-exps/` exactly like a CLI run (tagged
`"benchmark": "interface_graph"`), and saved workflows live under `workflows/` — see
`workflows/examples/quick_eval.json` for the `Dataset(peanut) + Dataset(human_annotations) →
Judge → Eval` example.

## What it does

1. **lm_engine** (`vejudge/lm_engine/`) — reusable engines over the Pluto gateway
   (`generate(prompt, media_inputs, schema) -> dict`), Gemini default for video, GPT for
   text, with endpoint failover and per-call history logging.
2. **judges** (`vejudge/core/`) — the 6 metrics M1–M6 (assembly/render failure, prompt
   completeness, visual alignment, edit coherence, AV sync), wrapping `lm_engine`.
3. **loaders** (`vejudge/database/`) — peanut rendered-output samples + human annotations.
4. **benchmark** (`vejudge/benchmark/`) — aligns judge signals to human dimensions and
   reports per-dimension / per-category Spearman, Kendall, MAE, and QWK.

v1 scope: the `peanut` model; calibration is scaffolded but deferred (raw gap first).
