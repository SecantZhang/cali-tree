"""``DataLoader`` — abstract base producing judge-ready samples.

A loader knows how to enumerate items and build a ``JudgeSample`` (the dict shape the
judges consume) for each. Concrete loaders never bypass this interface so downstream
code (workflow, benchmark) is dataset-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

ItemId = str  # canonical id, e.g. "prj-paris-2025::0::peanut"


class DataLoader(ABC):
    @abstractmethod
    def list_items(self) -> list[ItemId]:
        """All item ids this loader can produce samples for."""

    @abstractmethod
    def load_sample(self, item_id: ItemId) -> dict[str, Any]:
        """Build a JudgeSample dict for one item.

        Shape:
            {
              "item_id", "project", "prompt_idx", "model", "use_case",
              "input": {user_prompt, a_roll_transcript_text, b_roll_captions_excerpt,
                        initial_timeline_text, notes_path, asset_filepaths, prompt_index, ...},
              "algorithm": <model>,
              "output": {output_video_path, assembly_json},
            }
        """
