"""Prompt registry: maps metric id -> versioned builder, records versions."""

from __future__ import annotations

from typing import Any, Callable

from . import (
    m1_assembly_failure,
    m2_render_failure,
    m3_prompt_completeness,
    m4_visual_alignment,
    m5_edit_coherence,
    m6_av_sync,
)
from .spec import PromptSpec

_MODULES = {
    "M1": m1_assembly_failure,
    "M2": m2_render_failure,
    "M3": m3_prompt_completeness,
    "M4": m4_visual_alignment,
    "M5": m5_edit_coherence,
    "M6": m6_av_sync,
}

PROMPT_BUILDERS: dict[str, Callable[[dict[str, Any]], PromptSpec]] = {
    mid: mod.build for mid, mod in _MODULES.items()
}


def build_prompt(metric_id: str, sample: dict[str, Any]) -> PromptSpec:
    return PROMPT_BUILDERS[metric_id](sample)


def prompt_versions() -> dict[str, str]:
    """metric id -> prompt VERSION, for recording in run config."""
    return {mid: mod.VERSION for mid, mod in _MODULES.items()}
