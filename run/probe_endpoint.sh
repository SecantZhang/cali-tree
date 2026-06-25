#!/usr/bin/env bash
# =============================================================================
# probe_endpoint.sh — measure the gateway's concurrency / rate-limit ceiling
# =============================================================================
# Fires increasing batches of tiny concurrent TEXT calls and reports
# success/429/error counts + latency per level, plus any rate-limit headers.
# Use the result to choose a safe --concurrency for the benchmark.
#
# Makes REAL (but cheap, ~few-token) calls -> passes --live. Total cost: cents.
#
#   ./run/probe_endpoint.sh                       # levels 1,2,4,8,16
#   ./run/probe_endpoint.sh --levels 1,2,4,8,16,32
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

python -m vejudge.lm_engine.probe --live "$@"
