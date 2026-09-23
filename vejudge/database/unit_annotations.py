"""Strict JSONL loader for optional timestamp/unit-level human supervision."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.area.rubrics import AREA_RUBRICS

REQUIRED_FIELDS = {"item_id", "unit_id", "rubric_id", "rating"}


def load_unit_annotations(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Unit annotation file not found: {source}")
    records: list[dict[str, Any]] = []
    with open(source, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on unit annotation line {line_number}: {error}"
                ) from error
            missing = REQUIRED_FIELDS - set(record)
            if missing:
                raise ValueError(
                    f"Unit annotation line {line_number} missing: {sorted(missing)}"
                )
            if record["rubric_id"] not in AREA_RUBRICS:
                raise ValueError(
                    f"Unit annotation line {line_number} has unknown rubric_id "
                    f"'{record['rubric_id']}'"
                )
            rating = record["rating"]
            if (
                not isinstance(rating, (int, float))
                or isinstance(rating, bool)
                or not 1 <= float(rating) <= 5
            ):
                raise ValueError(
                    f"Unit annotation line {line_number} rating must be in [1, 5]"
                )
            normalized = {
                "item_id": str(record["item_id"]),
                "unit_id": str(record["unit_id"]),
                "rubric_id": str(record["rubric_id"]),
                "rating": float(rating),
                "severity": record.get("severity"),
                "comment": record.get("comment"),
                "annotator_id": record.get("annotator_id"),
                "timestamp": record.get("timestamp"),
            }
            records.append(normalized)
    return records
