"""Judge registry: metric modality split + a factory binding metrics to engines."""

from __future__ import annotations

from ...lm_engine.lm_template import LMEngine
from ..rubric.definitions import JUDGE_METRICS
from .base_judge import Judge

JUDGE_MODALITY: dict[str, str] = {
    mid: m.modality for mid, m in JUDGE_METRICS.items()
}
TEXT_JUDGES: list[str] = [mid for mid, mod in JUDGE_MODALITY.items() if mod == "text"]
VIDEO_JUDGES: list[str] = [mid for mid, mod in JUDGE_MODALITY.items() if mod == "video"]
ALL_JUDGES: list[str] = list(JUDGE_METRICS.keys())


def make_judge(metric_id: str, engine: LMEngine) -> Judge:
    return Judge(metric_id, engine)
