"""Llama engine (text judges) via the Pluto OpenAI-compatible gateway.

Set ``VEJUDGE_LLAMA_MODEL`` to override the default; confirm the gateway exposes the
model before use.
"""

from __future__ import annotations

import os

from ..lm_template import LMEngine


class LlamaEngine(LMEngine):
    name = "llama"
    default_model = os.environ.get("VEJUDGE_LLAMA_MODEL", "llama-3-3-70b")
    supports_video = False
