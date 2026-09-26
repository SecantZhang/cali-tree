"""``CalibratedResult`` — the per-item artifact a ``cl_adversarial`` interface node
produces: a ``DebateVerdict`` plus a concise, injectable ``optimized_prompt`` a
downstream ``Judge.run(..., extra_context=...)`` call can use to re-score *this same
item* with the debate's own feedback in view.

Two levels of calibration text:

- **Per-item**: a shared semantic schema and bounded renderer fed either by deterministic
  rule extraction or one optional LLM summarization call. Both retain reusable principles
  plus observable evidence while filtering human labels and target-score leakage.
- **Corpus** (``render_corpus_calibration_prompt``): the deferred "aggregation" — one
  *item-independent* prompt distilling the failure modes that recur *across* a whole run
  into a short, transferable calibration note, meant to be applied to unseen items. This
  is the generalizing artifact; the fixed taxonomy vocabulary is what lets it generalize
  instead of replaying any single item's narrative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Iterable, Optional

from ...prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from .schema import DebateTranscript, DebateVerdict
from .semantic_summary import SUMMARY_VERSION, render_summary, rule_based_summary

# Short, infinitive-phrased restatements of each judge failure mode, sized to slot into
# "tendency to {phrase}" / "to {phrase}" frames. Kept separate from
# FAILURE_MODE_TAXONOMY (whose entries are full declarative sentences aimed at the
# human-proxy persona prompt) but pinned to the same key set — see
# test_calibration_tendency_phrases_cover_the_taxonomy, which fails if the two drift.
_TENDENCY: dict[str, str] = {
    "surface_realism_bias": "reward clean-looking output that ignores the instruction",
    "frame_only_blindness": "miss flicker, motion, or other temporal defects",
    "audio_neglect": "ignore the audio track",
    "source_drift_blindness": "miss unintended changes to the source material",
    "overconfident_rationale": "assert a rationale without citing concrete evidence",
    "scale_drift": "let score meaning drift across prompts",
    "long_video_compression": "lose detail when summarizing a long video",
    "position_bias": "prefer a candidate for its ordering rather than its content",
    "self_bias": "favor outputs from a related model family",
    "category_imbalance": "over- or under-score based on edit category rather than quality",
}


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
    # Counts per FAILURE_MODE_TAXONOMY key across this item's debate (mirrors
    # DebateVerdict.failure_mode_summary) — carried onto the result so the corpus-level
    # aggregation can read it straight off calibration_results / a reloaded checkpoint,
    # without re-walking the transcript turns.
    failure_mode_summary: dict[str, int] = field(default_factory=dict)
    summary_mode_requested: str = "rule_based"
    summary_mode_used: str = "rule_based"
    summary_version: str = SUMMARY_VERSION
    semantic_summary: dict[str, Any] = field(default_factory=dict)
    summary_error: Optional[str] = None
    human_disagreement_profile: dict[str, Any] = field(default_factory=dict)

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
            failure_mode_summary=dict(data.get("failure_mode_summary") or {}),
            summary_mode_requested=data.get("summary_mode_requested", "rule_based"),
            summary_mode_used=data.get("summary_mode_used", "rule_based"),
            summary_version=data.get("summary_version", "legacy"),
            semantic_summary=dict(data.get("semantic_summary") or {}),
            summary_error=data.get("summary_error"),
            human_disagreement_profile=dict(data.get("human_disagreement_profile") or {}),
        )


def _top_tendencies(failure_mode_summary: dict[str, int], k: int) -> list[str]:
    """The ``k`` most-cited failure modes as tendency phrases, most frequent first
    (ties broken by key for determinism). Unknown keys are skipped."""
    ranked = sorted(
        ((key, n) for key, n in failure_mode_summary.items() if key in _TENDENCY),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return [_TENDENCY[key] for key, _n in ranked[:k]]


def render_optimized_prompt_addendum(verdict: DebateVerdict) -> str:
    """Deterministically retain safe semantic rules and observable debate evidence."""
    summary = rule_based_summary(
        verdict.transcript, verdict.failure_mode_summary, _TENDENCY,
    )
    return render_summary(summary)


def render_corpus_calibration_prompt(results: Iterable[dict[str, Any]]) -> str:
    """One item-independent calibration note distilling the failure modes that recur
    *across* a run's calibrated items — the generalizing artifact, meant to be applied to
    unseen items (not the item that produced it).

    Reads ``failure_mode_summary`` (recurring judge error modes) and ``score_delta``
    (directional bias) off each per-item result dict — the shape in a node's
    ``calibration_results`` output or a reloaded checkpoint. Deterministic; returns ``""``
    when there's nothing generalizable (no results, or no flagged modes and no consistent
    bias).
    """
    results = list(results)
    if not results:
        return ""

    totals: dict[str, int] = {}
    deltas: list[float] = []
    for r in results:
        for key, n in (r.get("failure_mode_summary") or {}).items():
            if key in _TENDENCY and isinstance(n, int):
                totals[key] = totals.get(key, 0) + n
        d = r.get("score_delta")
        if isinstance(d, (int, float)) and not isinstance(d, bool):
            deltas.append(float(d))

    tendencies = _top_tendencies(totals, k=3)
    mean_delta = mean(deltas) if deltas else 0.0
    # Magnitude, not just direction: a bare "you under-score" makes the judge correct
    # upward with no sense of how far, which overshot in leave-one-out CV (a 2/5 item the
    # judge should have scored ~3 jumped to 5). The mean signed delta *is* the average
    # correction the review applied, so stating it (~N points) gives the re-judge a
    # target size, not just a sign.
    mag = abs(mean_delta)
    if mean_delta > 0.05:
        direction = f"tended to under-score by roughly {mag:.1f} point(s) (review raised its scores)"
    elif mean_delta < -0.05:
        direction = f"tended to over-score by roughly {mag:.1f} point(s) (review lowered its scores)"
    else:
        direction = ""

    if not tendencies and not direction:
        return ""

    n = len(results)
    sentences = [
        f"Calibration note from {n} adversarially-reviewed item"
        f"{'s' if n != 1 else ''}:"
    ]
    if tendencies:
        sentences[0] += " this judge's recurring tendencies are to " + "; to ".join(tendencies) + "."
    else:
        sentences[0] += " no systematic judge failure modes were flagged."
    if direction:
        sentences.append(f"Overall it {direction}.")
    sentences.append("Weigh these tendencies when assigning a score.")
    return " ".join(sentences)


def to_calibrated_result(verdict: DebateVerdict) -> CalibratedResult:
    semantic = rule_based_summary(
        verdict.transcript, verdict.failure_mode_summary, _TENDENCY,
    )
    return CalibratedResult(
        item_id=verdict.item_id,
        metric_id=verdict.metric_id,
        original_score=verdict.initial_score,
        final_score=verdict.final_score,
        score_delta=verdict.score_delta,
        converged=verdict.converged,
        rounds_run=verdict.rounds_run,
        flags=list(verdict.flags),
        optimized_prompt=render_summary(semantic),
        reasoning=verdict.reasoning_trace,
        transcript=verdict.transcript,
        grounded=verdict.grounded,
        failure_mode_summary=dict(verdict.failure_mode_summary),
        semantic_summary=semantic.to_dict(),
        human_disagreement_profile=dict(verdict.human_disagreement_profile),
    )
