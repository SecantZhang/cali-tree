"""The 6-metric video-editing rubric (M1–M6).

This inlines the metric catalog that previously lived in ``evaluation/mllm_judge_metrics.py``
so the package is self-contained. Judges import definitions from here.
"""

from __future__ import annotations

from dataclasses import dataclass

SCORE_MIN = 1
SCORE_MAX = 5


@dataclass(frozen=True)
class JudgeMetric:
    id: str  # "M1".."M6"
    metric: str  # human-readable name
    component: str  # "Plan" | "Video"
    modality: str  # "text" | "video"
    default_model_role: str  # "text" | "video" (which engine family)
    definition: str
    measures_what: str


JUDGE_METRICS: dict[str, JudgeMetric] = {
    "M1": JudgeMetric(
        id="M1",
        metric="Assembly Failure",
        component="Plan",
        modality="text",
        default_model_role="text",
        definition=(
            "Given the user prompt, notes JSON, and assembly_json, does the assembly plan "
            "even address the user's request? Binary pass/fail gate."
        ),
        measures_what="Whether the pipeline produced a plan that targets the stated goal.",
    ),
    "M2": JudgeMetric(
        id="M2",
        metric="Render Failure",
        component="Video",
        modality="video",
        default_model_role="video",
        definition=(
            "Is the rendered MP4 a non-broken, watchable video that plausibly attempts "
            "the user prompt? Catches render glitches, black frames, or wrong content."
        ),
        measures_what="Whether the rendered output is a valid, non-corrupt video.",
    ),
    "M3": JudgeMetric(
        id="M3",
        metric="Prompt completeness",
        component="Plan",
        modality="text",
        default_model_role="text",
        definition=(
            "Given source transcript, captions, and user prompt, does the assembled plan "
            "satisfy every part of the request? Scored 1-5."
        ),
        measures_what="Whether the assembly covers the full user prompt, not just a subset.",
    ),
    "M4": JudgeMetric(
        id="M4",
        metric="Visual Prompt Alignment",
        component="Video",
        modality="video",
        default_model_role="video",
        definition=(
            "Does the rendered video visually fulfill the user's prompt? Are B-roll, A-roll, "
            "cuts, and timing aligned with what was asked?"
        ),
        measures_what="Whether what appears on screen matches the user's stated intent.",
    ),
    "M5": JudgeMetric(
        id="M5",
        metric="Edit Coherence",
        component="Video",
        modality="video",
        default_model_role="video",
        definition=(
            "Flow, pacing, watchability. Are transitions smooth? Is pacing appropriate "
            "for the stated audience? Is audio/visual sync intact?"
        ),
        measures_what="Overall production quality and watchability of the rendered edit.",
    ),
    "M6": JudgeMetric(
        id="M6",
        metric="AV Sync",
        component="Video",
        modality="video",
        default_model_role="video",
        definition=(
            "Audio-visual synchronization judge with three sub-dimensions: "
            "(6a) Does the voiceover match the A-roll/B-roll shown at that time? "
            "(6b) Are there sudden pauses or interruptions in the voiceover track? "
            "(6c) Are there sudden pauses, freeze frames, or interruptions in the visuals? "
            "Each sub-dimension scored 1-5; overall score is their average."
        ),
        measures_what=(
            "Whether the audio and visual tracks are synchronized, continuous, and "
            "topically matched throughout the video."
        ),
    ),
}


def metric_definition(metric_id: str) -> str:
    """Definition + 'Measures:' line for a metric id, for embedding in prompts."""
    m = JUDGE_METRICS[metric_id]
    return f"{m.definition}\nMeasures: {m.measures_what}"
