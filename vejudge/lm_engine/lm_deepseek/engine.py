"""Deepseek engine (text judges) via the Pluto OpenAI-compatible gateway.

Set ``VEJUDGE_DEEPSEEK_MODEL`` to override the default; confirm the gateway exposes the
model before use.
"""

from __future__ import annotations

import os

from ..lm_template import LMEngine


class DeepseekEngine(LMEngine):
    name = "deepseek"
    default_model = os.environ.get("VEJUDGE_DEEPSEEK_MODEL", "deepseek-r1")
    supports_video = False
