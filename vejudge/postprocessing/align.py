"""Crosswalk: map judge metric outputs onto the human annotation dimensions.

Each human dimension is paired with the judge signal that most directly measures it
(see docs/research.md and EVAL_PLAN.md). ``judge_signal_for_dimension`` pulls the 1-5
value out of a judge-results dict; ``derive_overall`` builds the pairwise signal.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..core.rubric.definitions import JUDGE_METRICS
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


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def score_at_path(parsed: dict[str, Any], score_path: str) -> Optional[float]:
    """Walk a dotted ``score_path`` to a numeric 1-5 score — generalizes ``_top_score``/
    ``_sub_score`` for **custom** judge specs (which declare their own path). The path may
    point at the number directly (``"score_1_to_5"``) or at a sub-dict that contains it
    (``"voiceover_visual_match"`` or ``"voiceover_visual_match.score_1_to_5"``).
    """
    cur: Any = parsed
    for part in score_path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict):
        cur = cur.get("score_1_to_5")
    return _num(cur)


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

# Splits ALIGNMENT's dimensions by modality, derived from each dimension's metric_id's own
# `JUDGE_METRICS[metric_id].modality` (core/rubric/definitions.py) rather than a second
# hardcoded copy of the M1/M3 vs M2/M4/M5/M6 split — used by the Eval Text/Eval Video node
# executors to each compute only their own modality's dimensions.
TEXT_DIMENSIONS: frozenset[str] = frozenset(
    dim for dim, (metric_id, _extractor) in ALIGNMENT.items()
    if JUDGE_METRICS[metric_id].modality == "text"
)
VIDEO_DIMENSIONS: frozenset[str] = frozenset(
    dim for dim, (metric_id, _extractor) in ALIGNMENT.items()
    if JUDGE_METRICS[metric_id].modality == "video"
)

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


def _custom_entry_for_dimension(
    judge_results: dict[str, Any], dimension: str
) -> Optional[dict[str, Any]]:
    """A custom judge spec's result entry targeting ``dimension`` (carries its own
    ``align: {dimension, score_path}``), or None. Builtin metrics use ``ALIGNMENT`` instead.
    """
    for entry in judge_results.values():
        if not isinstance(entry, dict):
            continue
        align = entry.get("align")
        if isinstance(align, dict) and align.get("dimension") == dimension:
            return entry
    return None


def judge_signal_for_dimension(
    judge_results: dict[str, Any], dimension: str
) -> Optional[float]:
    """Return the judge's 1-5 value aligned to ``dimension`` (None if unavailable).

    Builtin metrics resolve via the ``ALIGNMENT`` crosswalk; a **custom** judge spec's
    result entry carries its own ``align: {dimension, score_path}`` and is used when no
    builtin metric present covers this dimension.
    """
    if dimension in ALIGNMENT:
        metric_id, extractor = ALIGNMENT[dimension]
        parsed = _parsed(judge_results, metric_id)
        if parsed is not None:
            return extractor(parsed)
    entry = _custom_entry_for_dimension(judge_results, dimension)
    if entry is not None:
        parsed = entry.get("parsed")
        score_path = (entry.get("align") or {}).get("score_path")
        if isinstance(parsed, dict) and score_path:
            return score_at_path(parsed, score_path)
    return None


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


def diagnose_missing_rows(
    items: list[str],
    human: dict[str, Any],
    per_item_judges: dict[str, dict[str, Any]],
    *,
    sample_size: int = 20,
    dimensions: Optional[frozenset[str]] = None,
) -> list[dict[str, Any]]:
    """Explain why (item, dimension) pairs failed to produce an aligned row.

    ``build_aligned_rows`` silently ``continue``s past several distinct causes (missing
    human score, the judge metric never having run at all, an invalid/skipped judge
    result, or a parsed result with no numeric score at the expected field) — useful for
    a human/live run that overlaps by item id but still yields zero (or unexpectedly few)
    aligned rows, since none of those causes is otherwise visible anywhere. Grouped by
    (dimension, reason) rather than emitted per item, since the same cause typically
    applies to every item at once (e.g. a metric simply wasn't selected on the Judge
    node) — a flat per-item list would just repeat the same line dozens of times.

    ``dimensions`` restricts the diagnosis to a subset of ``HUMAN_DIMENSIONS`` (e.g. the
    Eval Text/Eval Video node split) — ``None`` (the default) covers all of them, matching
    the CLI benchmark's unified gap report.
    """
    counts: dict[tuple[str, str], dict[str, Any]] = {}

    def _record(dim: str, reason: str, item_id: str) -> None:
        key = (dim, reason)
        entry = counts.setdefault(
            key, {"dimension": dim, "reason": reason, "count": 0, "example_item_ids": []}
        )
        entry["count"] += 1
        if len(entry["example_item_ids"]) < 3:
            entry["example_item_ids"].append(item_id)

    dims = dimensions if dimensions is not None else HUMAN_DIMENSIONS
    for item_id in items[:sample_size]:
        agg = human.get(item_id)
        if agg is None:
            continue
        judge_results = per_item_judges.get(item_id, {})
        for dim in dims:
            if dim not in ALIGNMENT:
                _record(dim, "dimension has no ALIGNMENT crosswalk entry", item_id)
                continue
            metric_id, extractor = ALIGNMENT[dim]
            if agg.scores.get(dim) is None:
                _record(dim, "no human score for this dimension on this item", item_id)
                continue
            res = judge_results.get(metric_id)
            if res is None:
                _record(
                    dim,
                    f"judge metric {metric_id} was never produced for this item (not "
                    "selected on the Judge node, or the item was skipped)",
                    item_id,
                )
                continue
            parsed = res.get("parsed")
            if not isinstance(parsed, dict):
                status = "skipped" if res.get("skipped") else (res.get("error") or "invalid/unparsed")
                _record(
                    dim, f"judge metric {metric_id} has no valid parsed output ({status})", item_id
                )
                continue
            if extractor(parsed) is None:
                _record(
                    dim,
                    f"judge metric {metric_id}'s parsed output has no numeric score at "
                    "the expected field for this dimension",
                    item_id,
                )

    return sorted(counts.values(), key=lambda e: -e["count"])


def build_aligned_rows(
    items: list[str],
    human: dict[str, Any],
    per_item_judges: dict[str, dict[str, Any]],
    *,
    dimensions: Optional[frozenset[str]] = None,
) -> list[dict[str, Any]]:
    """Pair human scores with aligned judge signals, one row per (item, dimension).

    Shared by the CLI benchmark (``benchmark/human_gap/runner.py``) and the interface's
    Eval Text/Eval Video node executors, so all compute the human-vs-judge gap the same
    way. ``dimensions`` restricts the output to a subset of ``HUMAN_DIMENSIONS`` (e.g. one
    modality's dimensions) — ``None`` (the default) covers all of them, matching the CLI
    benchmark's unified gap report.
    """
    dims = dimensions if dimensions is not None else HUMAN_DIMENSIONS
    rows: list[dict[str, Any]] = []
    for item_id in items:
        agg = human[item_id]
        judge_results = per_item_judges.get(item_id, {})
        for dim in dims:
            # No `dim in ALIGNMENT` guard: `judge_signal_for_dimension` returns None for a
            # dimension with neither a builtin crosswalk entry nor a custom judge targeting
            # it, which the None check below already skips — so custom target dimensions
            # (not in ALIGNMENT) still produce rows.
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
