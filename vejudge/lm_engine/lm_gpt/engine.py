"""GPT engine (text judges) via the Pluto OpenAI-compatible gateway."""

from __future__ import annotations

from ... import config
from ..lm_template import LMEngine


class GptEngine(LMEngine):
    name = "gpt"
    default_model = config.DEFAULT_TEXT_MODEL  # gpt-4.1
    supports_video = False
