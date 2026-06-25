#!/usr/bin/env bash
# =============================================================================
# check_endpoints.sh — report which gateway endpoint(s) are up
# =============================================================================
# Probes the primary + mirror Pluto endpoints with one tiny request each and
# prints their status / latency. Use it when you suspect an endpoint is down
# (the benchmark auto-reorders to a working endpoint, but this shows you why).
#
# Makes REAL (but ~1-token, ~free) calls -> passes --live.
#
#   ./run/check_endpoints.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

python -m vejudge.lm_engine.health --live "$@"
