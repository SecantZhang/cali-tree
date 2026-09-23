#!/usr/bin/env python3
"""Materialize the public ImagenHub data used by Cali-Tree.

Downloads are resumable: an existing non-empty file is reused, while the final manifest
records a SHA-256 for every materialized asset.  No gateway credentials are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests

from vejudge import config
from vejudge.database.dl_imagenhub import EDITORS, IMAGENMUSEUM_EDITORS, build_split_manifest

RATINGS_BASE = (
    "https://raw.githubusercontent.com/TIGER-AI-Lab/ImagenHub/refs/heads/main/"
    "eval/human_ratings/Text-Guided_IE"
)
MUSEUM_BASE = "https://chromaica.github.io/Museum/ImagenHub_Text-Guided_IE"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path) -> None:
    if path.is_file() and path.stat().st_size:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    headers = {"Range": f"bytes={partial.stat().st_size}-"} if partial.exists() else {}
    with requests.get(url, headers=headers, stream=True, timeout=120) as response:
        if response.status_code == 200 and partial.exists() and headers:
            partial.unlink()
        response.raise_for_status()
        mode = "ab" if response.status_code == 206 else "wb"
        with partial.open(mode) as stream:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    stream.write(chunk)
    partial.replace(path)


def build_asset_manifest(root: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".part") and path.name != "manifest.json"
    )
    return {
        "dataset": "ImagenHub/Text_Guided_Image_Editing",
        "revision": "a393c006cd0c843d8ca57ae4a6ee954ee376ef67",
        "tasks": len(rows),
        "editors": list(IMAGENMUSEUM_EDITORS),
        "rating_editors": list(EDITORS),
        "files": {
            str(path.relative_to(root)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in files
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=config.IMAGENHUB_ROOT)
    parser.add_argument("--limit", type=int, default=None, help="Development-only task limit")
    args = parser.parse_args()
    root: Path = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "Missing 'datasets'. Install with: pip install -e '.[calitree]'",
            file=sys.stderr,
        )
        return 2

    for rater in (1, 2, 3):
        name = f"Text-Guided_IE_rater{rater}.tsv"
        download(f"{RATINGS_BASE}/{name}", root / "ratings" / name)

    dataset = load_dataset(
        "ImagenHub/Text_Guided_Image_Editing",
        split="filtered",
        revision="a393c006cd0c843d8ca57ae4a6ee954ee376ef67",
    )
    rows: list[dict[str, object]] = []
    for index, row in enumerate(dataset):
        if args.limit is not None and index >= args.limit:
            break
        uid = f"sample_{row['img_id']}_{int(row['turn_index'])}"
        source_path = root / "inputs" / f"{uid}.jpg"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            row["source_img"].convert("RGB").save(source_path, format="JPEG", quality=95)
        rows.append({
            "uid": uid,
            "img_id": str(row["img_id"]),
            "turn_index": int(row["turn_index"]),
            "instruction": str(row["instruction"]),
            "source_global_caption": str(row.get("source_global_caption") or ""),
            "target_global_caption": str(row.get("target_global_caption") or ""),
            "target_local_caption": str(row.get("target_local_caption") or ""),
        })
        remote_name = f"{uid}.jpg"
        for editor in IMAGENMUSEUM_EDITORS:
            download(
                f"{MUSEUM_BASE}/{editor}/{remote_name}",
                root / "outputs" / editor / remote_name,
            )

    metadata_path = root / "metadata.jsonl"
    metadata_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    task_uids = [str(row["uid"]) for row in rows]
    if len(task_uids) >= 29:
        split_dir = root / "splits"
        split_dir.mkdir(exist_ok=True)
        for seed in (42, 43, 44):
            path = split_dir / f"seed_{seed}.json"
            path.write_text(
                json.dumps(build_split_manifest(task_uids, seed=seed), indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )

    manifest = build_asset_manifest(root, rows)
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"ImagenHub ready at {root}: {len(rows)} tasks, "
        f"{len(IMAGENMUSEUM_EDITORS)} public editors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
