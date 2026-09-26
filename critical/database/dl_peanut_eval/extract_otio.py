"""Extract an output-timeline-aware assembly view from an OTIO timeline (JSON).

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
    """Convert an OTIO RationalTime sub-object to seconds."""
    if not isinstance(node, dict):
        return None
    value = node.get("value")
    rate = node.get("rate") or 1
    try:
        return float(value) / float(rate)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


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
    gaps: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for track_index, track in enumerate(tracks):
        if not isinstance(track, dict):
            continue
        kind = track.get("kind")
        output_cursor = 0.0
        for child_index, child in enumerate(track.get("children") or []):
            if not isinstance(child, dict):
                continue
            schema = str(child.get("OTIO_SCHEMA", ""))
            sr = child.get("source_range") or {}
            duration = _rt_value(sr.get("duration")) or 0.0
            record = {
                "name": child.get("name"),
                "track": kind,
                "track_index": track_index,
                "child_index": child_index,
                "start": _rt_value(sr.get("start_time")),
                "duration": duration,
                "output_start": output_cursor,
                "output_end": output_cursor + duration,
            }
            if schema.startswith("Clip"):
                clips.append(record)
                output_cursor += duration
            elif schema.startswith("Gap"):
                gaps.append(record)
                output_cursor += duration
            elif schema.startswith("Transition"):
                record.update({
                    "in_offset": _rt_value(child.get("in_offset")) or 0.0,
                    "out_offset": _rt_value(child.get("out_offset")) or 0.0,
                })
                transitions.append(record)

    if not clips:
        return {}
    return {
        "source": "otio",
        "n_clips": len(clips),
        "tracks": sorted({c["track"] for c in clips if c.get("track")}),
        "clips": clips,
        "gaps": gaps,
        "transitions": transitions,
    }
