"""Aggregate multi-annotator records into one row per (project, prompt_idx, model).

Per-dimension score = mean of available numeric (1-5) annotator scores (empty strings
dropped). Pairwise preferences are derived from ``overall_ranking`` vs ``output_slot``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable, Optional

from .loader import HumanAnnotationRecord

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
    scores: dict[str, Optional[float]] = field(default_factory=dict)
    score_counts: dict[str, int] = field(default_factory=dict)
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
) -> dict[str, AggregatedHumanRecord]:
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
        )
        for dim in HUMAN_DIMENSIONS:
            vals = [
                v
                for r in recs
                if (v := _num(r.annotation.get(dim))) is not None
            ]
            agg.scores[dim] = mean(vals) if vals else None
            agg.score_counts[dim] = len(vals)

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
