"""Extract a compact assembly view from an OTIO timeline (JSON).

coconut/grapenut renders ship a ``.otio`` (OTIO_SCHEMA JSON: ``tracks`` Stack → per-track
``children`` → ``Clip`` items with ``name`` + ``source_range``) instead of peanut's
``notes.json``. This pulls a light clip list so the text critic has assembly context; the
video judge scores from the rendered video regardless of this. Best-effort: returns ``{}``
on a missing/unparseable file, so an item with no usable timeline degrades to video-only.
"""

from __future__ import annotations

import json
from typing import Any


def _rt_value(node: Any) -> Any:
    """Pull the numeric ``value`` out of an OTIO RationalTime sub-object."""
    return node.get("value") if isinstance(node, dict) else None


def extract_assembly_from_otio(otio_path: str) -> dict[str, Any]:
    if not otio_path:
        return {}
    try:
        with open(otio_path, encoding="utf-8") as f:
            timeline = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}

    tracks = (timeline.get("tracks") or {}).get("children")
    if not isinstance(tracks, list):
        return {}

    clips: list[dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        kind = track.get("kind")
        for child in track.get("children") or []:
            if not isinstance(child, dict) or not str(child.get("OTIO_SCHEMA", "")).startswith("Clip"):
                continue
            sr = child.get("source_range") or {}
            clips.append({
                "name": child.get("name"),
                "track": kind,
                "start": _rt_value(sr.get("start_time")),
                "duration": _rt_value(sr.get("duration")),
            })

    if not clips:
        return {}
    return {
        "source": "otio",
        "n_clips": len(clips),
        "tracks": sorted({c["track"] for c in clips if c.get("track")}),
        "clips": clips,
    }
