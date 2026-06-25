#!/usr/bin/env bash
# =============================================================================
# setup_env.sh — one-time environment setup
# =============================================================================
# Creates a local virtualenv and installs VEJudge (editable) + dev deps.
# Run this ONCE before any other script in this folder.
#
#   ./run/setup_env.sh
#
# Safe to re-run: it reuses an existing .venv and just re-installs.
# No gateway calls are made here.
# =============================================================================
set -euo pipefail

# Resolve the project dir (parent of this run/ folder) so the script works
# regardless of where it is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Create the venv if it does not exist yet.
if [ ! -d .venv ]; then
  echo "Creating virtualenv at $PROJECT_DIR/.venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Upgrading pip and installing vejudge (editable) + dev deps ..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"

echo "Done. Activate later with:  source .venv/bin/activate"
echo "Verify with:               ./run/run_tests.sh"
