#!/usr/bin/env bash
set -euo pipefail
# Installation is explicit. Training never installs packages or creates a venv.
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="${CALITREE_GEPA_PYTHON:-python3.11}"
"$python_bin" -m venv "$repo_root/.venv-gepa"
"$repo_root/.venv-gepa/bin/python" -m pip install 'gepa==0.1.4'
