# VEJudge Architecture

> The directory tree below is the **intended (aspirational) layout**. Most of it does not exist on disk yet — it documents the target structure as code is built out.

## Project Structure

```
root/
├── logs/                          # See CLAUDE.md → Logging Conventions
│   ├── exps/                      # Experiment logs, one dir per run timestamp
│   │   └── 260501-22:00:04-exps/
│   │       ├── run.log            # Pipeline execution log
│   │       └── llm-histories.log  # Full LLM request/response history
│   └── updates/                   # Codebase update logs (append-only summary + details)
│       ├── updates_summary.md     # Append-only summary, one block per update
│       └── details/
│           └── 260501-22:00:04-updates.md
├── data/                          # One subdirectory per data source
│   ├── data_1_dir/
│   └── data_2_dir/
├── tests/                         # Test suite, mirrors the vejudge/ package layout
│   ├── unit/                      # Per-module tests; lm_engine calls mocked
│   ├── integration/              # Small end-to-end pipeline runs on fixtures
│   └── fixtures/                  # Tiny sample media + golden expected outputs
└── vejudge/                       # Main package
    ├── logging/                   # Structured logging utilities
    ├── database/                  # Data loaders for video datasets
    │   ├── dl_template/           # Abstract base — all loaders inherit from this
    │   ├── dl_database1/          # One dir per dataset
    │   ├── dl_database2/
    │   ├── dl_dataloader1/        # Unified DataLoader wrapping all sources
    │   └── dl_others1/
    ├── lm_engine/                 # Multimodal LLM access layer
    │   ├── lm_template/           # Abstract base — all engines inherit from this
    │   ├── lm_gemini/
    │   ├── lm_gpt/
    │   └── lm_qwen/
    ├── preprocessing/             # Media preprocessing and sampling
    │   ├── pp_template/           # Abstract base for all preprocessors
    │   ├── sampling/
    │   │   ├── unified_sampling/
    │   │   └── stratified_sampling/
    │   ├── clustering/
    │   ├── preprocessing/         # Frame extraction, audio, captions, OCR, ASR
    │   └── eval/                  # Metrics for preprocessing quality
    ├── core/                      # Core judging framework (implemented as `vejudge/core/`,
    │   │                          #   renamed from the nested `vejudge/vejudge/` to avoid
    │   │                          #   the awkward `vejudge.vejudge.*` import path)
    │   ├── rubric/                # Rubric definitions and scoring schemas
    │   ├── prompts/               # Versioned prompt templates
    │   ├── judge/                 # Judge runner — calls lm_engine, validates output
    │   ├── calibration/           # Calibration models
    │   ├── ensemble/              # Multi-judge and prompt-variant ensemble
    │   └── eval/                  # Metrics against human labels
    ├── workflow/                  # End-to-end pipeline assembly
    ├── postprocessing/            # Score alignment, aggregation, output formatting
    │   └── eval/
    ├── benchmark/                 # Benchmark runners for specific datasets/tasks
    └── interface/                 # ComfyUI-style node interface
        ├── node_db/
        ├── node_preprocessing/
        ├── node_vejudge/
        ├── node_postprocessing/
        └── node_eval/
```

---

## Systems Design

| Component | Stores |
|---|---|
| Object storage | Source videos, output videos, clips, frames, audio |
| Relational DB | Item metadata, labels, prompt versions, judge runs |
| Vector DB | Embeddings for instructions, captions, frames, rationales |
| Feature cache | Captions, OCR, ASR, shot boundaries, quality metrics |
| Calibration registry | Calibration model version, training set, metrics |
| Audit log | Who/what produced each score and when |

---

## Testing

Tests live in `tests/` and mirror the `vejudge/` package layout so each module's tests sit at the matching path.

- **Unit tests** (`tests/unit/`) — one suite per module family. Every abstract template has a contract test that all subclasses must pass (loaders, LM engines, preprocessors), so swappable components stay interchangeable.
- **LM engines are mocked** in unit tests — no real API calls. Use recorded responses (a fixture replay of `llm-histories.log`-style payloads) to keep tests deterministic and free.
- **Integration tests** (`tests/integration/`) — run a small end-to-end pipeline (db loader → preprocessing → judge → calibration) on fixtures, asserting the unified JSON schema, score ranges (1–5), and required fields hold throughout.
- **Fixtures** (`tests/fixtures/`) — tiny sample videos/frames plus golden expected outputs. Keep them small enough to commit; never depend on external datasets or network access.
- **Validation logic** (JSON validity, score ranges, required fields, non-empty rationale) is covered by dedicated tests, since the judge flags rather than silently defaults invalid output.
- Run with `pytest`. Unit tests must pass with no credentials or GPU; integration tests may be marked and skipped when media tooling is unavailable.

---

## Benchmarking

The `benchmark/` package holds runners that measure the core research question: **the agreement gap between human annotators and LLM/VLM judges.**

- A **benchmark** is a fixed, versioned combination of: a dataset split, a judge configuration (model + prompt version + input strategy), and a calibration version. Pinning all three makes results reproducible and comparable across runs.
- Each runner loads human-labeled items, produces judge scores, and reports human-vs-judge agreement using the metrics in `research.md` (Spearman/Kendall, MAE, QWK, pairwise accuracy, calibration error) — **always with a per-category breakdown**.
- Benchmark outputs are written through the **Experiments logging** convention (`logs/exps/<timestamp>-exps/`, see `CLAUDE.md`). The benchmark id is the run timestamp.
- Compare conditions by varying one axis at a time (e.g., input strategy A–E from `research.md`, or raw vs. calibrated scores) and reading the per-run metrics across timestamped directories.
- New benchmarks subclass a benchmark-runner template so dataset-specific runners stay swappable, consistent with the rest of the package.
