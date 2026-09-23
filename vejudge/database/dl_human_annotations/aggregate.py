"""Aggregate multi-annotator records into one row per (project, prompt_idx, model).

Per-dimension score = mean of available numeric (1-5) annotator scores (empty strings
dropped). Pairwise preferences are derived from ``overall_ranking`` vs ``output_slot``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any, Iterable, Optional

from .loader import HumanAnnotationRecord

# Point-estimate reducers for collapsing a dimension's per-rater scores into one number. `none`
# is handled separately (no reduction — `scores[dim]` stays None, `raw_scores` carries the
# individual ratings). max/min are offered per the interface dropdown; mean is the default.
_REDUCERS = {"mean": mean, "median": median, "max": max, "min": min}
AGGREGATION_METHODS: list[str] = [*_REDUCERS, "none"]


def _reduce(vals: list[float], method: str) -> Optional[float]:
    """Collapse a dimension's rater values by `method`; `none` (or empty) yields no estimate."""
    if not vals or method == "none":
        return None
    reducer = _REDUCERS.get(method, mean)
    return float(reducer(vals))

# The 9 scored human dimensions (1-5). Emotion / free-text fields are excluded.
HUMAN_DIMENSIONS: list[str] = [
    "voiceover_matches_visuals",
    "abrupt_cutoffs_voiceover",
    "abrupt_cutoffs_video",
    "story_flow_voiceover",
    "story_flow_visuals",
    "section_placement_opening",
    "section_placement_middle",
    "section_placement_closing",
    "video_addresses_prompt",
    # Public text-driven video-editing quality (VE-Bench MOS; its own scale, not 1-5) — a
    # separate calibration track from the peanut assembly dimensions above.
    "edit_quality",
]


@dataclass
class AggregatedHumanRecord:
    item_id: str
    project: str
    prompt_idx: int
    model: str
    use_case: str = "unknown"
    n_annotators: int = 0
    n_complete: int = 0
    # How `scores` was reduced from `raw_scores`: mean (default) / median / max / min, or
    # "none" — no reduction, `scores[dim]` is None and consumers read `raw_scores` per rater.
    aggregation: str = "mean"
    scores: dict[str, Optional[float]] = field(default_factory=dict)
    score_counts: dict[str, int] = field(default_factory=dict)
    # Per-rater numeric scores kept alongside the mean (`scores`) + count (`score_counts`),
    # so the individual raters aren't discarded on aggregation. Used to measure inter-rater
    # agreement (the human ceiling) — see core.eval.rater_agreement. `scores[dim]` stays the
    # mean of `raw_scores[dim]`; nothing that reads `scores` is affected.
    raw_scores: dict[str, list[float]] = field(default_factory=dict)
    pairwise: list[dict[str, Any]] = field(default_factory=list)


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def aggregate_annotations(
    records: Iterable[HumanAnnotationRecord],
    *,
    use_case_lookup: Optional[dict[str, str]] = None,
    method: str = "mean",
) -> dict[str, AggregatedHumanRecord]:
    """Collapse per-rater annotations into one record per (project, prompt_idx, model).

    `method` picks the per-dimension point estimate written to `scores` (mean/median/max/min);
    `none` leaves `scores[dim]` as None and only carries the individual ratings in `raw_scores`.
    `raw_scores` / `score_counts` / annotator counts are the same regardless of `method`.
    """
    use_case_lookup = use_case_lookup or {}
    grouped: dict[str, list[HumanAnnotationRecord]] = {}
    for r in records:
        grouped.setdefault(r.item_id, []).append(r)

    out: dict[str, AggregatedHumanRecord] = {}
    for item_id, recs in grouped.items():
        first = recs[0]
        agg = AggregatedHumanRecord(
            item_id=item_id,
            project=first.project,
            prompt_idx=first.prompt_idx,
            model=first.model,
            use_case=use_case_lookup.get(first.project, "unknown"),
            n_annotators=len(recs),
            n_complete=sum(1 for r in recs if r.complete),
            aggregation=method,
        )
        for dim in HUMAN_DIMENSIONS:
            vals = [
                v
                for r in recs
                if (v := _num(r.annotation.get(dim))) is not None
            ]
            agg.scores[dim] = _reduce(vals, method)
            agg.score_counts[dim] = len(vals)
            if vals:
                agg.raw_scores[dim] = vals

        for r in recs:
            ranking = _num(r.annotation.get("overall_ranking"))
            if ranking is None or r.output_slot is None:
                continue
            agg.pairwise.append(
                {
                    "annotator": r.annotator,
                    "cell_key": r.cell_key,
                    "this_slot": r.output_slot,
                    "preferred_slot": int(ranking),
                    "this_preferred": int(ranking) == r.output_slot,
                }
            )
        out[item_id] = agg
    return out
