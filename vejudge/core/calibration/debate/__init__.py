"""Adversarial calibration: a bounded judge-vs-human-proxy debate over one (item,
metric) pair, refining a prior ``Judge.run()`` score into a ``DebateVerdict`` with a
distilled reasoning trace. See docs/research.md for the failure-mode taxonomy and
CLAUDE.md's Calibration conventions for how this relates to ``Calibrator``.
"""

from .calibrated_result import (
    CalibratedResult,
    render_corpus_calibration_prompt,
    render_optimized_prompt_addendum,
    to_calibrated_result,
)
from .registry import DEBATE_METRICS, debate_prompt_versions, make_debate
from .retrieval import RetrievedNote, find_similar_human_note
from .runner import DebateConfig, DebateRunner, DebateTurnRunner
from .schema import (
    DebateTranscript,
    DebateTurn,
    DebateVerdict,
    FAILURE_MODE_TAXONOMY,
    extract_original_score,
    normalize_failure_modes,
    render_reasoning_trace,
)

__all__ = [
    "DEBATE_METRICS",
    "CalibratedResult",
    "DebateConfig",
    "DebateRunner",
    "DebateTranscript",
    "DebateTurn",
    "DebateTurnRunner",
    "DebateVerdict",
    "FAILURE_MODE_TAXONOMY",
    "RetrievedNote",
    "debate_prompt_versions",
    "extract_original_score",
    "find_similar_human_note",
    "make_debate",
    "normalize_failure_modes",
    "render_corpus_calibration_prompt",
    "render_optimized_prompt_addendum",
    "render_reasoning_trace",
    "to_calibrated_result",
]
