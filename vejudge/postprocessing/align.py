"""Crosswalk: map judge metric outputs onto the human annotation dimensions.

Each human dimension is paired with the judge signal that most directly measures it
(see docs/research.md and EVAL_PLAN.md). ``judge_signal_for_dimension`` pulls the 1-5
value out of a judge-results dict; ``derive_overall`` builds the pairwise signal.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..database.dl_human_annotations import HUMAN_DIMENSIONS

# human dimension -> (metric_id, extractor over that metric's parsed dict)
JudgeExtractor = Callable[[dict[str, Any]], Optional[float]]


def _top_score(parsed: dict[str, Any]) -> Optional[float]:
    v = parsed.get("score_1_to_5")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sub_score(key: str) -> JudgeExtractor:
    def extract(parsed: dict[str, Any]) -> Optional[float]:
        sub = parsed.get(key) or {}
        v = sub.get("score_1_to_5") if isinstance(sub, dict) else None
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    return extract


ALIGNMENT: dict[str, tuple[str, JudgeExtractor]] = {
    "video_addresses_prompt": ("M3", _top_score),
    "voiceover_matches_visuals": ("M6", _sub_score("voiceover_visual_match")),
    "abrupt_cutoffs_voiceover": ("M6", _sub_score("voiceover_continuity")),
    "abrupt_cutoffs_video": ("M6", _sub_score("visual_continuity")),
    "story_flow_voiceover": ("M5", _top_score),
    "story_flow_visuals": ("M5", _top_score),
    "section_placement_opening": ("M5", _top_score),
    "section_placement_middle": ("M5", _top_score),
    "section_placement_closing": ("M5", _top_score),
}

JUDGE_SIGNAL_LABEL: dict[str, str] = {
    "video_addresses_prompt": "M3.score_1_to_5",
    "voiceover_matches_visuals": "M6a.voiceover_visual_match",
    "abrupt_cutoffs_voiceover": "M6b.voiceover_continuity",
    "abrupt_cutoffs_video": "M6c.visual_continuity",
    "story_flow_voiceover": "M5.score_1_to_5",
    "story_flow_visuals": "M5.score_1_to_5",
    "section_placement_opening": "M5.score_1_to_5",
    "section_placement_middle": "M5.score_1_to_5",
    "section_placement_closing": "M5.score_1_to_5",
}


def _parsed(judge_results: dict[str, Any], metric_id: str) -> Optional[dict[str, Any]]:
    res = judge_results.get(metric_id) or {}
    parsed = res.get("parsed")
    return parsed if isinstance(parsed, dict) else None


def judge_signal_for_dimension(
    judge_results: dict[str, Any], dimension: str
) -> Optional[float]:
    """Return the judge's 1-5 value aligned to ``dimension`` (None if unavailable)."""
    if dimension not in ALIGNMENT:
        return None
    metric_id, extractor = ALIGNMENT[dimension]
    parsed = _parsed(judge_results, metric_id)
    return extractor(parsed) if parsed else None


def derive_overall(judge_results: dict[str, Any]) -> Optional[float]:
    """Mean of available quality scores (M3, M4, M5 top scores + M6 overall)."""
    vals: list[float] = []
    for mid in ("M3", "M4", "M5"):
        parsed = _parsed(judge_results, mid)
        if parsed:
            v = _top_score(parsed)
            if v is not None:
                vals.append(v)
    m6 = _parsed(judge_results, "M6")
    if m6:
        ov = m6.get("overall_av_sync_score")
        if isinstance(ov, (int, float)) and not isinstance(ov, bool):
            vals.append(float(ov))
    return sum(vals) / len(vals) if vals else None


def build_aligned_rows(
    items: list[str],
    human: dict[str, Any],
    per_item_judges: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair human scores with aligned judge signals, one row per (item, dimension).

    Shared by the CLI benchmark (``benchmark/human_gap/runner.py``) and the interface's
    Eval Node executor, so both compute the human-vs-judge gap the same way.
    """
    rows: list[dict[str, Any]] = []
    for item_id in items:
        agg = human[item_id]
        judge_results = per_item_judges.get(item_id, {})
        for dim in HUMAN_DIMENSIONS:
            if dim not in ALIGNMENT:
                continue
            human_score = agg.scores.get(dim)
            judge_score = judge_signal_for_dimension(judge_results, dim)
            if human_score is None or judge_score is None:
                continue
            rows.append(
                {
                    "item_id": item_id,
                    "project": agg.project,
                    "model": agg.model,
                    "use_case": agg.use_case,
                    "dimension": dim,
                    "human": human_score,
                    "judge_raw": judge_score,
                }
            )
    return rows
