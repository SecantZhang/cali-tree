"""``CalibratedResult`` — the per-item artifact a ``cl_adversarial`` interface node
produces: a ``DebateVerdict`` plus an ``optimized_prompt`` addendum a downstream
``Judge.run(..., extra_context=...)`` call can inject to re-score *this same item*
with the debate's own feedback in view.

Deliberately built on the already-implemented ``DebateVerdict``/``reasoning_trace`` —
no new LM calls, no cross-item aggregation (that's a separate, not-yet-designed
"aggregation node").
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .schema import DebateTranscript, DebateVerdict


@dataclass
class CalibratedResult:
    item_id: str
    metric_id: str
    original_score: Optional[float]
    final_score: Optional[float]
    score_delta: Optional[float]
    converged: bool
    rounds_run: int
    flags: list[str]
    optimized_prompt: str
    reasoning: str
    transcript: DebateTranscript
    # See DebateTranscript.grounded — whether this item's debate actually used a real
    # human anchor score (opt-in + a usable anchor existed) or fell back to blind
    # simulation. Interface-node code (human_scores/human_gap) attaches separately.
    grounded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibratedResult":
        data = dict(data)
        return cls(
            item_id=data["item_id"],
            metric_id=data["metric_id"],
            original_score=data.get("original_score"),
            final_score=data.get("final_score"),
            score_delta=data.get("score_delta"),
            converged=bool(data.get("converged", False)),
            rounds_run=data.get("rounds_run", 0),
            flags=list(data.get("flags") or []),
            optimized_prompt=data.get("optimized_prompt", ""),
            reasoning=data.get("reasoning", ""),
            transcript=DebateTranscript.from_dict(data["transcript"]),
            grounded=bool(data.get("grounded", False)),
        )


def render_optimized_prompt_addendum(verdict: DebateVerdict) -> str:
    """Frame the debate outcome as instructive feedback for a re-judge of this same
    item. Deterministic (no extra LM call) — a direct restatement of the verdict, not a
    rewrite of it."""
    # Both are guarded together: the "revised the score from X to Y" branch below needs
    # both, and initial_score is None only for a malformed anchor that shouldn't reach
    # here at all (see cl_adversarial_node._usable_anchor) — but guarding it directly
    # here too means this function is safe regardless of what the caller validated.
    if verdict.final_score is None or verdict.initial_score is None:
        return (
            "A prior adversarial review of this item could not reach a valid revised "
            "score (see flags: " + ", ".join(verdict.flags) + "). Treat this item's "
            "score with extra scrutiny."
        )

    if verdict.converged and verdict.score_delta is not None and abs(verdict.score_delta) < 1e-9:
        verdict_line = (
            f"A prior adversarial review of this item confirmed the original score of "
            f"{verdict.final_score:g} held up under scrutiny."
        )
    else:
        state = "converged" if verdict.converged else "did not fully converge but"
        verdict_line = (
            f"A prior adversarial review of this item ({state}) revised the score from "
            f"{verdict.initial_score:g} to {verdict.final_score:g}."
        )

    return (
        f"{verdict_line} Consider this feedback when scoring:\n{verdict.reasoning_trace}"
    )


def to_calibrated_result(verdict: DebateVerdict) -> CalibratedResult:
    return CalibratedResult(
        item_id=verdict.item_id,
        metric_id=verdict.metric_id,
        original_score=verdict.initial_score,
        final_score=verdict.final_score,
        score_delta=verdict.score_delta,
        converged=verdict.converged,
        rounds_run=verdict.rounds_run,
        flags=list(verdict.flags),
        optimized_prompt=render_optimized_prompt_addendum(verdict),
        reasoning=verdict.reasoning_trace,
        transcript=verdict.transcript,
        grounded=verdict.grounded,
    )
