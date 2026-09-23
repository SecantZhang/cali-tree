"""Multimodal LLM access layer.

All engines expose ``generate(prompt, media_inputs, schema) -> dict`` and subclass
``lm_template.LMEngine``. Use :func:`get_engine` to construct one by family name.
"""

from __future__ import annotations

from typing import Any, Optional

from .creds import PlutoCreds, load_creds
from .gate import LiveCallNotAllowed, live_allowed, require_live
from .lm_claude import ClaudeEngine
from .lm_deepseek import DeepseekEngine
from .lm_gemini import GeminiEngine
from .lm_gpt import GptEngine
from .lm_kimi import KimiEngine
from .lm_llama import LlamaEngine
from .lm_qwen import QwenEngine
from .lm_template import LMEngine, MediaInput

_ENGINES: dict[str, type[LMEngine]] = {
    "gemini": GeminiEngine,
    "gpt": GptEngine,
    "qwen": QwenEngine,
    "claude": ClaudeEngine,
    "deepseek": DeepseekEngine,
    "llama": LlamaEngine,
    "kimi": KimiEngine,
}


def get_engine(kind: str, **kwargs: Any) -> LMEngine:
    """Construct an engine by family name (see :func:`available_engines` for the full list)."""
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
    "ClaudeEngine",
    "DeepseekEngine",
    "LlamaEngine",
    "KimiEngine",
    "PlutoCreds",
    "load_creds",
    "get_engine",
    "available_engines",
    "live_allowed",
    "require_live",
    "LiveCallNotAllowed",
]
