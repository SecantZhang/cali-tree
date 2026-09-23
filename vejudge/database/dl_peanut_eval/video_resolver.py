"""Resolve rendered-output paths for an eval model.

Models share the human-annotation format but render to different on-disk trees, so
discovery/resolution dispatches on ``config.MODEL_LAYOUT``:

    peanut   <RENDERED_ROOT>/peanut-.../<project>/
                 videos/<ts>_prompt_<idx>_final.mp4
                 notes/<ts>_prompt_<idx>_notes.json
                 otio/<ts>_prompt_<idx>_final.otio      (discover via notes files)
    coconut  <RENDERED_ROOT>/coconut/<project>/<NNN>/render.mp4 + timeline.otio + plan.md
                 prompt_idx = int(NNN) - 1              (ordinal run subdirs, 001-indexed)
    grapenut <RENDERED_ROOT>/grapenut/<project>/videos/<idx>_video.mp4
                 otio/<idx>_timeline.otio

The public API (``resolve_peanut_output`` / ``resolve_peanut_outputs``) is unchanged; only
the internals branch by layout. The peanut path is byte-for-byte the old behavior.
"""

from __future__ import annotations

import glob
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ... import config

logger = logging.getLogger(__name__)


@dataclass
class RenderedOutput:
    project: str
    model: str
    prompt_idx: int
    video_path: Optional[str]
    notes_path: Optional[str]
    otio_path: Optional[str]
    plan_path: Optional[str] = None


def _model_dir(model: str) -> str:
    return config.MODEL_DIR_ALIASES.get(model, model)


def _layout(model: str) -> str:
    return config.MODEL_LAYOUT.get(model, "peanut")


def _abs(p: Path) -> Optional[str]:
    return os.path.abspath(str(p)) if p.exists() else None


def _glob_one(directory: Path, pattern: str) -> Optional[str]:
    matches = sorted(glob.glob(str(directory / pattern)))
    return os.path.abspath(matches[0]) if matches else None


# --- peanut (unchanged behavior) ----------------------------------------------------------

def _resolve_peanut(project: str, prompt_idx: int, model: str) -> RenderedOutput:
    base = config.RENDERED_ROOT / _model_dir(model) / project
    return RenderedOutput(
        project=project, model=model, prompt_idx=prompt_idx,
        video_path=_glob_one(base / "videos", f"*prompt_{prompt_idx}_final.mp4"),
        notes_path=_glob_one(base / "notes", f"*prompt_{prompt_idx}_notes.json"),
        otio_path=_glob_one(base / "otio", f"*prompt_{prompt_idx}_final.otio"),
    )


_PROMPT_RE = re.compile(r"prompt_(\d+)_notes\.json$")


def _discover_peanut(project: str, model: str) -> list[RenderedOutput]:
    base = config.RENDERED_ROOT / _model_dir(model) / project
    notes_dir = base / "notes"
    if not notes_dir.is_dir():
        return []
    outs: list[RenderedOutput] = []
    for nf in sorted(notes_dir.glob("*prompt_*_notes.json")):
        m = _PROMPT_RE.search(nf.name)
        if m:
            outs.append(_resolve_peanut(project, int(m.group(1)), model))
    return outs


# --- coconut: ordinal run subdirs {NNN}/render.mp4, prompt_idx = NNN - 1 -------------------

def _resolve_coconut(project: str, prompt_idx: int, model: str) -> RenderedOutput:
    run = f"{prompt_idx + 1:03d}"
    base = config.RENDERED_ROOT / _model_dir(model) / project / run
    return RenderedOutput(
        project=project, model=model, prompt_idx=prompt_idx,
        video_path=_abs(base / "render.mp4"),
        notes_path=None,
        otio_path=_abs(base / "timeline.otio"),
        plan_path=_abs(base / "plan.md"),
    )


def _discover_coconut(project: str, model: str) -> list[RenderedOutput]:
    base = config.RENDERED_ROOT / _model_dir(model) / project
    if not base.is_dir():
        return []
    runs = sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and d.name.isdigit() and (d / "render.mp4").exists()
    )
    # Ordinal assumption: run NNN holds prompt (NNN-1). Warn loudly if the run numbers aren't
    # the contiguous 001..00N we expect — that's where a silent prompt↔video misalignment
    # would come from.
    expected = [f"{i + 1:03d}" for i in range(len(runs))]
    if runs != expected:
        logger.warning(
            "coconut layout: %s run subdirs %s are not contiguous 001..00N — "
            "prompt_idx↔video mapping may be unreliable", project, runs,
        )
    return [_resolve_coconut(project, int(r) - 1, model) for r in runs]


# --- grapenut: videos/{idx}_video.mp4 -----------------------------------------------------

def _resolve_grapenut(project: str, prompt_idx: int, model: str) -> RenderedOutput:
    base = config.RENDERED_ROOT / _model_dir(model) / project
    return RenderedOutput(
        project=project, model=model, prompt_idx=prompt_idx,
        video_path=_abs(base / "videos" / f"{prompt_idx}_video.mp4"),
        notes_path=None,
        otio_path=_abs(base / "otio" / f"{prompt_idx}_timeline.otio"),
    )


_GRAPE_RE = re.compile(r"^(\d+)_video\.mp4$")


def _discover_grapenut(project: str, model: str) -> list[RenderedOutput]:
    videos = config.RENDERED_ROOT / _model_dir(model) / project / "videos"
    if not videos.is_dir():
        return []
    outs: list[RenderedOutput] = []
    for vf in sorted(videos.glob("*_video.mp4")):
        m = _GRAPE_RE.match(vf.name)
        if m:
            outs.append(_resolve_grapenut(project, int(m.group(1)), model))
    return outs


_RESOLVE = {"peanut": _resolve_peanut, "coconut": _resolve_coconut, "grapenut": _resolve_grapenut}
_DISCOVER = {"peanut": _discover_peanut, "coconut": _discover_coconut, "grapenut": _discover_grapenut}


def resolve_peanut_output(project: str, prompt_idx: int, model: str = "peanut") -> RenderedOutput:
    return _RESOLVE[_layout(model)](project, prompt_idx, model)


def resolve_peanut_outputs(project: str, model: str = "peanut") -> list[RenderedOutput]:
    """Discover all (prompt_idx) rendered outputs available for a project."""
    return _DISCOVER[_layout(model)](project, model)
