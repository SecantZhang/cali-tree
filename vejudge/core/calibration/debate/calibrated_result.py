"""``CalibratedResult`` — the per-item artifact a ``cl_adversarial`` interface node
produces: a ``DebateVerdict`` plus a concise, injectable ``optimized_prompt`` a
downstream ``Judge.run(..., extra_context=...)`` call can use to re-score *this same
item* with the debate's own feedback in view.

Two levels of calibration text, both deterministic (no extra LM call):

- **Per-item** (``render_optimized_prompt_addendum``): a *distilled* lesson — the score
  correction, the judge failure-mode tendencies the debate flagged (from the fixed
  ``FAILURE_MODE_TAXONOMY``), and at most one short guidance clause. Deliberately NOT the
  full round-by-round transcript: that lives in ``reasoning`` for display only, and
  dumping it verbatim into a judge prompt produced 300–2400-word addenda that overfit to
  one item and swamped the base prompt. The distilled form is bounded (~40-50 words) no
  matter how many rounds ran.
- **Corpus** (``render_corpus_calibration_prompt``): the deferred "aggregation" — one
  *item-independent* prompt distilling the failure modes that recur *across* a whole run
  into a short, transferable calibration note, meant to be applied to unseen items. This
  is the generalizing artifact; the fixed taxonomy vocabulary is what lets it generalize
  instead of replaying any single item's narrative.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Iterable, Optional

from ...prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from .schema import DebateTranscript, DebateVerdict

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

# Guidance clauses longer than this (in words) are truncated — the one item-specific,
# free-text part of the per-item lesson, capped so it can't reintroduce the wordiness
# the distillation exists to remove.
_GUIDANCE_MAX_WORDS = 26


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
        )


def _first_sentence(text: str, max_words: int = _GUIDANCE_MAX_WORDS) -> str:
    """First sentence of ``text``, truncated to ``max_words`` (with an ellipsis)."""
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    words = sentence.split()
    if len(words) <= max_words:
        return sentence
    return " ".join(words[:max_words]) + "…"


def _top_tendencies(failure_mode_summary: dict[str, int], k: int) -> list[str]:
    """The ``k`` most-cited failure modes as tendency phrases, most frequent first
    (ties broken by key for determinism). Unknown keys are skipped."""
    ranked = sorted(
        ((key, n) for key, n in failure_mode_summary.items() if key in _TENDENCY),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return [_TENDENCY[key] for key, _n in ranked[:k]]


def render_optimized_prompt_addendum(verdict: DebateVerdict) -> str:
    """A concise, injectable calibration lesson for re-judging *this same item*.

    Deterministic (no extra LM call). Bounded in length regardless of round count: a
    score-correction header, the debate's flagged judge tendencies (fixed taxonomy
    vocabulary), and at most one capped guidance clause — not the full transcript, which
    stays in ``reasoning`` for display only.
    """
    if verdict.final_score is None or verdict.initial_score is None:
        header = (
            "A prior adversarial review could not settle on a revised score; weigh this "
            "item's score with extra scrutiny."
        )
    elif verdict.score_delta is not None and abs(verdict.score_delta) < 1e-9:
        header = f"A prior adversarial review confirmed the score of {verdict.final_score:g}."
    else:
        header = (
            f"A prior adversarial review adjusted the score "
            f"{verdict.initial_score:g}→{verdict.final_score:g}."
        )

    parts = [header]

    tendencies = _top_tendencies(verdict.failure_mode_summary, k=2)
    if tendencies:
        parts.append("It flagged this judge's tendency to " + "; to ".join(tendencies) + ".")

    # One decisive, capped guidance clause: the last human-proxy critique's lead line
    # (the correction signal the fresh judge should weigh). The only free-text, item-
    # specific part — capped by _first_sentence so it can't reintroduce the wordiness.
    proxy = verdict.transcript.last("human_proxy")
    if proxy is not None and proxy.parsed:
        lines = proxy.parsed.get("reasoning_lines") or []
        if lines:
            clause = _first_sentence(str(lines[0]))
            if clause:
                parts.append(f"Key point: {clause}")

    return " ".join(parts)


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
    if mean_delta > 0.05:
        direction = "tended to under-score (review raised its scores)"
    elif mean_delta < -0.05:
        direction = "tended to over-score (review lowered its scores)"
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
        failure_mode_summary=dict(verdict.failure_mode_summary),
    )
