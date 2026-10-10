"""Gemini engine (video-capable) — the default judge engine.

Uses the official Gemini GenerateContent API with inline image/video parts.
"""

from __future__ import annotations

from ... import config
from ..lm_template import LMEngine


class GeminiEngine(LMEngine):
    name = "gemini"
    default_model = config.DEFAULT_VIDEO_MODEL  # gemini-2.5-pro
    supports_video = True
