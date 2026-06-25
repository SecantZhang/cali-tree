"""Multimodal LLM access layer.

All engines expose ``generate(prompt, media_inputs, schema) -> dict`` and subclass
``lm_template.LMEngine``. Use :func:`get_engine` to construct one by family name.
"""

from __future__ import annotations

from typing import Any, Optional

from .creds import PlutoCreds, load_creds
from .gate import LiveCallNotAllowed, live_allowed, require_live
from .lm_gemini import GeminiEngine
from .lm_gpt import GptEngine
from .lm_qwen import QwenEngine
from .lm_template import LMEngine, MediaInput

_ENGINES: dict[str, type[LMEngine]] = {
    "gemini": GeminiEngine,
    "gpt": GptEngine,
    "qwen": QwenEngine,
}


def get_engine(kind: str, **kwargs: Any) -> LMEngine:
    """Construct an engine by family name (``gemini`` | ``gpt`` | ``qwen``)."""
    key = kind.lower()
    if key not in _ENGINES:
        raise ValueError(f"Unknown engine '{kind}'. Options: {sorted(_ENGINES)}")
    return _ENGINES[key](**kwargs)


def available_engines() -> list[str]:
    return sorted(_ENGINES)


__all__ = [
    "LMEngine",
    "MediaInput",
    "GeminiEngine",
    "GptEngine",
    "QwenEngine",
    "PlutoCreds",
    "load_creds",
    "get_engine",
    "available_engines",
    "live_allowed",
    "require_live",
    "LiveCallNotAllowed",
]
