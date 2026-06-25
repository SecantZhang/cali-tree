#!/usr/bin/env bash
# =============================================================================
# run_base_benchmark_robust.sh — robustness grid (temperature x repeats)
# =============================================================================
# Runs the full base benchmark across a GRID of sampling temperatures (rows) and
# repeated runs (columns) to measure judge stability:
#   - does the judge return the same scores on repeat runs? (self-consistency)
#   - are the human-vs-judge correlation swings real or just small-n noise? (bootstrap CI)
#
# Each grid cell is one full ~10-min base run. The DEFAULT grid is
#   temperatures {0.0, 0.3, 0.7, 1.0} x 5 repeats = 20 cells
# i.e. ~3.5 HOURS and ~2040 gateway calls (~1360 video). This is expensive.
#
#   1) ALWAYS dry-run first (free, no calls):
#        ./run/run_base_benchmark_robust.sh --dry-run
#   2) Then launch the real grid IN THE BACKGROUND (it runs for hours):
#        nohup ./run/run_base_benchmark_robust.sh > robust.out 2>&1 &
#
# Override the grid / scope via pass-through flags, e.g.:
#   ./run/run_base_benchmark_robust.sh --temperatures 0.0,1.0 --repeats 3
#   ./run/run_base_benchmark_robust.sh --judges M3,M5,M6 --limit 5
#   ./run/run_base_benchmark_robust.sh --skip-video        # text judges only (cheap)
#
# RESUME an interrupted grid (e.g. after the endpoint dropped): --continue reuses the
# completed cells (and a half-finished cell's checkpointed judge calls) and runs only the
# rest. The grid is read from the run's robust_config.json, so the default grid flags above
# are ignored on resume.
#   ./run/run_base_benchmark_robust.sh --continue                       # most recent *-robust
#   ./run/run_base_benchmark_robust.sh --continue logs/exps/<ts>-robust # a specific run
#   ./run/run_base_benchmark_robust.sh --continue --dry-run             # show pending cells
#
# Outputs: a combined logs/exps/<ts>-robust/ dir with robust_grid.csv,
# robust_summary.csv, robust_report.md, cells.json — with each of the 20 cells
# nested inside as <ts>-robust/temp<T>_rep<N>-exps/ (its own per-cell artifacts).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# Defaults: full 4x5 grid, text conc 8 / video conc 4, real calls (--live).
# A user-supplied flag in "$@" overrides the matching default (later value wins).
python -m vejudge.benchmark.robust \
  --temperatures 0.0,0.3,0.7,1.0 \
  --repeats 5 \
  --concurrency 8 \
  --video-concurrency 4 \
  --live \
  "$@"
