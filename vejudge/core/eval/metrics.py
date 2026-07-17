"""Agreement metrics between judge scores and human labels.

All functions tolerate short / degenerate inputs by returning ``None`` rather than
raising, so a sparse benchmark (few matched items per dimension) still produces a
report. Use :func:`by_category` to break any metric down by a grouping key.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

Number = float


def _clean_pairs(
    x: Sequence[float], y: Sequence[float]
) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for a, b in zip(x, y):
        if a is None or b is None:
            continue
        try:
            xs.append(float(a))
            ys.append(float(b))
        except (TypeError, ValueError):
            continue
    return xs, ys


def spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    xs, ys = _clean_pairs(x, y)
    if len(xs) < 3:
        return None
    try:
        from scipy.stats import spearmanr

        r, _ = spearmanr(xs, ys)
        return None if (r is None or math.isnan(r)) else float(r)
    except ImportError:
        return _rank_corr(xs, ys)


def pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """PLCC — linear correlation. Reported alongside SRCC for video-quality-assessment
    comparability (VE-Bench and most VQA papers report both)."""
    xs, ys = _clean_pairs(x, y)
    if len(xs) < 3:
        return None
    try:
        from scipy.stats import pearsonr

        r, _ = pearsonr(xs, ys)
        return None if (r is None or math.isnan(r)) else float(r)
    except ImportError:
        # Plain covariance/std fallback if scipy is absent.
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        vx = sum((a - mx) ** 2 for a in xs)
        vy = sum((b - my) ** 2 for b in ys)
        denom = (vx * vy) ** 0.5
        return None if denom == 0 else cov / denom


def kendall(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    xs, ys = _clean_pairs(x, y)
    if len(xs) < 3:
        return None
    try:
        from scipy.stats import kendalltau

        t, _ = kendalltau(xs, ys)
        return None if (t is None or math.isnan(t)) else float(t)
    except ImportError:
        return None


def mae(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    xs, ys = _clean_pairs(x, y)
    if not xs:
        return None
    return sum(abs(a - b) for a, b in zip(xs, ys)) / len(xs)


def quadratic_weighted_kappa(
    x: Sequence[float], y: Sequence[float], *, lo: int = 1, hi: int = 5
) -> Optional[float]:
    """QWK over integer-rounded scores in [lo, hi]."""
    xs, ys = _clean_pairs(x, y)
    if len(xs) < 2:
        return None
    n_cls = hi - lo + 1

    def idx(v: float) -> int:
        return min(hi, max(lo, int(round(v)))) - lo

    O = [[0] * n_cls for _ in range(n_cls)]
    for a, b in zip(xs, ys):
        O[idx(a)][idx(b)] += 1

    row = [sum(O[i]) for i in range(n_cls)]
    col = [sum(O[i][j] for i in range(n_cls)) for j in range(n_cls)]
    total = len(xs)

    num = den = 0.0
    for i in range(n_cls):
        for j in range(n_cls):
            w = ((i - j) ** 2) / ((n_cls - 1) ** 2)
            e = row[i] * col[j] / total
            num += w * O[i][j]
            den += w * e
    if den == 0:
        return None
    return 1.0 - num / den


def _rank_corr(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson correlation of ranks (Spearman fallback without scipy)."""

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


@dataclass
class PairResult:
    """One pairwise-preference comparison outcome."""

    judge_prefers: int  # the slot the judge scored higher
    human_prefers: int  # the slot the human ranked first
    agree: bool


def pairwise_accuracy(pairs: Sequence[PairResult]) -> Optional[float]:
    if not pairs:
        return None
    return sum(1 for p in pairs if p.agree) / len(pairs)


def by_category(
    rows: Sequence[dict],
    *,
    category_key: str,
    metric_fn: Callable[[list[float], list[float]], Optional[float]],
    x_key: str,
    y_key: str,
) -> dict[str, Optional[float]]:
    """Group rows by ``category_key`` and apply ``metric_fn`` to each group."""
    groups: dict[str, tuple[list[float], list[float]]] = {}
    for r in rows:
        cat = str(r.get(category_key))
        xs, ys = groups.setdefault(cat, ([], []))
        xs.append(r.get(x_key))
        ys.append(r.get(y_key))
    return {cat: metric_fn(xs, ys) for cat, (xs, ys) in groups.items()}
