"""Run the judges over a sample, routing text vs video metrics to the right engine.

Each judge runs inside its own try/except so one failure never aborts a benchmark; the
failure is recorded in the result dict and surfaces in the report.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..core.judge import make_judge
from ..core.judge.registry import ALL_JUDGES, JUDGE_MODALITY
from ..lm_engine.lm_template import LMEngine


@dataclass
class JudgeEngines:
    """Engine routing by modality."""

    text: LMEngine
    video: LMEngine

    def for_metric(self, metric_id: str) -> LMEngine:
        return self.video if JUDGE_MODALITY[metric_id] == "video" else self.text


def run_judges_for_sample(
    sample: dict[str, Any],
    engines: JudgeEngines,
    *,
    judges: Optional[list[str]] = None,
    skip_video: bool = False,
    logger: Optional[Any] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Run the requested judges (default all M1–M6) on one sample.

    ``progress_cb`` (if given) is called with each metric id just before that judge
    runs, so a caller can drive a progress bar showing the current judge.
    """
    selected = judges or ALL_JUDGES
    has_video = bool((sample.get("output") or {}).get("output_video_path"))
    results: dict[str, Any] = {}

    for metric_id in selected:
        is_video = JUDGE_MODALITY[metric_id] == "video"
        if is_video and (skip_video or not has_video):
            results[metric_id] = {
                "judge": metric_id,
                "metric_id": metric_id,
                "parsed": None,
                "skipped": True,
            }
            continue

        if progress_cb:
            progress_cb(metric_id)
        if logger:
            logger.info("  %s (%s)...", metric_id, JUDGE_MODALITY[metric_id])
        t0 = time.time()
        judge = make_judge(metric_id, engines.for_metric(metric_id))
        results[metric_id] = judge.run(sample)
        if logger:
            took = time.time() - t0
            flags = results[metric_id].get("validation_flags") or []
            logger.info("    done (%.1fs) flags=%s", took, flags)

    return results


def main(argv: Optional[list[str]] = None) -> int:
    """``vejudge-eval`` entry point — points at the benchmark CLI for v1.

    A standalone single-sample eval CLI can be added later; for now the benchmark
    runner is the supported end-to-end entry point.
    """
    print(
        "vejudge-eval: use `vejudge-bench` to run the human-vs-judge benchmark.\n"
        "  e.g. vejudge-bench --dry-run --models peanut --projects prj-paris-2025"
    )
    return 0
