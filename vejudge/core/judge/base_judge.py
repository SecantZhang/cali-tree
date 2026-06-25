"""``Judge`` — builds a prompt, calls an lm_engine, parses + validates the result.

One generic runner parametrized by metric id; the rubric decides modality (text vs
video) and thus whether the rendered video is attached as a media input.
"""

from __future__ import annotations

from typing import Any, Optional

from ...lm_engine.lm_template import LMEngine
from ..prompts import build_prompt
from ..rubric.definitions import JUDGE_METRICS
from .parse import parse_json_object
from .validate import validate_judge_output

METRIC_FULL_ID = {
    "M1": "M1_assembly_failure",
    "M2": "M2_render_failure",
    "M3": "M3_prompt_completeness",
    "M4": "M4_visual_alignment",
    "M5": "M5_edit_coherence",
    "M6": "M6_av_sync",
}


class Judge:
    """Run a single metric judge over a sample."""

    def __init__(self, metric_id: str, engine: LMEngine) -> None:
        if metric_id not in JUDGE_METRICS:
            raise ValueError(f"Unknown metric '{metric_id}'")
        self.metric_id = metric_id
        self.metric = JUDGE_METRICS[metric_id]
        self.engine = engine

    @property
    def full_id(self) -> str:
        return METRIC_FULL_ID[self.metric_id]

    def _media_inputs(self, sample: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        if self.metric.modality != "video":
            return None
        path = (sample.get("output") or {}).get("output_video_path", "")
        if not path:
            return None
        return [{"type": "video", "path": path}]

    def run(self, sample: dict[str, Any], *, model: Optional[str] = None) -> dict[str, Any]:
        spec = build_prompt(self.metric_id, sample)
        media = self._media_inputs(sample)

        result: dict[str, Any] = {
            "judge": self.full_id,
            "metric_id": self.metric_id,
            "prompt_version": spec.version,
            "parsed": None,
            "raw_content": "",
        }

        try:
            out = self.engine.generate(
                spec.user, media_inputs=media, system=spec.system, model=model
            )
        except Exception as e:  # noqa: BLE001 - recorded so the run continues
            result["error"] = str(e)
            result["validation_flags"] = ["engine_error"]
            return result

        content = out.get("content") or ""
        result["raw_content"] = content
        result["promptTokens"] = out.get("promptTokens")
        result["completionTokens"] = out.get("completionTokens")
        result["totalTokens"] = out.get("totalTokens")
        result["model"] = out.get("model")

        try:
            parsed = parse_json_object(content)
        except (ValueError, TypeError):
            parsed = None
        result["parsed"] = parsed

        required = list(build_prompt(self.metric_id, sample).schema.keys())
        validation = validate_judge_output(parsed, required_fields=required)
        result["validation_flags"] = validation.flags
        result["valid"] = validation.ok
        return result
