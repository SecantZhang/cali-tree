"""VE-Bench DB → JudgeSample loader + label materialization.

On-disk layout (under ``config.VEBENCH_ROOT``):
    label.txt                      # "<file>.mp4|<human_MOS>|<edit_prompt>" per line
    train_samples/edited/<file>.mp4  # the edited (output) video
    train_samples/src/<file>.mp4     # the source (input) video, same basename

Item id: ``<stem>::0::vebench`` where ``stem`` is the filename without ``.mp4`` (one edit
per file, so prompt_idx is always 0). The edit instruction is the judge's ``user_prompt``;
the edited mp4 is the ``output_video_path``; the source mp4 rides along as an asset.

``materialize_vebench_labels`` writes each item's MOS as a ``*_humaneval.json`` under
``HUMAN_ANNOTATIONS_ROOT/vebench/`` (dimension ``edit_quality``), so the existing Dataset
node's label lookup consumes VE-Bench with no graph change. VE-Bench ships a single
aggregated MOS (no per-rater breakdown), so it materializes as one annotator per item.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from ... import config
from ..dl_template import DataLoader, ItemId

_MODEL = "vebench"
VEBENCH_DIMENSION = "edit_quality"


@lru_cache(maxsize=1)
def _labels(label_path: str) -> dict[str, tuple[float, str]]:
    """stem -> (mos, edit_prompt), parsed from label.txt (pipe-delimited)."""
    out: dict[str, tuple[float, str]] = {}
    p = Path(label_path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        fname, mos_s, prompt = parts[0], parts[1], "|".join(parts[2:])
        try:
            mos = float(mos_s)
        except ValueError:
            continue
        stem = fname[:-4] if fname.endswith(".mp4") else fname
        out[stem] = (mos, prompt.strip())
    return out


class VeBenchLoader(DataLoader):
    def __init__(self, *, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else config.VEBENCH_ROOT

    def _label_path(self) -> Path:
        return self.root / "label.txt"

    def _edited(self, stem: str) -> Path:
        return self.root / "train_samples" / "edited" / f"{stem}.mp4"

    def _src(self, stem: str) -> Path:
        return self.root / "train_samples" / "src" / f"{stem}.mp4"

    def list_items(self) -> list[ItemId]:
        labels = _labels(str(self._label_path()))
        return [
            f"{stem}::0::{_MODEL}"
            for stem in sorted(labels)
            if self._edited(stem).is_file()
        ]

    def load_sample(self, item_id: ItemId) -> dict[str, Any]:
        stem = item_id.split("::")[0]
        labels = _labels(str(self._label_path()))
        mos_prompt = labels.get(stem)
        prompt = mos_prompt[1] if mos_prompt else ""
        edited = self._edited(stem)
        src = self._src(stem)
        assets = [str(src.resolve())] if src.is_file() else []
        return {
            "item_id": item_id,
            "project": stem,
            "prompt_idx": 0,
            "model": _MODEL,
            "use_case": "video_editing",
            "input": {
                "asset_filepaths": assets,
                "user_prompt": prompt,
                "target_duration": None,
                "initial_timeline_text": "",
                "b_roll_captions_excerpt": "",
                "a_roll_transcript_text": "",
                "prompt_index": 0,
                "notes_path": "",
                # The source (pre-edit) video — the reference the edit was applied to.
                "source_video_path": str(src.resolve()) if src.is_file() else "",
            },
            "algorithm": _MODEL,
            "output": {
                "output_video_path": str(edited.resolve()) if edited.is_file() else "",
                "assembly_json": {},
            },
        }


def materialize_vebench_labels(
    *, root: Optional[Path] = None, out_root: Optional[Path] = None, limit: Optional[int] = None
) -> int:
    """Write VE-Bench MOS as per-item ``*_humaneval.json`` under
    ``HUMAN_ANNOTATIONS_ROOT/vebench/`` so the Dataset node's label lookup finds them.
    Returns the number of files written. Idempotent (overwrites)."""
    loader = VeBenchLoader(root=root)
    labels = _labels(str(loader._label_path()))
    dest = Path(out_root) if out_root else (config.HUMAN_ANNOTATIONS_ROOT / _MODEL)
    dest.mkdir(parents=True, exist_ok=True)

    stems = [s for s in sorted(labels) if loader._edited(s).is_file()]
    if limit is not None:
        stems = stems[:limit]

    written = 0
    for stem in stems:
        mos, _prompt = labels[stem]
        record = {
            "annotator": "vebench_mos",
            "project": stem,
            "prompt_idx": 0,
            "model": _MODEL,
            "cell_key": f"prompt_0__{_MODEL}",
            "output_slot": 1,
            "annotation": {VEBENCH_DIMENSION: mos, "_complete": True},
        }
        (dest / f"vebench_{stem}_humaneval.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        written += 1
    return written
