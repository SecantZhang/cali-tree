"""Local adapter for EditInspector's independently human-annotated edits.

Setup owns all network I/O. Graph execution reads only the materialized CSV-derived
metadata and image files, so dry runs and tests cannot download assets implicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ..dl_template.base import DataLoader
from ... import config

EDITINSPECTOR_REVISION = "e18cd6b6b80311d8514787618c2a6cbebff563ef"


def accuracy_level_label(level: int) -> str:
    """Map the benchmark's published accuracy scale to VEJudge's three classes.

    EditInspector defines 0=inaccurate, 1=inaccurate but reflects the instruction,
    2=accurate but unexpected, and 3=accurate. The mapping is therefore semantic and
    predeclared rather than fitted against judge predictions.
    """
    try:
        return {0: "no", 1: "partial", 2: "yes", 3: "yes"}[int(level)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"EditInspector accuracy level must be 0..3, got {level!r}") from exc


class EditInspectorLoader(DataLoader):
    """Build JudgeSample-compatible external image pairs and three-rater labels."""

    def __init__(self, *, root: Optional[Path] = None) -> None:
        self.root = Path(root or config.EDITINSPECTOR_ROOT)
        self._rows: Optional[dict[str, dict[str, Any]]] = None

    def _load(self) -> None:
        if self._rows is not None:
            return
        metadata_path = self.root / "metadata.jsonl"
        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"EditInspector metadata not found at {metadata_path}; "
                "run ./run/setup_editinspector.sh"
            )
        rows: dict[str, dict[str, Any]] = {}
        for line_number, line in enumerate(
            metadata_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            item_id = str(row.get("item_id") or "")
            if not item_id:
                raise ValueError(
                    f"EditInspector metadata line {line_number} has no item_id"
                )
            if item_id in rows:
                raise ValueError(f"Duplicate EditInspector item_id {item_id!r}")
            accuracy_level_label(int(row["accuracy_level"]))
            levels = row.get("rater_accuracy_levels")
            if (
                not isinstance(levels, list)
                or len(levels) != 3
                or any(int(level) not in {0, 1, 2, 3} for level in levels)
            ):
                raise ValueError(
                    f"EditInspector {item_id} must contain three rater levels in 0..3"
                )
            rows[item_id] = row
        if not rows:
            raise ValueError(f"EditInspector metadata is empty at {metadata_path}")
        self._rows = rows

    def list_items(self) -> list[str]:
        self._load()
        assert self._rows is not None
        missing: list[str] = []
        for item_id, row in self._rows.items():
            for field in ("source_path", "edited_path"):
                path = self.root / str(row[field])
                if not path.is_file() or not path.stat().st_size:
                    missing.append(str(path.relative_to(self.root)))
        if missing:
            preview = ", ".join(missing[:5])
            suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise FileNotFoundError(
                f"EditInspector setup is incomplete: {preview}{suffix}; "
                "rerun ./run/setup_editinspector.sh to resume"
            )
        return sorted(self._rows)

    def load_sample(self, item_id: str) -> dict[str, Any]:
        self._load()
        assert self._rows is not None
        if item_id not in self._rows:
            raise KeyError(item_id)
        row = self._rows[item_id]
        source_path = self.root / str(row["source_path"])
        edited_path = self.root / str(row["edited_path"])
        if not source_path.is_file() or not edited_path.is_file():
            raise FileNotFoundError(
                f"Missing EditInspector image for {item_id}; "
                "run ./run/setup_editinspector.sh"
            )
        return {
            "item_id": item_id,
            "project": "editinspector",
            "prompt_idx": int(row["source_index"]),
            "task_uid": str(row["benchmark_id"]),
            "model": "EditInspector-MagicBrush",
            "editor": "EditInspector-MagicBrush",
            "algorithm": "EditInspector-MagicBrush",
            "use_case": "text-guided-image-editing",
            "split": "test",
            "external_partition": str(
                row.get("evaluation_partition") or "development"
            ),
            "source_dataset": "EditInspector",
            "action": str(row.get("action") or "unknown"),
            "input": {
                "user_prompt": str(row["instruction"]),
                "instruction": str(row["instruction"]),
                "source_image_path": str(source_path),
            },
            "output": {"edited_image_path": str(edited_path)},
        }

    def load_label(self, item_id: str) -> dict[str, Any]:
        self._load()
        assert self._rows is not None
        if item_id not in self._rows:
            raise KeyError(item_id)
        row = self._rows[item_id]
        levels = [int(level) for level in row["rater_accuracy_levels"]]
        annotators = list(row.get("annotators") or [None, None, None])
        return {
            "item_id": item_id,
            "task_uid": str(row["benchmark_id"]),
            "editor": "EditInspector-MagicBrush",
            "split": "test",
            "source_dataset": "EditInspector",
            "accuracy_level": int(row["accuracy_level"]),
            "target_label": accuracy_level_label(int(row["accuracy_level"])),
            "ratings": [
                {
                    "sc": {0: 0.0, 1: 0.5, 2: 1.0, 3: 1.0}[level],
                    "accuracy_level": level,
                    "annotator": annotators[index] if index < len(annotators) else None,
                }
                for index, level in enumerate(levels)
            ],
            "n_annotators": len(levels),
        }

    def load_all(self) -> tuple[dict[str, Any], dict[str, Any]]:
        items = self.list_items()
        return (
            {item_id: self.load_sample(item_id) for item_id in items},
            {item_id: self.load_label(item_id) for item_id in items},
        )
