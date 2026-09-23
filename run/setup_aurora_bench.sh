#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${VEJUDGE_PYTHON:-$repo_dir/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin=python3
fi
cd "$repo_dir"
exec "$python_bin" -m run.setup_aurora_bench "$@"
