#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
venv_path="$repo_root/.venv-gepa"
python_bin="${PYTHON311:-/opt/homebrew/bin/python3.11}"

if [[ ! -x "$python_bin" ]]; then
  echo "Python 3.11 was not found at $python_bin; set PYTHON311 to its path." >&2
  exit 1
fi

"$python_bin" -m venv "$venv_path"
"$venv_path/bin/python" -m pip install --upgrade pip
"$venv_path/bin/python" -m pip install "gepa==0.1.4" "requests>=2.31"
echo "GEPA environment ready at $venv_path"

