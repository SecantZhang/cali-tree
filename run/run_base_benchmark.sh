#!/usr/bin/env bash
# =============================================================================
# run_base_benchmark.sh — THE base benchmark (full raw human-vs-judge gap)
# =============================================================================
# Runs ALL six judges (M1-M6) over ALL matched peanut items: text judges -> GPT,
# video judges -> Gemini (rendered MP4 uploaded per item). This is the headline
# baseline: the raw gap, no calibration.
#
# Makes MANY REAL calls -> passes --live. This is the slow/expensive path
# because of large video uploads. ALWAYS run estimate_cost.sh first.
#
#   ./run/estimate_cost.sh            # 1. see how many items/calls + cost
#   ./run/run_base_benchmark.sh       # 2. run the full baseline
#
# You can still narrow scope via pass-through flags, e.g.:
#   ./run/run_base_benchmark.sh --projects prj-paris-2025
#   ./run/run_base_benchmark.sh --limit 5
#
# RESUME an interrupted run: --continue reuses checkpointed judge calls and redoes only the
# missing ones (config read from the run's run_config.json).
#   ./run/run_base_benchmark.sh --continue                        # most recent benchmark run
#   ./run/run_base_benchmark.sh --continue logs/exps/<ts>-exps    # a specific run
#
# Results: logs/exps/<timestamp>-exps/
#   gap_result.json      per-dimension & per-category Spearman/Kendall/MAE/QWK
#   aligned_pairs.csv    raw (human, judge) pairs
#   gap_report.xlsx      metrics table  + chart_gap_by_dimension.png
#   run.log, llm-histories.log, run_config.json
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# No --limit and no --judges => all matched items, all six judges (the baseline).
# Text and video judges get independent pools:
#   --concurrency 8        : text judges (cheap, fast; gateway allows ~16)
#   --video-concurrency 4  : video judges (bandwidth/memory-bound -> keep modest)
# Override either by passing your own value after this script (the later value wins).
python -m vejudge.benchmark.cli \
  --models peanut \
  --concurrency 8 \
  --video-concurrency 4 \
  --live \
  "$@"
