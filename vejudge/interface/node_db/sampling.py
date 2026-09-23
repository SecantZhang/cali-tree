"""Deterministic item filtering + sampling, shared by the Dataset and Human Annotations
node executors (ratio + mode, per interface.md).

Pure functions, no I/O — each caller resolves item ids and use_case lookups first.
"""

from __future__ import annotations

import re
from typing import Optional

VALID_MODES = {"unified", "stratified", "split_label_stratified"}


def apply_filters(
    items: list[str],
    *,
    use_case_filter: Optional[list[str]],
    item_id_pattern: Optional[str],
    item_use_case: dict[str, str],
) -> list[str]:
    """Narrows ``items`` by use_case membership and/or an ``item_id`` regex, in that order."""
    out = items
    if use_case_filter:
        allowed = set(use_case_filter)
        out = [i for i in out if item_use_case.get(i) in allowed]
    if item_id_pattern:
        rx = re.compile(item_id_pattern)
        out = [i for i in out if rx.search(i)]
    return out


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


def _balanced_allocation(group_sizes: list[int], total: int) -> list[int]:
    """Allocate as evenly as possible across non-empty groups, respecting capacities."""
    quotas = [0] * len(group_sizes)
    remaining = min(max(0, total), sum(group_sizes))
    while remaining:
        progressed = False
        for index in sorted(range(len(group_sizes)), key=lambda i: (quotas[i], i)):
            if quotas[index] >= group_sizes[index]:
                continue
            quotas[index] += 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            break
    return quotas


def select_split_label_items(
    items: list[str],
    *,
    split_lookup: dict[str, str],
    label_lookup: dict[str, str],
    ratio: float = 1.0,
    count: Optional[int] = None,
    split_ratios: Optional[dict[str, float]] = None,
    group_lookup: Optional[dict[str, str]] = None,
    split_group_offsets: Optional[dict[str, int]] = None,
) -> list[str]:
    """Select a deterministic calibration subset with balanced training labels.

    By default the total train/test allocation follows the source corpus. Callers can
    instead provide independent ``split_ratios`` (for example all official training data
    and 10% of held-out data). When ``group_lookup`` is supplied, ratios are applied to
    groups and every item in a selected group is retained; this prevents editor outputs
    sharing one source image/instruction from being partially sampled.

    In the legacy item-level path, training cases are allocated evenly across labels while
    held-out cases retain source prevalence. Grouped selection preserves whole groups, so
    exact item-level label quotas are intentionally subordinate to leakage safety.
    """
    ordered = sorted(items)
    if split_ratios is not None:
        selected: list[str] = []
        by_split: dict[str, list[str]] = {}
        for item_id in ordered:
            by_split.setdefault(
                split_lookup.get(item_id, "unknown"), []
            ).append(item_id)
        for split in sorted(
            by_split,
            key=lambda value: (
                value != "train", value != "test", value,
            ),
        ):
            split_items = by_split[split]
            split_ratio = float(split_ratios.get(split, ratio))
            if group_lookup:
                groups: dict[str, list[str]] = {}
                for item_id in split_items:
                    groups.setdefault(
                        group_lookup.get(item_id, item_id), []
                    ).append(item_id)
                group_ids = sorted(groups)
                offset = int(
                    (split_group_offsets or {}).get(split, 0)
                ) % len(group_ids)
                rotated_group_ids = (
                    group_ids[offset:] + group_ids[:offset]
                )
                target_groups = _target_count(
                    len(group_ids), split_ratio
                )
                selected_group_ids = [
                    rotated_group_ids[index]
                    for index in _evenly_spaced_indices(
                        len(group_ids), target_groups
                    )
                ]
                for group_id in selected_group_ids:
                    selected.extend(groups[group_id])
            else:
                target_items = _target_count(
                    len(split_items), split_ratio
                )
                selected.extend(
                    split_items[index]
                    for index in _evenly_spaced_indices(
                        len(split_items), target_items
                    )
                )
        return sorted(selected)

    target = (
        max(0, min(int(count), len(ordered)))
        if count is not None
        else _target_count(len(ordered), ratio)
    )
    if target == 0:
        return []

    by_split: dict[str, list[str]] = {}
    for item_id in ordered:
        by_split.setdefault(split_lookup.get(item_id, "unknown"), []).append(item_id)
    split_keys = sorted(by_split, key=lambda value: (value != "train", value != "test", value))
    split_quotas = _proportional_allocation(
        [len(by_split[key]) for key in split_keys], target
    )

    if "train" in by_split and target >= 3:
        train_index = split_keys.index("train")
        train_labels = {
            label_lookup[item_id]
            for item_id in by_split["train"]
            if label_lookup.get(item_id)
        }
        required = min(len(train_labels), len(by_split["train"]), target)
        while split_quotas[train_index] < required:
            donors = [
                index for index, quota in enumerate(split_quotas)
                if index != train_index and quota > 0
            ]
            if not donors:
                break
            donor = max(donors, key=lambda index: (split_quotas[index], -index))
            split_quotas[donor] -= 1
            split_quotas[train_index] += 1

    selected: list[str] = []
    for split, split_quota in zip(split_keys, split_quotas):
        grouped: dict[str, list[str]] = {}
        for item_id in by_split[split]:
            grouped.setdefault(label_lookup.get(item_id, "unknown"), []).append(item_id)
        labels = sorted(grouped)
        sizes = [len(grouped[label]) for label in labels]
        quotas = (
            _balanced_allocation(sizes, split_quota)
            if split == "train"
            else _proportional_allocation(sizes, split_quota)
        )
        for label, quota in zip(labels, quotas):
            group = grouped[label]
            selected.extend(group[index] for index in _evenly_spaced_indices(len(group), quota))
    return sorted(selected)


def select_items(
    items: list[str],
    *,
    ratio: float = 1.0,
    count: Optional[int] = None,
    mode: str = "unified",
    use_case_lookup: Optional[dict[str, str]] = None,
) -> list[str]:
    """Deterministically pick a subset of ``items`` per sampling mode and a size target.

    The size target is either a **fraction** (``ratio`` ∈ [0, 1]) or an **absolute count**
    (``count`` — takes precedence when given, clamped to the available item total). The
    Dataset node maps its single ``sampling_ratio`` field to one of these: a value > 1 is a
    count, ≤ 1 is a ratio (and its "full dataset" toggle forces ``ratio=1.0``).

    - ``"unified"``: evenly-spaced selection across the sorted item list.
    - ``"stratified"``: group by ``use_case_lookup`` (item id -> use_case, missing ->
      ``"unknown"``), allocate the target count proportionally across groups, then
      evenly-spaced selection within each group.
    - ``"split_label_stratified"`` is handled by :func:`select_split_label_items` because
      it needs label metadata in addition to the generic use-case lookup.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown sampling mode '{mode}'. Options: {sorted(VALID_MODES)}")

    ordered = sorted(items)
    if count is not None:
        target = max(0, min(int(count), len(ordered)))
    else:
        target = _target_count(len(ordered), ratio)
    if target == 0:
        return []

    if mode == "unified":
        idx = _evenly_spaced_indices(len(ordered), target)
        return [ordered[i] for i in idx]

    if mode == "split_label_stratified":
        raise ValueError(
            "split_label_stratified requires select_split_label_items with labels"
        )

    # use-case stratified
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
