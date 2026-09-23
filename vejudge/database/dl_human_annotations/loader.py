"""Parse the human annotation JSON files into flat records.

Each file is one annotator's rating of one (project, prompt_idx, model, output_slot).
Scores in the ``annotation`` block are strings "1".."5" or "" (not rated).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from ... import config


@dataclass
class HumanAnnotationRecord:
    path: str
    annotator: str
    project: str
    model: str
    prompt_idx: int
    cell_key: str
    output_slot: Optional[int]
    complete: bool
    annotation: dict[str, Any] = field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return f"{self.project}::{self.prompt_idx}::{self.model}"


def _coerce_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_human_annotations(
    *,
    root: Optional[Path] = None,
    models: Optional[Iterable[str]] = None,
    projects: Optional[Iterable[str]] = None,
) -> list[HumanAnnotationRecord]:
    """Load all ``*_humaneval.json`` files, optionally filtered by model/project."""
    base = Path(root) if root else config.HUMAN_ANNOTATIONS_ROOT
    model_set = set(models) if models else None
    project_set = set(projects) if projects else None

    records: list[HumanAnnotationRecord] = []
    for fp in sorted(base.rglob("*_humaneval.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ann = data.get("annotation") or {}
        model = data.get("model", "")
        project = data.get("project", "")
        if model_set and model not in model_set:
            continue
        if project_set and project not in project_set:
            continue
        records.append(
            HumanAnnotationRecord(
                path=str(fp),
                annotator=data.get("annotator", ""),
                project=project,
                model=model,
                prompt_idx=_coerce_int(data.get("prompt_idx")) or 0,
                cell_key=data.get("cell_key", ""),
                output_slot=_coerce_int(data.get("output_slot")),
                complete=bool(ann.get("_complete", False)),
                annotation=ann,
            )
        )
    return records
