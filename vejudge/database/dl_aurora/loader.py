"""Local, read-only adapter for the human-rated AURORA-Bench outputs.

The official release contains 400 source-image/instruction pairs, outputs from five
editing models, and one aggregate human score in ``[0, 2]`` for every output.  Setup
owns all network and archive work; this loader only validates and reads materialized
paths so graph runs remain deterministic and offline.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Iterable, Optional

from ... import config
from ..dl_template.base import DataLoader

AURORA_MODELS: tuple[str, ...] = (
    "finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999",
    "genhowto",
    "instruct-pix2pix-00-22000",
    "magic_reproduce_epoch=47-step=12999",
    "mgie",
)
AURORA_TASKS: tuple[str, ...] = (
    "ag",
    "clevr",
    "emu",
    "epic",
    "kubric",
    "magicbrush",
    "something",
    "whatsup",
)
SPLIT_SEEDS: tuple[int, ...] = (42, 43, 44)


def score_to_label(score: float) -> tuple[int, str]:
    """Discretize the released mean score using predeclared half-point cutoffs.

    AURORA's underlying human choices are 0=none, 1=partial, and 2=full.  The
    published JSON averages repeated judgments, so its targets are fractional.  The
    continuous ``human_score`` remains the primary calibration target; this mapping is
    supplied for VEJudge's existing three-class calibration nodes.
    """
    value = float(score)
    if not 0.0 <= value <= 2.0:
        raise ValueError(f"AURORA human score must be in [0, 2], got {score!r}")
    ordinal = 0 if value < 0.5 else (1 if value < 1.5 else 2)
    return ordinal, ("no", "partial", "yes")[ordinal]


def build_split_manifest(
    task_uids: Iterable[str], *, seed: int, train_tasks: int = 80
) -> dict[str, Any]:
    """Build a deterministic task-grouped 20/80 calibration/evaluation split."""
    uids = sorted(set(task_uids))
    if len(uids) < train_tasks:
        raise ValueError(f"Need at least {train_tasks} tasks, got {len(uids)}")
    shuffled = list(uids)
    random.Random(seed).shuffle(shuffled)
    train = sorted(shuffled[:train_tasks])
    test = sorted(shuffled[train_tasks:])
    return {
        "seed": seed,
        "task_digest": hashlib.sha256("\n".join(uids).encode()).hexdigest(),
        "train": train,
        "test": test,
    }


class AuroraBenchLoader(DataLoader):
    """Build judge-ready image pairs and aggregate 0--2 human targets."""

    def __init__(
        self,
        *,
        root: Optional[Path] = None,
        repeat: int = 1,
        models: Optional[Iterable[str]] = None,
        tasks: Optional[Iterable[str]] = None,
    ) -> None:
        self.root = Path(root or config.AURORA_BENCH_ROOT)
        if repeat not in (1, 2, 3):
            raise ValueError("repeat must be 1, 2, or 3")
        self.repeat = repeat
        self.seed = SPLIT_SEEDS[repeat - 1]
        self.models = tuple(models or AURORA_MODELS)
        self.tasks = tuple(tasks or AURORA_TASKS)
        unknown_models = set(self.models) - set(AURORA_MODELS)
        unknown_tasks = set(self.tasks) - set(AURORA_TASKS)
        if unknown_models:
            raise ValueError(f"Unknown AURORA models: {sorted(unknown_models)}")
        if unknown_tasks:
            raise ValueError(f"Unknown AURORA tasks: {sorted(unknown_tasks)}")
        self._rows: Optional[dict[str, dict[str, Any]]] = None

    def _load(self) -> None:
        if self._rows is not None:
            return
        metadata_path = self.root / "metadata.jsonl"
        split_path = self.root / "splits" / f"seed_{self.seed}.json"
        if not metadata_path.is_file() or not split_path.is_file():
            raise FileNotFoundError(
                f"AURORA-Bench metadata or split is missing under {self.root}; "
                "run ./run/setup_aurora_bench.sh"
            )
        split_manifest = json.loads(split_path.read_text(encoding="utf-8"))
        split = {uid: "train" for uid in split_manifest["train"]}
        split.update({uid: "test" for uid in split_manifest["test"]})
        rows: dict[str, dict[str, Any]] = {}
        for line_number, line in enumerate(
            metadata_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            item_id = str(row.get("item_id") or "")
            if not item_id:
                raise ValueError(f"AURORA metadata line {line_number} has no item_id")
            if item_id in rows:
                raise ValueError(f"Duplicate AURORA item_id {item_id!r}")
            if str(row.get("task_uid")) not in split:
                raise ValueError(f"AURORA item {item_id!r} is absent from seed {self.seed}")
            score_to_label(float(row["human_score"]))
            row["split"] = split[str(row["task_uid"])]
            rows[item_id] = row
        if not rows:
            raise ValueError(f"AURORA metadata is empty at {metadata_path}")
        self._rows = rows

    def list_items(self) -> list[str]:
        self._load()
        assert self._rows is not None
        selected = {
            item_id: row
            for item_id, row in self._rows.items()
            if row["model"] in self.models and row["task"] in self.tasks
        }
        missing: list[str] = []
        for row in selected.values():
            for field in ("source_path", "edited_path"):
                path = self.root / str(row[field])
                if not path.is_file() or not path.stat().st_size:
                    missing.append(str(path.relative_to(self.root)))
        if missing:
            preview = ", ".join(missing[:5])
            suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise FileNotFoundError(
                f"AURORA-Bench setup is incomplete: {preview}{suffix}; "
                "rerun ./run/setup_aurora_bench.sh"
            )
        return sorted(selected)

    def load_sample(self, item_id: str) -> dict[str, Any]:
        self._load()
        assert self._rows is not None
        if item_id not in self._rows:
            raise KeyError(item_id)
        row = self._rows[item_id]
        if row["model"] not in self.models or row["task"] not in self.tasks:
            raise KeyError(item_id)
        source_path = self.root / str(row["source_path"])
        edited_path = self.root / str(row["edited_path"])
        if not source_path.is_file() or not edited_path.is_file():
            raise FileNotFoundError(
                f"Missing AURORA-Bench image for {item_id}; "
                "run ./run/setup_aurora_bench.sh"
            )
        return {
            "item_id": item_id,
            "project": "aurora-bench",
            "prompt_idx": int(row["prompt_index"]),
            "task_uid": str(row["task_uid"]),
            "model": str(row["model"]),
            "editor": str(row["model"]),
            "algorithm": str(row["model"]),
            "use_case": "text-guided-image-editing",
            "source_dataset": "AURORA-Bench",
            "task": str(row["task"]),
            "split": str(row["split"]),
            "split_seed": self.seed,
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
        if row["model"] not in self.models or row["task"] not in self.tasks:
            raise KeyError(item_id)
        score = float(row["human_score"])
        target_score, target_label = score_to_label(score)
        return {
            "item_id": item_id,
            "task_uid": str(row["task_uid"]),
            "editor": str(row["model"]),
            "model": str(row["model"]),
            "task": str(row["task"]),
            "split": str(row["split"]),
            "split_seed": self.seed,
            "source_dataset": "AURORA-Bench",
            "human_score": score,
            "human_score_scale": [0.0, 2.0],
            "normalized_sc": score / 2.0,
            "target_score": target_score,
            "target_label": target_label,
            # The public artifact contains only the aggregate. The paper reports three
            # expert annotators, but does not expose their individual judgments.
            "n_annotators": 3,
            "ratings": [],
            "raw_ratings_available": False,
        }

    def load_all(self) -> tuple[dict[str, Any], dict[str, Any]]:
        items = self.list_items()
        return (
            {item_id: self.load_sample(item_id) for item_id in items},
            {item_id: self.load_label(item_id) for item_id in items},
        )
