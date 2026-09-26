"""Loader for the peanut video-editing eval dataset.

Joins (project, prompt_idx, model) -> rendered video + curated text inputs, producing
JudgeSamples. v1 targets the ``peanut`` model (clean prompt_N naming + notes JSON).
"""

from .loader import PeanutEvalLoader
from .video_resolver import RenderedOutput, resolve_peanut_outputs

__all__ = ["PeanutEvalLoader", "RenderedOutput", "resolve_peanut_outputs"]
