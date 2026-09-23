#!/usr/bin/env python3
"""Materialize a deterministic subset of the public EditInspector benchmark.

The official CSV is pinned to a Git commit. Selection is independently shuffled within
the predeclared no/partial/yes classes, so a smaller ratio is a strict subset of a later
larger run. Existing images and partial downloads are reused.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable

from vejudge import config
from vejudge.database.dl_editinspector import (
    EDITINSPECTOR_REVISION,
    accuracy_level_label,
)
from run.setup_imagenhub import download, sha256

CSV_URL = (
    "https://raw.githubusercontent.com/editinspector/EditInspector/"
    f"{EDITINSPECTOR_REVISION}/benchmark/editinspector_benchmark.csv"
)


def _literal_list(value: str, *, field: str) -> list[Any]:
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list):
        raise ValueError(f"EditInspector {field} must be a list")
    return parsed


def parse_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "annotated_is_accurate_level",
            "metadata_annotated_is_accurate_level",
            "annotators",
            "instruction",
            "action",
            "id",
            "Image1",
            "Image2",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"EditInspector CSV is missing columns: {sorted(missing)}")
        for source_index, row in enumerate(reader):
            level = int(row["annotated_is_accurate_level"])
            target_label = accuracy_level_label(level)
            rater_levels = [
                int(value)
                for value in _literal_list(
                    row["metadata_annotated_is_accurate_level"],
                    field="metadata_annotated_is_accurate_level",
                )
            ]
            if len(rater_levels) != 3 or any(
                value not in {0, 1, 2, 3} for value in rater_levels
            ):
                raise ValueError(
                    f"EditInspector row {source_index} must contain three rater levels"
                )
            annotators = _literal_list(row["annotators"], field="annotators")
            benchmark_id = str(row["id"]).strip()
            if not benchmark_id:
                raise ValueError(f"EditInspector row {source_index} has no id")
            rows.append({
                "source_index": source_index,
                "item_id": f"editinspector::{source_index:04d}",
                "benchmark_id": benchmark_id,
                "instruction": str(row["instruction"]).strip(),
                "action": str(row.get("action") or "unknown").strip() or "unknown",
                "accuracy_level": level,
                "target_label": target_label,
                "rater_accuracy_levels": rater_levels,
                "annotators": annotators,
                "source_url": str(row["Image1"]).strip(),
                "edited_url": str(row["Image2"]).strip(),
                "source_path": f"images/source/{source_index:04d}.png",
                "edited_path": f"images/edited/{source_index:04d}.png",
            })
    if len(rows) != 783:
        raise ValueError(f"Expected 783 EditInspector rows, got {len(rows)}")
    return rows


def select_rows(
    rows: Iterable[dict[str, Any]], *, ratio: float, seed: int
) -> list[dict[str, Any]]:
    if not 0 < ratio <= 1:
        raise ValueError("ratio must be in (0, 1]")
    grouped: dict[str, list[dict[str, Any]]] = {
        "no": [], "partial": [], "yes": [],
    }
    for row in rows:
        grouped[str(row["target_label"])].append(row)
    selected: list[dict[str, Any]] = []
    for label_index, label in enumerate(("no", "partial", "yes")):
        group = sorted(grouped[label], key=lambda row: str(row["item_id"]))
        random.Random(seed + label_index * 1009).shuffle(group)
        count = len(group) if ratio == 1 else math.ceil(len(group) * ratio)
        selected.extend(group[:count])
    return sorted(selected, key=lambda row: int(row["source_index"]))


def assign_evaluation_partitions(
    all_rows: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    seed: int,
) -> None:
    """Mark frozen 10%, next-40%, and final-50% nested evaluation partitions."""
    development_ids = {
        row["item_id"]
        for row in select_rows(all_rows, ratio=0.1, seed=seed)
    }
    first_half_ids = {
        row["item_id"]
        for row in select_rows(all_rows, ratio=0.5, seed=seed)
    }
    for row in selected:
        row["evaluation_partition"] = (
            "development"
            if row["item_id"] in development_ids
            else (
                "confirmation"
                if row["item_id"] in first_half_ids
                else "final"
            )
        )


def build_manifest(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    ratio: float,
    seed: int,
) -> dict[str, Any]:
    paths = [root / "source" / "editinspector_benchmark.csv", root / "metadata.jsonl"]
    for row in rows:
        paths.extend([
            root / str(row["source_path"]),
            root / str(row["edited_path"]),
        ])
    label_counts = {
        label: sum(row["target_label"] == label for row in rows)
        for label in ("no", "partial", "yes")
    }
    partition_counts = {
        partition: sum(
            row.get("evaluation_partition") == partition
            for row in rows
        )
        for partition in ("development", "confirmation", "final")
    }
    return {
        "dataset": "editinspector/EditInspector",
        "revision": EDITINSPECTOR_REVISION,
        "selection_ratio": ratio,
        "selection_seed": seed,
        "items": len(rows),
        "label_mapping": {"0": "no", "1": "partial", "2": "yes", "3": "yes"},
        "label_counts": label_counts,
        "partition_counts": partition_counts,
        "files": {
            str(path.relative_to(root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(set(paths))
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=config.EDITINSPECTOR_ROOT)
    parser.add_argument(
        "--ratio", type=float, default=1.0,
        help="Deterministic class-stratified fraction to materialize",
    )
    parser.add_argument("--seed", type=int, default=44)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "source" / "editinspector_benchmark.csv"
    download(CSV_URL, csv_path)
    all_rows = parse_rows(csv_path)
    selected = select_rows(all_rows, ratio=args.ratio, seed=args.seed)
    assign_evaluation_partitions(all_rows, selected, seed=args.seed)
    for row in selected:
        download(str(row["source_url"]), root / str(row["source_path"]))
        download(str(row["edited_url"]), root / str(row["edited_path"]))
    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in selected
        ),
        encoding="utf-8",
    )
    manifest = build_manifest(root, selected, ratio=args.ratio, seed=args.seed)
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"EditInspector ready at {root}: {len(selected)} items, "
        f"labels={manifest['label_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
