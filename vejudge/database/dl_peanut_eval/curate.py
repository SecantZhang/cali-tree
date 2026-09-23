"""Build a curated judge sample from project paths + a notes/video pair.

Adapted from the original ``curate_peanut_sample.py`` to read ``user_query.json``
(``prompts[].user_request`` + ``target_duration``) instead of a separate refine-query
file. The output dict matches the PeanutEval sample shape the judges expect.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


def _abspath(p: str) -> str:
    return os.path.abspath(p)


def _truncate(s: str, max_chars: int) -> str:
    return s if len(s) <= max_chars else s[: max_chars - 3] + "..."


def _load_a_roll_pool(project_dir: str) -> Any:
    for name in ("all_sentences.json", "aroll.json"):
        p = os.path.join(project_dir, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return []


def load_user_prompt(project_dir: str, prompt_index: int) -> tuple[str, Optional[int]]:
    """Return (user_request, target_duration) for a prompt index from user_query.json."""
    uq_path = os.path.join(project_dir, "user_query.json")
    if not os.path.isfile(uq_path):
        return "", None
    with open(uq_path, encoding="utf-8") as f:
        uq = json.load(f)
    prompts = uq.get("prompts") or []
    if prompt_index < 0 or prompt_index >= len(prompts):
        raise IndexError(
            f"prompt_index {prompt_index} out of range (len={len(prompts)}) for {uq_path}"
        )
    entry = prompts[prompt_index]
    return str(entry.get("user_request", "")), entry.get("target_duration")


def curate_sample(
    *,
    project: str,
    project_dir: str,
    prompt_index: int,
    model: str,
    use_case: str,
    notes_path: str,
    output_video_path: str,
    otio_path: str = "",
    plan_path: str = "",
    captions_max_chars: int = 16000,
    transcript_max_chars: int = 200000,
) -> dict[str, Any]:
    from .extract_notes import extract_peanut_assembly_from_notes
    from .extract_otio import extract_assembly_from_otio

    project_dir = _abspath(project_dir)
    notes_path = _abspath(notes_path) if notes_path else ""
    output_video_path = _abspath(output_video_path) if output_video_path else ""
    otio_path = _abspath(otio_path) if otio_path else ""
    plan_path = _abspath(plan_path) if plan_path else ""

    user_prompt, target_duration = load_user_prompt(project_dir, prompt_index)

    aroll = _load_a_roll_pool(project_dir)
    transcript_text = _truncate(
        json.dumps(aroll, ensure_ascii=False, indent=2), transcript_max_chars
    )

    visual_path = os.path.join(project_dir, "all_visual_clips.json")
    captions_excerpt = ""
    if os.path.isfile(visual_path):
        with open(visual_path, encoding="utf-8") as f:
            captions_excerpt = _truncate(f.read(), captions_max_chars)

    asset_paths: list[str] = []
    for rel in ("video_id_map.json", "all_visual_clips.json", "all_sentences.json",
                "user_query.json", "config.json"):
        p = os.path.join(project_dir, rel)
        if os.path.isfile(p):
            asset_paths.append(_abspath(p))
    for extra in (notes_path, otio_path, plan_path, output_video_path):
        if extra:
            asset_paths.append(extra)

    # Assembly source precedence: peanut's notes.json, else an OTIO timeline
    # (coconut/grapenut), else empty (video-only — the judge still has the render).
    assembly_json: dict[str, Any] = {}
    if notes_path and os.path.isfile(notes_path):
        assembly_json = extract_peanut_assembly_from_notes(notes_path)
    elif otio_path and os.path.isfile(otio_path):
        assembly_json = extract_assembly_from_otio(otio_path)

    return {
        "item_id": f"{project}::{prompt_index}::{model}",
        "project": project,
        "prompt_idx": prompt_index,
        "model": model,
        "use_case": use_case,
        "input": {
            "asset_filepaths": sorted(set(asset_paths)),
            "user_prompt": user_prompt,
            "target_duration": target_duration,
            "initial_timeline_text": "",
            "b_roll_captions_json_path": _abspath(visual_path)
            if os.path.isfile(visual_path)
            else "",
            "b_roll_captions_excerpt": captions_excerpt,
            "a_roll_transcript_text": transcript_text,
            "prompt_index": prompt_index,
            "notes_path": notes_path,
        },
        "algorithm": model,
        "output": {
            "output_video_path": output_video_path,
            "otio_path": otio_path,
            "plan_path": plan_path,
            "assembly_json": assembly_json,
        },
    }
