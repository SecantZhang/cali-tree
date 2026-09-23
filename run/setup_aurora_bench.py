#!/usr/bin/env python3
"""Materialize the official human-rated AURORA-Bench image-editing outputs.

The release uses two Google Drive files: a JSON table with 2,000 aggregate human
scores and a ZIP containing the 400 source images plus five generated outputs per
prompt. Downloads are resumable and checked against pinned SHA-256 digests before
safe extraction. No model or gateway credentials are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from run.setup_imagenhub import download, sha256
from vejudge import config
from vejudge.database.dl_aurora import (
    AURORA_MODELS,
    AURORA_TASKS,
    SPLIT_SEEDS,
    build_split_manifest,
    score_to_label,
)

RATINGS_FILE_ID = "1uWpVOit_eUvI6GnY_Bvaj_vPd3H8cTbT"
IMAGES_FILE_ID = "1wUwlxN1ArqTlCQQgnsj7DoXNoPRX71Ao"
DRIVE_DOWNLOAD = "https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
RATINGS_SHA256 = "a420cf439f0ccbc02735b358d5cf77dda6f6dd5df872b30d17ace326c98de145"
IMAGES_SHA256 = "8a3430a01cda0139d4c99835a75dca98e16ec6ccc486fa30afa4504f3f18c69f"
EXPECTED_ITEMS = 2_000
EXPECTED_TASKS = 400
TRAIN_TASKS = 80


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected}, got {actual}. "
            "Delete the file and rerun setup."
        )


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe path in AURORA archive: {member.filename!r}")
        if path.parts and path.parts[0] != "human_ratings":
            raise ValueError(
                f"Unexpected top-level path in AURORA archive: {member.filename!r}"
            )
        members.append(member)
    return members


def extract_archive(archive_path: Path, root: Path) -> None:
    """Safely extract missing/size-mismatched files from the official ZIP."""
    with zipfile.ZipFile(archive_path) as archive:
        for member in _safe_members(archive):
            destination = root / PurePosixPath(member.filename)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if destination.is_file() and destination.stat().st_size == member.file_size:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_suffix(destination.suffix + ".part")
            with archive.open(member) as source, partial.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if partial.stat().st_size != member.file_size:
                raise ValueError(f"Incomplete extraction for {member.filename!r}")
            partial.replace(destination)


def task_uid(input_path: str, prompt: str) -> str:
    canonical = f"{input_path}\n{prompt}".encode("utf-8")
    return f"aurora-task-{hashlib.sha256(canonical).hexdigest()[:20]}"


def parse_ratings(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("AURORA ratings JSON must be a list")
    rows: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    prompt_indices: dict[str, int] = {}
    for source_index, raw in enumerate(payload):
        if not isinstance(raw, dict):
            raise ValueError(f"AURORA ratings row {source_index} must be an object")
        missing = {"input", "gen", "prompt", "model", "score", "task"} - raw.keys()
        if missing:
            raise ValueError(
                f"AURORA ratings row {source_index} is missing {sorted(missing)}"
            )
        model = str(raw["model"])
        task = str(raw["task"])
        if model not in AURORA_MODELS:
            raise ValueError(f"Unknown AURORA model in row {source_index}: {model!r}")
        if task not in AURORA_TASKS:
            raise ValueError(f"Unknown AURORA task in row {source_index}: {task!r}")
        score = float(raw["score"])
        target_score, target_label = score_to_label(score)
        source_path = str(raw["input"])
        edited_path = str(raw["gen"])
        prompt = str(raw["prompt"]).strip()
        uid = task_uid(source_path, prompt)
        prompt_index = prompt_indices.setdefault(uid, len(prompt_indices))
        item_id = f"{uid}::{model}"
        if item_id in seen_items:
            raise ValueError(f"Duplicate AURORA item {item_id!r}")
        seen_items.add(item_id)
        rows.append({
            "source_index": source_index,
            "item_id": item_id,
            "task_uid": uid,
            "prompt_index": prompt_index,
            "instruction": prompt,
            "model": model,
            "task": task,
            "human_score": score,
            "target_score": target_score,
            "target_label": target_label,
            "source_path": source_path,
            "edited_path": edited_path,
        })
    if len(rows) != EXPECTED_ITEMS:
        raise ValueError(f"Expected {EXPECTED_ITEMS} AURORA ratings, got {len(rows)}")
    tasks = {row["task_uid"] for row in rows}
    if len(tasks) != EXPECTED_TASKS:
        raise ValueError(f"Expected {EXPECTED_TASKS} AURORA tasks, got {len(tasks)}")
    expected_models = set(AURORA_MODELS)
    by_task: dict[str, set[str]] = {}
    for row in rows:
        by_task.setdefault(str(row["task_uid"]), set()).add(str(row["model"]))
    incomplete = [uid for uid, models in by_task.items() if models != expected_models]
    if incomplete:
        raise ValueError(f"AURORA tasks missing model outputs: {incomplete[:5]}")
    return rows


def validate_assets(root: Path, rows: Iterable[dict[str, Any]]) -> list[Path]:
    paths: set[Path] = set()
    missing: list[str] = []
    for row in rows:
        for field in ("source_path", "edited_path"):
            path = root / str(row[field])
            paths.add(path)
            if not path.is_file() or not path.stat().st_size:
                missing.append(str(row[field]))
    if missing:
        preview = ", ".join(missing[:5])
        suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
        raise FileNotFoundError(f"AURORA archive is missing assets: {preview}{suffix}")
    return sorted(paths)


def build_manifest(
    root: Path,
    rows: list[dict[str, Any]],
    asset_paths: Iterable[Path],
) -> dict[str, Any]:
    metadata_path = root / "metadata.jsonl"
    ratings_path = root / "source" / "human_ratings.json"
    split_paths = [root / "splits" / f"seed_{seed}.json" for seed in SPLIT_SEEDS]
    files = sorted({ratings_path, metadata_path, *split_paths, *asset_paths})
    label_counts = Counter(str(row["target_label"]) for row in rows)
    task_counts = Counter(str(row["task"]) for row in rows)
    model_counts = Counter(str(row["model"]) for row in rows)
    return {
        "dataset": "McGill-NLP/AURORA-Bench human ratings",
        "paper": "arXiv:2407.03471v3",
        "release": "2024-12-05",
        "ratings_google_drive_id": RATINGS_FILE_ID,
        "images_google_drive_id": IMAGES_FILE_ID,
        "source_sha256": {
            "human_ratings.json": RATINGS_SHA256,
            "human_ratings.zip": IMAGES_SHA256,
        },
        "items": len(rows),
        "tasks": len({row["task_uid"] for row in rows}),
        "models": list(AURORA_MODELS),
        "task_types": list(AURORA_TASKS),
        "model_counts": dict(sorted(model_counts.items())),
        "task_type_counts": dict(sorted(task_counts.items())),
        "human_score_scale": {
            "minimum": 0.0,
            "maximum": 2.0,
            "semantics": {"0": "none", "1": "partial", "2": "full"},
            "note": "Published values are means of repeated discrete judgments.",
        },
        "class_mapping": {
            "no": "score < 0.5",
            "partial": "0.5 <= score < 1.5",
            "yes": "score >= 1.5",
        },
        "label_counts": {label: label_counts[label] for label in ("no", "partial", "yes")},
        "split": {
            "unit": "source-image/instruction task",
            "train_tasks": TRAIN_TASKS,
            "test_tasks": EXPECTED_TASKS - TRAIN_TASKS,
            "seeds": list(SPLIT_SEEDS),
        },
        "files": {
            str(path.relative_to(root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=config.AURORA_BENCH_ROOT)
    parser.add_argument(
        "--keep-archive",
        action="store_true",
        help="Retain the 482 MB source ZIP after successful extraction",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    ratings_path = source_dir / "human_ratings.json"
    archive_path = source_dir / "human_ratings.zip"

    download(DRIVE_DOWNLOAD.format(file_id=RATINGS_FILE_ID), ratings_path)
    verify_sha256(ratings_path, RATINGS_SHA256)
    rows = parse_ratings(ratings_path)

    # A complete prior extraction can rerun without redownloading the large archive.
    try:
        asset_paths = validate_assets(root, rows)
    except FileNotFoundError:
        download(DRIVE_DOWNLOAD.format(file_id=IMAGES_FILE_ID), archive_path)
        verify_sha256(archive_path, IMAGES_SHA256)
        extract_archive(archive_path, root)
        asset_paths = validate_assets(root, rows)

    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    task_uids = [str(row["task_uid"]) for row in rows]
    split_dir = root / "splits"
    split_dir.mkdir(exist_ok=True)
    for seed in SPLIT_SEEDS:
        (split_dir / f"seed_{seed}.json").write_text(
            json.dumps(
                build_split_manifest(task_uids, seed=seed, train_tasks=TRAIN_TASKS),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    manifest = build_manifest(root, rows, asset_paths)
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if archive_path.exists() and not args.keep_archive:
        archive_path.unlink()
    print(
        f"AURORA-Bench ready at {root}: {len(rows)} outputs from "
        f"{manifest['tasks']} tasks and {len(AURORA_MODELS)} models; "
        f"labels={manifest['label_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
