"""Inter-rater agreement — the human ceiling for judge calibration.

A judge's MAE against the human anchor is only meaningful relative to how much the humans
disagree with each other: an item scored 2/4/5 by three raters has a ~1.3-point human
spread, so a judge within ~1 point of the mean is already at the noise floor. This computes,
per dimension, how far raters sit from their own item mean — the yardstick to report the
judge's MAE against.

Operates on the per-rater values kept in ``AggregatedHumanRecord.raw_scores`` (see
``dl_human_annotations.aggregate``); items with fewer than 2 raters on a dimension carry no
disagreement signal and are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import mean
from typing import Iterable, Optional


@dataclass
class RaterAgreement:
    dimension: str
    n_items: int          # items with >= 2 raters on this dimension
    n_ratings: int        # total individual ratings counted
    self_mae: Optional[float]      # mean |rater - item_mean| — the "ceiling" for anchor MAE
    pairwise_mae: Optional[float]  # mean |rater_i - rater_j| over rater pairs within an item


def _item_self_devs(vals: list[float]) -> list[float]:
    m = mean(vals)
    return [abs(v - m) for v in vals]


def _item_pairwise_devs(vals: list[float]) -> list[float]:
    return [abs(a - b) for a, b in combinations(vals, 2)]


def inter_rater_agreement(
    raw_scores_per_item: Iterable[dict[str, list[float]]],
    *,
    dimensions: Optional[Iterable[str]] = None,
) -> dict[str, RaterAgreement]:
    """Per-dimension inter-rater agreement over a collection of items' ``raw_scores`` maps.

    ``raw_scores_per_item`` is an iterable of ``{dimension: [rater values]}`` (one per item —
    e.g. ``[rec.raw_scores for rec in aggregated.values()]``). Returns one ``RaterAgreement``
    per dimension that had at least one multi-rater item.
    """
    items = list(raw_scores_per_item)
    dims = list(dimensions) if dimensions is not None else sorted(
        {d for it in items for d in it}
    )

    out: dict[str, RaterAgreement] = {}
    for dim in dims:
        self_devs: list[float] = []
        pair_devs: list[float] = []
        n_items = 0
        n_ratings = 0
        for it in items:
            vals = [float(v) for v in it.get(dim, [])]
            if len(vals) < 2:
                continue
            n_items += 1
            n_ratings += len(vals)
            self_devs.extend(_item_self_devs(vals))
            pair_devs.extend(_item_pairwise_devs(vals))
        if n_items == 0:
            continue
        out[dim] = RaterAgreement(
            dimension=dim,
            n_items=n_items,
            n_ratings=n_ratings,
            self_mae=round(mean(self_devs), 4) if self_devs else None,
            pairwise_mae=round(mean(pair_devs), 4) if pair_devs else None,
        )
    return out
