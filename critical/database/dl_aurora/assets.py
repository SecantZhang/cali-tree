"""Normalize the known source/output panels in the pinned AURORA release.

Only Something-Something outputs from these three editors are composites in
the 2024-12-05 archive. Other images, including naturally wide scenes, are kept
intact. Setup owns materialization; the loader remains read-only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, ImageStat


COMPOSITE_EDITORS = frozenset({
    "instruct-pix2pix-00-22000",
    "finetune_magicbrush_ag_something_kubric_15-15-1-1_init-magic_first_epoch=02-step=41999",
    "magic_reproduce_epoch=47-step=12999",
})


def is_release_composite(task: str, editor: str) -> bool:
    return task == "something" and editor in COMPOSITE_EDITORS


def source_preview_distance(source: Image.Image, preview: Image.Image) -> float:
    """JPEG-tolerant source correspondence; unrelated scenes must not be cropped."""
    source, preview = source.convert("RGB"), preview.convert("RGB")
    target = preview.resize((64, 64), Image.Resampling.LANCZOS)
    candidates = [
        source.resize(preview.size, Image.Resampling.LANCZOS),
        ImageOps.fit(source, preview.size, method=Image.Resampling.LANCZOS),
    ]
    return min(
        sum(ImageStat.Stat(ImageChops.difference(
            candidate.resize((64, 64), Image.Resampling.LANCZOS), target,
        )).mean) / 3
        for candidate in candidates
    )


def materialize_output_panel(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    """Return copied metadata pointing to a lossless right-panel extraction.

    Routing depends exclusively on release task/editor metadata, never labels,
    instructions or predictions. The pinned archive audit found all 150 left
    previews within 1.20 RGB intensity units of their source at 64x64. A bound of
    2 guards this release contract; it is not a general composite detector.
    """
    result = dict(row)
    if not is_release_composite(str(row["task"]), str(row["model"])):
        return result
    raw_relative = str(row.get("raw_edited_path", row["edited_path"]))
    raw_path, source_path = root / raw_relative, root / str(row["source_path"])
    raw_digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    with Image.open(source_path) as source, Image.open(raw_path) as composite:
        composite = composite.convert("RGB")
        width, height = composite.size
        if width % 2 or width < 2:
            raise ValueError(f"Invalid AURORA comparison panel dimensions: {raw_relative}")
        distance = source_preview_distance(source, composite.crop((0, 0, width // 2, height)))
        if distance > 2:
            raise ValueError(f"AURORA left panel does not match source: {raw_relative} (MAE={distance:.3f})")
        box = (width // 2, 0, width, height)
        panel = composite.crop(box)
    relative = Path("output_panels") / f"{raw_digest}.png"
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        with Image.open(destination) as existing:
            if existing.size != panel.size or existing.convert("RGB").tobytes() != panel.tobytes():
                raise ValueError(f"Existing AURORA output panel differs from raw crop: {destination}")
    else:
        temporary = destination.with_suffix(".tmp")
        panel.save(temporary, format="PNG")
        temporary.replace(destination)
    result.update({
        "raw_edited_path": raw_relative,
        "edited_path": str(relative),
        "image_normalization": {
            "layout": "source_left_output_right",
            "raw_sha256": raw_digest,
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "crop_box": list(box),
            "source_preview_mae64": distance,
            "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        },
    })
    return result
