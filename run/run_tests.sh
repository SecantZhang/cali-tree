#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — fast, free correctness check
# =============================================================================
# Runs the unit + integration test suite. Uses mocked engines, so it needs
# NO credentials and makes NO gateway calls. Run this after setup, and any
# time you change the code.
#
#   ./run/run_tests.sh                 # whole suite
#   ./run/run_tests.sh tests/unit -q   # pass-through args to pytest
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

# Quiet the harmless LibreSSL/urllib3 warning for clean output.
export PYTHONWARNINGS="ignore"

# Default to the full suite; allow overriding the target via "$@".
if [ "$#" -eq 0 ]; then
  python -m pytest tests/ -q
else
  python -m pytest "$@"
fi
