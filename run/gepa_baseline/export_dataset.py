#!/usr/bin/env python3
"""Export the ImagenHub dev-slice split for the isolated GEPA optimizer to consume.

Runs in the main (Python 3.9) venv, reusing the exact same graph-executed `imagenhub_source`
-> `dataset` split (seed 44, task-grouped, 232 train / 120 test) every other baseline this
session used, so the exported split is guaranteed identical rather than reimplemented. Writes
only file paths and labels -- no image bytes -- since the isolated GEPA venv reads the same
local ImagenHub files directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vejudge.interface.node_calibration.calitree_nodes import _calibration_split, _target
from vejudge.interface.server.executor import GraphExecutionEngine
from vejudge.interface.server.schemas import GraphIn, to_graph_spec
from vejudge.checkpoint import CheckpointStore
from vejudge.logging.exp_logger import make_exp_run

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / "workflows"
    / "examples"
    / "calitree_imagenhub.json"
)
OUTPUT = Path(__file__).resolve().parent / "dataset_export.json"


def main() -> int:
    payload = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph = GraphIn(**payload["graph"])
    run = make_exp_run(run_id="gepa-dataset-export")
    checkpoint = CheckpointStore(run.run_dir / "judge_results.jsonl")
    try:
        result = GraphExecutionEngine(
            to_graph_spec(graph), run=run, checkpoint=checkpoint,
            dry_run=True, allow_live=False,
        ).execute()
    finally:
        run.close()

    dataset_result = result.node_results.get("dataset")
    if dataset_result is None or dataset_result.status != "done":
        raise RuntimeError(f"dataset node did not complete: {dataset_result}")
    samples = dataset_result.outputs["samples"]
    labels = dataset_result.outputs["labels"]

    exported: dict[str, dict[str, Any]] = {}
    for item_id, sample in samples.items():
        label = labels.get(item_id)
        target = _target(label) if label is not None else ""
        if target not in {"no", "partial", "yes"}:
            continue
        exported[item_id] = {
            "item_id": item_id,
            "source_image_path": str(
                (sample.get("input") or {}).get("source_image_path") or ""
            ),
            "edited_image_path": str(
                (sample.get("output") or {}).get("edited_image_path") or ""
            ),
            "instruction": str((sample.get("input") or {}).get("instruction") or ""),
            "target_label": target,
            "split": str(sample.get("split") or ""),
        }

    # Same fit/validation split (seed 44, 0.25 fraction, task-grouped) used everywhere else
    # this session, so GEPA's trainset/valset partition is directly comparable to Global
    # TextGrad's -- not a separately invented split.
    train_ids = [i for i, row in exported.items() if row["split"] == "train"]
    fit_ids, validation_ids = _calibration_split(
        train_ids, labels, validation_fraction=0.25, seed=44
    )
    fit_set, validation_set = set(fit_ids), set(validation_ids)
    for item_id, row in exported.items():
        if item_id in fit_set:
            row["cal_split"] = "fit"
        elif item_id in validation_set:
            row["cal_split"] = "validation"
        else:
            row["cal_split"] = ""

    OUTPUT.write_text(json.dumps(exported, indent=2), encoding="utf-8")
    counts = {"train": 0, "test": 0}
    for row in exported.values():
        if row["split"] in counts:
            counts[row["split"]] += 1
    print(f"wrote {len(exported)} cases to {OUTPUT} ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
