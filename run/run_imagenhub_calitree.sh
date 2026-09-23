#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${VEJUDGE_PYTHON:-${project_root}/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="${VEJUDGE_PYTHON:-python3}"
fi
cd "$project_root"
exec "$python_bin" -m run.run_imagenhub_calitree "$@"
