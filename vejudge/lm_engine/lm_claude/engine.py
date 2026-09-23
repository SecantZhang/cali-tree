"""Claude engine (text judges) via the Pluto OpenAI-compatible gateway.

Set ``VEJUDGE_CLAUDE_MODEL`` to override the default; confirm the gateway exposes the
model before use.
"""

from __future__ import annotations

import os

from ..lm_template import LMEngine


class ClaudeEngine(LMEngine):
    name = "claude"
    default_model = os.environ.get("VEJUDGE_CLAUDE_MODEL", "claude-sonnet-4.5")
    supports_video = False
