"""Immutable on-disk calibration model registry."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class CalibrationRegistry:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, payload: dict[str, Any]) -> tuple[str, Path]:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        version = "edit-cal-" + hashlib.sha256(encoded.encode()).hexdigest()[:16]
        destination = self.root / f"{version}.json"
        if destination.exists():
            return version, destination
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        temporary.write_text(encoded + "\n", encoding="utf-8")
        try:
            # Link publication is atomic and refuses to replace an immutable version.
            os.link(temporary, destination)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)
        return version, destination
