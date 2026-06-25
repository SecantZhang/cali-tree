"""Central configuration: filesystem roots, model defaults, and env-var overrides.

Everything here can be overridden with an environment variable so the package never
hard-fails on a machine with a different layout. The defaults point at the research
repo layout this project ships against.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Filesystem roots ---------------------------------------------------------
# The research repo root is three levels up from this file:
#   <repo>/projects/vejudge/vejudge/config.py  ->  <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_path(var: str, default: Path) -> Path:
    val = os.environ.get(var, "").strip()
    return Path(val) if val else default


REPO_ROOT: Path = _env_path("VEJUDGE_REPO_ROOT", _REPO_ROOT)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]  # projects/vejudge/

DATA_ROOT: Path = _env_path("VEJUDGE_DATA_ROOT", REPO_ROOT / "data")
EVALUATION_ROOT: Path = _env_path("VEJUDGE_EVALUATION_ROOT", REPO_ROOT / "evaluation")
RENDERED_ROOT: Path = _env_path(
    "VEJUDGE_RENDERED_ROOT", EVALUATION_ROOT / "all models output"
)
HUMAN_ANNOTATIONS_ROOT: Path = _env_path(
    "VEJUDGE_HUMAN_ANNOTATIONS_ROOT", EVALUATION_ROOT / "human_annotations"
)
ENV_RAW_PATH: Path = _env_path("VEJUDGE_ENV_RAW", REPO_ROOT / ".env-raw")
LOGS_ROOT: Path = _env_path("VEJUDGE_LOGS_ROOT", PROJECT_ROOT / "logs")
USE_CASES_CONFIG: Path = _env_path(
    "VEJUDGE_USE_CASES_CONFIG", DATA_ROOT / "use_cases_config.json"
)

# --- Model defaults -----------------------------------------------------------
DEFAULT_VIDEO_MODEL: str = os.environ.get("VEJUDGE_VIDEO_MODEL", "gemini-2.5-pro")
DEFAULT_TEXT_MODEL: str = os.environ.get("VEJUDGE_TEXT_MODEL", "gpt-4.1")
# Default judge *engine* family. Gemini is video-capable and is the project default.
DEFAULT_JUDGE_ENGINE: str = os.environ.get("VEJUDGE_JUDGE_ENGINE", "gemini")

# --- Model-name -> on-disk rendered-output dir aliases ------------------------
# Human annotations record model="peanut" but the rendered videos live under the
# full pipeline dir name. v1 targets peanut only; others map to themselves.
MODEL_DIR_ALIASES: dict[str, str] = {
    "peanut": "peanut-v4-multi-track-gpt-5-1-medium",
    "coconut": "coconut",
    "grapenut": "grapenut",
    "loopedit": "loopedit",
}

# Soft warning threshold for base64 video uploads.
VIDEO_SIZE_WARN_MB: int = 50
