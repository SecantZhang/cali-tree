#!/usr/bin/env bash
# =============================================================================
# run_text_only.sh — cheap gap run using ONLY the text judges (no video upload)
# =============================================================================
# Runs the text judges (M1 assembly failure, M3 prompt completeness) over all
# peanut items. M3 aligns to the human "video_addresses_prompt" dimension, so
# you get real gap numbers without uploading any (large) video files.
#
# Makes REAL text calls -> passes --live. Cheap and fast; good for iterating.
#
#   ./run/run_text_only.sh
#   ./run/run_text_only.sh --projects prj-paris-2025
#
# Results: logs/exps/<timestamp>-exps/ (gap_result.json, aligned_pairs.csv, report).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# --skip-video drops M2/M4/M5/M6; --judges M1,M3 keeps only the text judges.
python -m vejudge.benchmark.cli \
  --models peanut \
  --judges M1,M3 \
  --skip-video \
  --live \
  "$@"
