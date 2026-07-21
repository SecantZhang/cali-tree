"""Shared PromptSpec type (separate module to avoid registry<->builder import cycle)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PromptSpec:
    """One assembled prompt for a judge call.

    ``system`` is None for video judges (everything goes in ``user``). ``schema`` is
    an advisory hint of the expected JSON keys (used by the engine's optional parse).
    """

    system: Optional[str]
    user: str
    schema: dict[str, Any] = field(default_factory=dict)
    optional_fields: set[str] = field(default_factory=set)
    version: str = "v1"
