"""Kimi engine (text judges) via the Pluto OpenAI-compatible gateway.

Set ``VEJUDGE_KIMI_MODEL`` to override the default; confirm the gateway exposes the
model before use.
"""

from __future__ import annotations

import os

from ..lm_template import LMEngine


class KimiEngine(LMEngine):
    name = "kimi"
    default_model = os.environ.get("VEJUDGE_KIMI_MODEL", "kimi-k2.5")
    supports_video = False
