"""Pull a compact a-roll / b-roll / transcript view from OrchestratorRefineV2 notes.

Copied from the original evaluation framework (extract_peanut_output.py) so the
package is self-contained.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def _read_notes(notes_path: str) -> dict[str, Any]:
    with open(notes_path, encoding="utf-8") as f:
        return json.load(f)


def _find_orchestrator_stage(stages: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Find the refine orchestrator stage, version-agnostically.

    peanut output notes use OrchestratorRefineV2, V4, ... — match any ``OrchestratorRefine*``
    (prefer the last). Fall back to any stage whose output carries a recognizable assembly
    field, so future stage renames still work.
    """
    if not isinstance(stages, list):
        return None
    refine = [s for s in stages if str(s.get("name", "")).startswith("OrchestratorRefine")]
    if refine:
        return refine[-1]
    for st in reversed(stages):
        out = st.get("output") or {}
        if isinstance(out, dict) and any(
            k in out for k in ("finalClipIds", "finalSegments", "finalTracks")
        ):
            return st
    return None


def _last_timeline_text_from_sub_stages(sub_stages: list[dict[str, Any]]) -> Optional[str]:
    """Latest word-level timeline string seen in a critic sub-stage."""
    last: Optional[str] = None
    for sub in sub_stages:
        inp = sub.get("input") or {}
        if not isinstance(inp, dict):
            continue
        ct = inp.get("currentTimeline")
        if isinstance(ct, str) and ct.strip():
            last = ct
    return last


_WORD_LINE = re.compile(r"^\s*(\d+),(.+),([\d.]+)\s*$")


def transcript_from_timeline_text(timeline_text: str) -> str:
    """Join word tokens from 'word_id,text,dur' lines into a single transcript."""
    parts: list[str] = []
    for line in timeline_text.splitlines():
        line = line.strip()
        if not line or line.startswith("clip "):
            continue
        m = _WORD_LINE.match(line)
        if not m:
            continue
        text = m.group(2).strip().strip('"')
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def extract_peanut_assembly_from_notes(notes_path: str) -> dict[str, Any]:
    """Return assembly_json with a_roll / b_roll / transcript / notes_prompt."""
    notes = _read_notes(notes_path)
    stages = notes.get("stages") or []
    orch = _find_orchestrator_stage(stages) if isinstance(stages, list) else None
    if not orch:
        return {
            "a_roll": {},
            "b_roll": [],
            "transcript": "",
            "notes_prompt": notes.get("prompt", ""),
        }

    out = orch.get("output") or {}
    a_roll: dict[str, Any] = {}
    b_roll: list[dict[str, Any]] = []
    transcript = ""

    # --- V2 schema: finalClipIds + trimmedWordIds + word-level timeline ----------
    final_ids = out.get("finalClipIds")
    if isinstance(final_ids, list):
        a_roll["final_clip_ids"] = final_ids
        trimmed = out.get("trimmedWordIds")
        a_roll["trimmed_word_ids"] = trimmed if isinstance(trimmed, list) else []
        timeline_text = _last_timeline_text_from_sub_stages(orch.get("subStages") or [])
        if timeline_text:
            a_roll["final_timeline_word_view"] = timeline_text
            transcript = transcript_from_timeline_text(timeline_text)

    # --- V4 schema: finalSegments (A-roll clips) + finalTracks (v1/v2 with captions) ---
    segs = out.get("finalSegments")
    if isinstance(segs, list):
        a_roll["final_segments"] = segs
        a_roll["n_segments"] = len(segs)
    tracks = out.get("finalTracks")
    if isinstance(tracks, dict):
        a_roll["track_sizes"] = {k: len(v) for k, v in tracks.items()
                                 if isinstance(v, list)}
        # B-roll overlay tracks carry captions; collect every captioned clip.
        for tname, clips in tracks.items():
            if tname == "v1" or not isinstance(clips, list):
                continue  # v1 is the main A-roll track
            for c in clips:
                if isinstance(c, dict) and c.get("caption"):
                    b_roll.append({k: c.get(k) for k in
                                   ("video_id", "start_ms", "end_ms", "caption")})

    return {
        "a_roll": a_roll,
        "b_roll": b_roll,
        "transcript": transcript,
        "notes_prompt": notes.get("prompt", ""),
    }
