"""Preprocessing Node executor — pass-through stub.

Per interface.md's Preprocessing Node spec (frame/keyframe/clip sampling, ASR transcript,
OCR, captions, shot boundaries, blur/flicker metrics, input strategies A-E) — none of
which has a concrete implementation yet (`vejudge/preprocessing/pp_template/base.py` is
still just an abstract `Preprocessor` base with no subclasses). This node exists to give
the graph the right shape and vocabulary now (dataset in, dataset out, sitting between
Dataset and Judge) without inventing artifact extraction ahead of that work landing — the
params are present but inert; real extraction is a separate, larger future feature.
"""

from __future__ import annotations

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

ARTIFACT_TYPES = [
    "sampled_frames", "keyframes", "short_clips", "asr_transcript", "ocr_text",
    "captions", "shot_boundaries", "audio_event_labels", "blur_flicker_metrics",
]


@register
class PreprocessingNodeExecutor(NodeExecutor):
    node_type = "preprocessing"
    category = "node_preprocessing"
    input_sockets = {"dataset": "dataset"}
    output_sockets = {"dataset": "dataset"}
    param_schema = {
        "artifact_types": {"type": "list[enum]", "options": ARTIFACT_TYPES, "default": None},
        "input_strategy": {
            "type": "enum", "options": ["A", "B", "C", "D", "E"], "default": "A",
        },
        "cache_policy": {
            "type": "enum", "options": ["reuse_if_present", "force_recompute"],
            "default": "reuse_if_present",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        dataset = ctx.inputs.get("dataset")
        if dataset is None:
            return NodeRunResult(
                status="error",
                error="Preprocessing Node requires a 'dataset' input (wire a Dataset "
                "Node's `dataset` output)",
            )
        # Pass-through: no artifact extraction is implemented yet (see module docstring).
        return NodeRunResult(
            outputs={"dataset": dataset},
            meta={"n_items": len(dataset), "note": "pass-through: no artifacts extracted yet"},
        )
