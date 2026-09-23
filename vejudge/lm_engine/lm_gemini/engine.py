"""Gemini engine (video-capable) — the default judge engine.

Routes through the Pluto OpenAI-compatible gateway; video is sent as a base64
``data:video/mp4`` part by the shared transport.
"""

from __future__ import annotations

from ... import config
from ..lm_template import LMEngine


class GeminiEngine(LMEngine):
    name = "gemini"
    default_model = config.DEFAULT_VIDEO_MODEL  # gemini-2.5-pro
    supports_video = True
