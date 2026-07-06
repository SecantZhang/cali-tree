"""Deterministic item sampling for the Dataset Node (ratio + mode, per interface.md).

Pure functions, no I/O — the executor resolves item ids and use_case lookups first.
"""

from __future__ import annotations

from typing import Optional

VALID_MODES = {"full", "unified", "stratified"}


def _evenly_spaced_indices(n: int, k: int) -> list[int]:
    """``k`` distinct, strictly increasing indices into ``range(n)``, evenly spaced."""
    if n <= 0 or k <= 0:
        return []
    k = min(k, n)
    return [(i * n) // k for i in range(k)]


def _target_count(n: int, ratio: float) -> int:
    if n <= 0:
        return 0
    ratio = max(0.0, min(1.0, ratio))
    if ratio <= 0.0:
        return 0
    return max(1, round(n * ratio))


def _proportional_allocation(group_sizes: list[int], total: int) -> list[int]:
    """Largest-remainder allocation of ``total`` across groups, capped at each group's size."""
    n = sum(group_sizes)
    if n == 0 or total <= 0:
        return [0] * len(group_sizes)
    total = min(total, n)
    raw = [total * g / n for g in group_sizes]
    base = [int(r) for r in raw]
    remainder = total - sum(base)
    order = sorted(range(len(group_sizes)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:remainder]:
        base[i] += 1
    return [min(b, g) for b, g in zip(base, group_sizes)]


def select_items(
    items: list[str],
    *,
    ratio: float = 1.0,
    mode: str = "full",
    use_case_lookup: Optional[dict[str, str]] = None,
) -> list[str]:
    """Deterministically pick a subset of ``items`` per sampling mode and ratio.

    - ``"full"``: ignore ``ratio``, return every item.
    - ``"unified"``: evenly-spaced selection across the sorted item list.
    - ``"stratified"``: group by ``use_case_lookup`` (item id -> use_case, missing ->
      ``"unknown"``), allocate the ratio-derived target count proportionally across
      groups, then evenly-spaced selection within each group.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown sampling mode '{mode}'. Options: {sorted(VALID_MODES)}")

    ordered = sorted(items)
    if mode == "full":
        return ordered

    target = _target_count(len(ordered), ratio)
    if target == 0:
        return []

    if mode == "unified":
        idx = _evenly_spaced_indices(len(ordered), target)
        return [ordered[i] for i in idx]

    # stratified
    lookup = use_case_lookup or {}
    groups: dict[str, list[str]] = {}
    for item in ordered:
        groups.setdefault(lookup.get(item, "unknown"), []).append(item)
    group_keys = sorted(groups)
    quotas = _proportional_allocation([len(groups[k]) for k in group_keys], target)

    selected: list[str] = []
    for key, quota in zip(group_keys, quotas):
        group_items = groups[key]
        idx = _evenly_spaced_indices(len(group_items), quota)
        selected.extend(group_items[i] for i in idx)
    return sorted(selected)
