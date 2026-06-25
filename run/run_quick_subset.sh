#!/usr/bin/env bash
# =============================================================================
# run_quick_subset.sh — small end-to-end run incl. video judges
# =============================================================================
# Runs a few judges (M3 text + M5/M6 video) over a SMALL number of items so you
# can validate the full pipeline (incl. real video uploads to Gemini) without a
# big spend. Defaults to 2 items.
#
# Makes REAL text + video calls -> passes --live.
#
#   ./run/run_quick_subset.sh                          # 2 items, M3,M5,M6
#   ./run/run_quick_subset.sh --limit 1                # even smaller
#   ./run/run_quick_subset.sh --projects prj-paris-2025
#
# NOTE: video judges base64-upload each rendered MP4; some are large (tens of
# MB), so even a few items can be slow. Use estimate_cost.sh first.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# --limit caps the number of items (the cost guardrail). Override via "$@".
python -m vejudge.benchmark.cli \
  --models peanut \
  --judges M3,M5,M6 \
  --limit 2 \
  --live \
  "$@"
