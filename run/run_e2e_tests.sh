#!/usr/bin/env bash
# =============================================================================
# run_e2e_tests.sh — real-browser end-to-end test of the interface
# =============================================================================
# Builds the web/ frontend, then runs the Playwright suite (web/e2e/specs/) against
# a real Chromium browser, a real FastAPI backend, and a real preview server — the
# only layer that catches real-CSS/real-CORS/real-click bugs the pytest and vitest
# suites structurally cannot (jsdom never enforces CORS or computes real layout).
#
# Cost & safety: every judge-node HTTP call in this suite goes to a local mock
# gateway (tests/e2e/mock_gateway.py), started + torn down automatically by
# web/e2e/global-setup.ts / global-teardown.ts — this script makes NO real
# (billable) gateway calls and needs no credentials.
#
#   ./run/run_e2e_tests.sh                        # whole suite
#   ./run/run_e2e_tests.sh shell-and-theme.spec.ts # pass-through args to `playwright test`
#
# One-time setup (real Chromium download, ~170MB): `cd web && npx playwright install chromium`
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONWARNINGS="ignore"

cd web

# Vite bakes VITE_API_BASE_URL into the build at build time — global-setup.ts reads
# this same value to know which port to launch the real backend on, so the build and
# the test run must agree on it (see web/e2e/global-setup.ts).
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8611}"

npm run build
npx playwright test "$@"
