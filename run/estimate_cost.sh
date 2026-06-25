#!/usr/bin/env bash
# =============================================================================
# estimate_cost.sh — dry run: see scope & cost WITHOUT spending anything
# =============================================================================
# Resolves which items will be evaluated and prints the estimated number of
# video vs text judge calls. Makes NO gateway calls and needs NO --live.
# Always run this before a real benchmark to know what you're about to spend.
#
#   ./run/estimate_cost.sh                          # all peanut items
#   ./run/estimate_cost.sh --projects prj-paris-2025
#   ./run/estimate_cost.sh --judges M3,M5,M6
#
# Writes dry_run.json into a fresh logs/exps/<timestamp>-exps/ directory.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

# --dry-run is the key flag; everything after is passed straight through.
python -m vejudge.benchmark.cli --dry-run --models peanut "$@"
