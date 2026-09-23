"""Local, reproducible ImagenHub/ImagenMuseum dataset adapter.

The setup script materializes the public ``filtered`` split into a compact path-based
layout.  This loader performs no network I/O: graph execution remains read-only and gives
an actionable error when setup has not been run.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any, Iterable, Optional

from ..dl_template.base import DataLoader
from ... import config

EDITORS: tuple[str, ...] = (
    "CycleDiffusion",
    "DiffEdit",
    "Imagic",
    "InstructPix2Pix",
    "MagicBrush",
    "Pix2PixZero",
    "Prompt2prompt",
    "SDEdit",
    "Text2Live",
)
# The official ratings include Imagic, but the cited public ImagenMuseum repository does
# not publish an Imagic directory. Keep Imagic in EDITORS so locally supplied assets remain
# usable, while public setup/defaults use only output sets that can actually be downloaded.
IMAGENMUSEUM_EDITORS: tuple[str, ...] = tuple(
    editor for editor in EDITORS if editor != "Imagic"
)
SPLIT_SEEDS: tuple[int, ...] = (42, 43, 44)


def _parse_rating(value: str) -> tuple[float, float]:
    parsed = ast.literal_eval(value.strip())
    if not isinstance(parsed, (list, tuple)) or len(parsed) != 2:
        raise ValueError(f"Expected [SC, PQ] rating, got {value!r}")
    sc, pq = float(parsed[0]), float(parsed[1])
    allowed = {0.0, 0.5, 1.0}
    if sc not in allowed or pq not in allowed:
        raise ValueError(f"Rating values must be in {sorted(allowed)}, got {parsed!r}")
    return sc, pq


def median_sc_label(ratings: Iterable[tuple[float, float]]) -> tuple[float, str]:
    values = [float(sc) for sc, _pq in ratings]
    if not values:
        raise ValueError("At least one human rating is required")
    median = float(statistics.median(values))
    return median, {0.0: "no", 0.5: "partial", 1.0: "yes"}[median]


def load_imagenhub_ratings(root: Path) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """Return ``uid -> editor -> [(SC, PQ), ...]`` from the three public TSVs."""
    out: dict[str, dict[str, list[tuple[float, float]]]] = {}
    ratings_dir = root / "ratings"
    paths = sorted(ratings_dir.glob("Text-Guided_IE_rater*.tsv"))
    if len(paths) != 3:
        raise FileNotFoundError(
            f"Expected 3 ImagenHub rating TSVs under {ratings_dir}; "
            "run ./run/setup_imagenhub.sh"
        )
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames is None or "uid" not in reader.fieldnames:
                raise ValueError(f"Invalid ImagenHub ratings header in {path}")
            missing = set(EDITORS) - set(reader.fieldnames)
            if missing:
                raise ValueError(f"{path} is missing editor columns: {sorted(missing)}")
            for row in reader:
                uid = Path(row["uid"]).stem
                by_editor = out.setdefault(uid, {})
                for editor in EDITORS:
                    by_editor.setdefault(editor, []).append(_parse_rating(row[editor]))
    return out


def build_split_manifest(
    task_uids: Iterable[str], *, seed: int, train_tasks: int = 29
) -> dict[str, Any]:
    uids = sorted(set(task_uids))
    if len(uids) < train_tasks:
        raise ValueError(f"Need at least {train_tasks} tasks, got {len(uids)}")
    shuffled = list(uids)
    random.Random(seed).shuffle(shuffled)
    train = sorted(shuffled[:train_tasks])
    test = sorted(shuffled[train_tasks:])
    digest = hashlib.sha256("\n".join(uids).encode()).hexdigest()
    return {
        "seed": seed,
        "task_digest": digest,
        "train": train,
        "test": test,
    }


class ImagenHubLoader(DataLoader):
    """Build JudgeSample-compatible image pairs plus classification labels."""

    def __init__(
        self,
        *,
        root: Optional[Path] = None,
        repeat: int = 1,
        editors: Optional[Iterable[str]] = None,
    ) -> None:
        self.root = Path(root or config.IMAGENHUB_ROOT)
        if repeat not in (1, 2, 3):
            raise ValueError("repeat must be 1, 2, or 3")
        self.repeat = repeat
        self.seed = SPLIT_SEEDS[repeat - 1]
        selected = tuple(editors or IMAGENMUSEUM_EDITORS)
        unknown = set(selected) - set(EDITORS)
        if unknown:
            raise ValueError(f"Unknown ImagenHub editors: {sorted(unknown)}")
        self.editors = selected
        self._metadata: Optional[dict[str, dict[str, Any]]] = None
        self._ratings: Optional[dict[str, dict[str, list[tuple[float, float]]]]] = None
        self._split: Optional[dict[str, str]] = None

    def _load(self) -> None:
        if self._metadata is not None:
            return
        metadata_path = self.root / "metadata.jsonl"
        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"ImagenHub metadata not found at {metadata_path}; "
                "run ./run/setup_imagenhub.sh"
            )
        metadata: dict[str, dict[str, Any]] = {}
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                metadata[str(row["uid"])] = row
        ratings = load_imagenhub_ratings(self.root)
        split_path = self.root / "splits" / f"seed_{self.seed}.json"
        if not split_path.is_file():
            raise FileNotFoundError(
                f"ImagenHub split manifest not found at {split_path}; "
                "run ./run/setup_imagenhub.sh"
            )
        manifest = json.loads(split_path.read_text(encoding="utf-8"))
        split = {uid: "train" for uid in manifest["train"]}
        split.update({uid: "test" for uid in manifest["test"]})
        self._metadata, self._ratings, self._split = metadata, ratings, split

    def list_items(self) -> list[str]:
        self._load()
        assert (
            self._metadata is not None
            and self._ratings is not None
            and self._split is not None
        )
        items: list[str] = []
        missing: list[str] = []
        for uid in sorted(self._metadata):
            if uid not in self._ratings:
                missing.append(f"ratings/{uid}")
                continue
            if uid not in self._split:
                missing.append(f"split/{uid}")
            if not (self.root / "inputs" / f"{uid}.jpg").is_file():
                missing.append(f"inputs/{uid}.jpg")
            for editor in self.editors:
                output = self.root / "outputs" / editor / f"{uid}.jpg"
                if not output.is_file():
                    missing.append(f"outputs/{editor}/{uid}.jpg")
                else:
                    items.append(f"{uid}::{editor}")
        if missing:
            preview = ", ".join(missing[:5])
            suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise FileNotFoundError(
                f"ImagenHub setup is incomplete: {preview}{suffix}; "
                "rerun ./run/setup_imagenhub.sh to resume"
            )
        return items

    def load_sample(self, item_id: str) -> dict[str, Any]:
        self._load()
        assert self._metadata is not None and self._split is not None
        try:
            uid, editor = item_id.rsplit("::", 1)
        except ValueError as exc:
            raise ValueError(f"Invalid ImagenHub item id {item_id!r}") from exc
        if uid not in self._metadata or editor not in self.editors:
            raise KeyError(item_id)
        row = self._metadata[uid]
        source_path = self.root / "inputs" / f"{uid}.jpg"
        output_path = self.root / "outputs" / editor / f"{uid}.jpg"
        if not source_path.is_file() or not output_path.is_file():
            raise FileNotFoundError(
                f"Missing ImagenHub image for {item_id}; run ./run/setup_imagenhub.sh"
            )
        return {
            "item_id": item_id,
            "project": "imagenhub-text-guided-ie",
            "prompt_idx": row.get("turn_index", 0),
            "task_uid": uid,
            "model": editor,
            "editor": editor,
            "algorithm": editor,
            "use_case": "text-guided-image-editing",
            "split": self._split[uid],
            "split_seed": self.seed,
            "input": {
                "user_prompt": row["instruction"],
                "instruction": row["instruction"],
                "source_image_path": str(source_path),
            },
            "output": {"edited_image_path": str(output_path)},
        }

    def load_label(self, item_id: str) -> dict[str, Any]:
        self._load()
        assert self._ratings is not None and self._split is not None
        uid, editor = item_id.rsplit("::", 1)
        ratings = self._ratings[uid][editor]
        median_sc, target = median_sc_label(ratings)
        return {
            "item_id": item_id,
            "task_uid": uid,
            "editor": editor,
            "split": self._split[uid],
            "split_seed": self.seed,
            "ratings": [{"sc": sc, "pq": pq} for sc, pq in ratings],
            "median_sc": median_sc,
            "target_label": target,
            "n_annotators": len(ratings),
        }

    def load_all(self) -> tuple[dict[str, Any], dict[str, Any]]:
        items = self.list_items()
        return (
            {item_id: self.load_sample(item_id) for item_id in items},
            {item_id: self.load_label(item_id) for item_id in items},
        )
