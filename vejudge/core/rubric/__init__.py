"""Rubric definitions and scoring schema for video-editing judging."""

from .definitions import (
    JUDGE_METRICS,
    SCORE_MAX,
    SCORE_MIN,
    JudgeMetric,
    metric_definition,
)

__all__ = [
    "JUDGE_METRICS",
    "SCORE_MAX",
    "SCORE_MIN",
    "JudgeMetric",
    "metric_definition",
]
