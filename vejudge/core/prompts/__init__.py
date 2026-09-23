"""Versioned prompt templates for the 6 judges.

Each metric module exposes ``VERSION`` and ``build(sample) -> PromptSpec``. The
registry records which prompt version each run used.
"""

from .registry import PROMPT_BUILDERS, build_prompt, prompt_versions
from .spec import PromptSpec

__all__ = ["PROMPT_BUILDERS", "PromptSpec", "build_prompt", "prompt_versions"]
