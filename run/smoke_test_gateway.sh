#!/usr/bin/env bash
# =============================================================================
# smoke_test_gateway.sh — one tiny REAL call to validate the gateway
# =============================================================================
# Sends a single trivial text prompt to the Pluto gateway to confirm:
#   - credentials load from .env-raw (or env vars),
#   - the endpoint (and mirror failover) work,
#   - token usage + llm-histories logging work.
#
# This makes ONE real (billable) call, so it passes --live for you.
# Cost is a few cents. Run it once after setup, before any benchmark.
#
#   ./run/smoke_test_gateway.sh                       # default: gpt, "OK" prompt
#   ./run/smoke_test_gateway.sh --engine gemini       # test the video engine's text path
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# --live authorizes the real call (this script exists specifically to make it).
python -m vejudge.lm_engine --engine gpt --text "Reply with the single word OK." --live "$@"
