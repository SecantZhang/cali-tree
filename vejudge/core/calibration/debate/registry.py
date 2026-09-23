"""Debate registry: a thin factory binding a metric + two engines to a ``DebateRunner``.

Same size/spirit as ``core.judge.registry`` -- NOT the versioned "calibration registry"
(fitted-model store) described in docs/architecture.md/CLAUDE.md, which has no backing
code yet and is out of scope here (see the plan's scope-boundary note).
"""

from __future__ import annotations

from typing import Optional

from ....lm_engine.lm_template import LMEngine
from ...judge.registry import ALL_JUDGES
from ...prompts import d1_judge_debate, d2_human_proxy_debate
from .runner import DebateConfig, DebateRunner

DEBATE_METRICS: list[str] = list(ALL_JUDGES)


def make_debate(
    metric_id: str,
    judge_engine: LMEngine,
    human_proxy_engine: LMEngine,
    *,
    judge_model: Optional[str] = None,
    proxy_model: Optional[str] = None,
    config: Optional[DebateConfig] = None,
) -> DebateRunner:
    if metric_id not in DEBATE_METRICS:
        raise ValueError(f"Unknown metric '{metric_id}'")
    return DebateRunner(
        metric_id=metric_id,
        judge_engine=judge_engine,
        proxy_engine=human_proxy_engine,
        judge_model=judge_model,
        proxy_model=proxy_model,
        config=config,
    )


def debate_prompt_versions() -> dict[str, str]:
    """D1/D2 prompt versions, for recording in run configs alongside ``prompt_versions()``."""
    return {"D1": d1_judge_debate.VERSION, "D2": d2_human_proxy_debate.VERSION}
