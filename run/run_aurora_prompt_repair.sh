#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  git_common="$(git -C "$repo_root" rev-parse --git-common-dir)"
  if [[ "$git_common" != /* ]]; then
    git_common="$repo_root/$git_common"
  fi
  shared_python="$(cd "$git_common/.." && pwd)/.venv/bin/python"
  if [[ -x "$shared_python" ]]; then
    python_bin="$shared_python"
  else
    python_bin="${PYTHON311:-/opt/homebrew/bin/python3.11}"
  fi
fi

cd "$repo_root"
exec "$python_bin" -m run.aurora_prompt_repair "$@"
