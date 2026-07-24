"""``Preprocessor`` — abstract base for media preprocessing/sampling (stub).

Artifacts should be cached by ``(item_id, preprocessing_config_hash)`` once implemented.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Preprocessor(ABC):
    @abstractmethod
    def run(self, sample: dict[str, Any]) -> Any:
        """Produce a JSON-safe preprocessing artifact for a sample."""
