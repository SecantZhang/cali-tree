"""The fixed, versioned v1 area-rubric catalog."""

from __future__ import annotations

from typing import Any

AREA_RUBRICS: dict[str, dict[str, Any]] = {
    "transition_smoothness": {
        "label": "Transition Smoothness",
        "unit_types": ["edit_boundary"],
        "version": "area-transition-v1",
        "instruction": (
            "Judge whether the edit at the center of this boundary clip is intentional and "
            "smooth. Consider visual discontinuity, motion, framing, transition effects, "
            "rhythm, and whether the cut disrupts comprehension."
        ),
    },
    "visual_quality_temporal_stability": {
        "label": "Visual Quality & Temporal Stability",
        "unit_types": ["shot"],
        "version": "area-shot-quality-v1",
        "instruction": (
            "Judge this shot's visual integrity over time. Consider blur, flicker, freezing, "
            "warping, compression, text stability, and distracting temporal artifacts."
        ),
    },
    "pacing_narrative_coherence": {
        "label": "Pacing & Narrative Coherence",
        "unit_types": ["sequence"],
        "version": "area-sequence-pacing-v1",
        "instruction": (
            "Judge whether this sequence has coherent progression and appropriate pacing for "
            "the user's request. Consider shot duration, ordering, repetition, clarity, and "
            "whether the segment advances the intended story."
        ),
    },
    "audio_continuity_av_sync": {
        "label": "Audio Continuity & AV Sync",
        "unit_types": ["audio_event", "edit_boundary"],
        "version": "area-audio-continuity-v1",
        "instruction": (
            "Judge audio continuity and audiovisual synchronization in this local window. "
            "Consider pops, abrupt cutoffs, awkward silence, repeated speech, mismatched "
            "voiceover/visual timing, and whether the edit sounds intentionally continuous."
        ),
    },
}


def area_rubric_spec(rubric_id: str) -> dict[str, Any]:
    if rubric_id not in AREA_RUBRICS:
        raise KeyError(f"Unknown area rubric '{rubric_id}'")
    rubric = AREA_RUBRICS[rubric_id]
    return {
        "kind": "area",
        "rubric_id": rubric_id,
        "label": rubric["label"],
        "unit_types": list(rubric["unit_types"]),
        "version": rubric["version"],
        "modality": "video",
        "system": (
            "You are a strict video-editing evaluator. Score only the supplied local unit. "
            "Do not infer quality outside its timestamp range. Return one JSON object."
        ),
        "instruction": rubric["instruction"],
        "expected_fields": [
            "score_1_to_5", "severity", "confidence", "rationale", "cited_timestamps"
        ],
    }
