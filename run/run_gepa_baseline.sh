#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${CRITICAL_PYTHON:-${project_root}/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="${CRITICAL_PYTHON:-python3}"
fi
cd "$project_root"
exec "$python_bin" -m run.run_gepa_baseline "$@"
