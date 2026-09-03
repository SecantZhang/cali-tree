"""Localized source→edited change signal for the image judge.

The three v4 evidence scores collapse `partial` into the `no`/`yes` tuples (~95% of partial
cases share an exact score tuple with a non-partial case), so the judge has no feature for
"partially done". This preprocessor gives it one: a luminance change map between SOURCE and
EDITED plus a compact textual descriptor (how much changed, where, whether the rest of the
scene is preserved). It is deterministic and cached by content hash, so it adds no model call
and never recomputes for an unchanged (source, edited) pair.

Dependencies: numpy (core) + Pillow (the `calitree` extra, already required for Cali-Tree
live runs). Pillow is imported lazily so importing this module never fails in a core install.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .. import config
from .pp_template.base import Preprocessor

PREPROCESSOR_VERSION = "localized-change-v1"

_VERT = ("top", "middle", "bottom")
_HORIZ = ("left", "center", "right")


def _default_cache_root() -> Path:
    return config.DATA_ROOT / "preprocessing" / "localized_change"


def _sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class LocalizedChangeConfig:
    """Config for the change map; its ``hash()`` is part of the cache key."""

    resize: int = 256
    threshold: float = 0.12  # per-pixel |Δluminance| (0..1) to count a pixel as changed
    grid: int = 3            # coarse grid for locating the dominant change region
    preserved_extent: float = 0.5  # below this changed fraction, call the scene "preserved"

    def hash(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(body).hexdigest()[:20]


class LocalizedChangePreprocessor(Preprocessor):
    def __init__(
        self,
        cache_root: Optional[Path] = None,
        config: Optional[LocalizedChangeConfig] = None,
    ) -> None:
        self.cache_root = Path(cache_root) if cache_root else _default_cache_root()
        self.config = config or LocalizedChangeConfig()

    def cache_key(self, sample: dict[str, Any]) -> str:
        source = str((sample.get("input") or {}).get("source_image_path") or "")
        edited = str((sample.get("output") or {}).get("edited_image_path") or "")
        if not source or not edited:
            raise ValueError(
                f"Image sample {sample.get('item_id')} is missing source/edited paths"
            )
        body = json.dumps(
            {
                "item_id": sample.get("item_id"),
                "source": _sha256_file(source),
                "edited": _sha256_file(edited),
                "config": self.config.hash(),
                "version": PREPROCESSOR_VERSION,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(body).hexdigest()

    def run(self, sample: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
        key = self.cache_key(sample)
        out_dir = self.cache_root / key[:2]
        map_path = out_dir / f"{key}.png"
        meta_path = out_dir / f"{key}.json"
        if not force and map_path.is_file() and meta_path.is_file():
            return json.loads(meta_path.read_text(encoding="utf-8"))

        from PIL import Image  # lazy: only needed when a change map is actually computed

        size = (self.config.resize, self.config.resize)
        source = str((sample.get("input") or {}).get("source_image_path"))
        edited = str((sample.get("output") or {}).get("edited_image_path"))
        src = np.asarray(
            Image.open(source).convert("L").resize(size), dtype=np.float32
        ) / 255.0
        edt = np.asarray(
            Image.open(edited).convert("L").resize(size), dtype=np.float32
        ) / 255.0
        diff = np.abs(src - edt)
        mask = diff >= self.config.threshold
        changed_extent = float(mask.mean())

        grid = max(1, int(self.config.grid))
        cell = self.config.resize // grid
        grid_scores: list[float] = []
        for gy in range(grid):
            for gx in range(grid):
                cell_mask = mask[gy * cell:(gy + 1) * cell, gx * cell:(gx + 1) * cell]
                grid_scores.append(float(cell_mask.mean()) if cell_mask.size else 0.0)

        descriptor = self._describe(changed_extent, grid_scores, grid)
        out_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray((mask * 255).astype("uint8")).save(map_path)
        result = {
            "cache_key": key,
            "change_map_path": str(map_path),
            "changed_extent": changed_extent,
            "grid_scores": grid_scores,
            "descriptor": descriptor,
            "version": PREPROCESSOR_VERSION,
        }
        meta_path.write_text(json.dumps(result), encoding="utf-8")
        return result

    def _describe(
        self, extent: float, grid_scores: list[float], grid: int
    ) -> str:
        if grid_scores:
            index = int(max(range(len(grid_scores)), key=lambda i: grid_scores[i]))
            row, col = divmod(index, grid)
        else:
            row = col = 0
        vert = _VERT[min(row, 2)] if grid == 3 else f"row{row}"
        horiz = _HORIZ[min(col, 2)] if grid == 3 else f"col{col}"
        preserved = "yes" if extent < self.config.preserved_extent else "no"
        return (
            f"Localized change evidence: ~{round(extent * 100)}% of the image differs between "
            f"SOURCE and EDITED, concentrated in the {vert}-{horiz} region; rest-of-scene "
            f"preserved: {preserved}. Use this to tell an incomplete-but-present edit (partial) "
            f"from an absent edit (no)."
        )
