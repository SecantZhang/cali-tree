"""Resolve rendered-output paths for the peanut model.

On-disk layout:
    <RENDERED_ROOT>/peanut-v4-multi-track-gpt-5-1-medium/<project>/
        videos/<ts>_prompt_<idx>_final.mp4
        notes/<ts>_prompt_<idx>_notes.json
        otio/<ts>_prompt_<idx>_final.otio

The timestamp prefix varies, so we glob by the ``prompt_<idx>`` suffix.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ... import config


@dataclass
class RenderedOutput:
    project: str
    model: str
    prompt_idx: int
    video_path: Optional[str]
    notes_path: Optional[str]
    otio_path: Optional[str]


def _model_dir(model: str) -> str:
    return config.MODEL_DIR_ALIASES.get(model, model)


def _glob_one(directory: Path, pattern: str) -> Optional[str]:
    matches = sorted(glob.glob(str(directory / pattern)))
    return os.path.abspath(matches[0]) if matches else None


def resolve_peanut_output(
    project: str, prompt_idx: int, model: str = "peanut"
) -> RenderedOutput:
    base = config.RENDERED_ROOT / _model_dir(model) / project
    video = _glob_one(base / "videos", f"*prompt_{prompt_idx}_final.mp4")
    notes = _glob_one(base / "notes", f"*prompt_{prompt_idx}_notes.json")
    otio = _glob_one(base / "otio", f"*prompt_{prompt_idx}_final.otio")
    return RenderedOutput(
        project=project,
        model=model,
        prompt_idx=prompt_idx,
        video_path=video,
        notes_path=notes,
        otio_path=otio,
    )


_PROMPT_RE = re.compile(r"prompt_(\d+)_notes\.json$")


def resolve_peanut_outputs(project: str, model: str = "peanut") -> list[RenderedOutput]:
    """Discover all (prompt_idx) outputs available for a project from its notes files."""
    base = config.RENDERED_ROOT / _model_dir(model) / project
    notes_dir = base / "notes"
    outputs: list[RenderedOutput] = []
    if not notes_dir.is_dir():
        return outputs
    for nf in sorted(notes_dir.glob("*prompt_*_notes.json")):
        m = _PROMPT_RE.search(nf.name)
        if not m:
            continue
        outputs.append(resolve_peanut_output(project, int(m.group(1)), model))
    return outputs
