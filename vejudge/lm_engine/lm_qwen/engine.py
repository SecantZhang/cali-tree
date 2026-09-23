"""Qwen engine stub — present so the template family is complete and swappable.

Set ``VEJUDGE_QWEN_MODEL`` and confirm the gateway exposes the model before use.
"""

from __future__ import annotations

import os

from ..lm_template import LMEngine


class QwenEngine(LMEngine):
    name = "qwen"
    default_model = os.environ.get("VEJUDGE_QWEN_MODEL", "qwen2.5-vl")
    supports_video = True
