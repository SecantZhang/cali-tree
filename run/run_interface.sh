#!/usr/bin/env bash
# =============================================================================
# run_interface.sh — launch the FastAPI backend for the node-graph interface
# =============================================================================
# Starts the local-only API server that the web/ React app talks to. No auth,
# binds to 127.0.0.1 by default. The Judge Node still enforces the same
# dry-run/--live gating as the CLI (see interface.md) — this script itself
# makes no gateway calls.
#
#   ./run/run_interface.sh                  # http://127.0.0.1:8000
#   ./run/run_interface.sh --port 9000
#   ./run/run_interface.sh --reload         # autoreload on source changes (dev)
#
# Requires the `interface` extra: pip install -e ".[interface]" (see setup_env.sh).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

VEJUDGE_REPO_ROOT=/Users/zzhang/Documents/research python -m vejudge.interface.server "$@"
