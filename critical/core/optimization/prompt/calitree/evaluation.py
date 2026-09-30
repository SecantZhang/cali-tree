"""Shared deterministic sampling and evaluation helpers."""

from typing import Any

from .metrics import LABELS


def balanced_case_subset(
    ids: list[str], targets: dict[str, str], limit: int
) -> list[str]:
    if limit <= 0 or len(ids) <= limit:
        return sorted(ids)
    groups: dict[str, list[str]] = {}
    for item_id in sorted(ids):
        groups.setdefault(targets[item_id], []).append(item_id)
    selected: list[str] = []
    offsets = {label: 0 for label in groups}
    labels = sorted(groups)
    while len(selected) < limit:
        progressed = False
        for label in labels:
            offset = offsets[label]
            if offset >= len(groups[label]):
                continue
            selected.append(groups[label][offset])
            offsets[label] += 1
            progressed = True
            if len(selected) == limit:
                break
        if not progressed:
            break
    return sorted(selected)


def balanced_accuracy(
    ids: list[str],
    targets: dict[str, str],
    results: dict[str, dict[str, Any]],
) -> float:
    scores: list[float] = []
    for label in LABELS:
        label_ids = [item_id for item_id in ids if targets[item_id] == label]
        if label_ids:
            scores.append(
                sum(results[item_id].get("label") == label for item_id in label_ids)
                / len(label_ids)
            )
    return sum(scores) / len(scores) if scores else 0.0


def behavior_profile(
    ids: list[str],
    targets: dict[str, str],
    results: dict[str, dict[str, Any]],
) -> list[float]:
    """Return a label-confusion fingerprint for a prompt on a fixed probe set.

    A profile has one coordinate per target/prediction pair.  Comparing profiles on
    the same examples makes leaves with the same *decision behavior* close even when
    their generated prompt text happens to look unrelated.
    """
    profile = [0.0] * (len(LABELS) * len(LABELS))
    label_index = {label: index for index, label in enumerate(LABELS)}
    for item_id in ids:
        target = targets.get(item_id)
        prediction = (results.get(item_id) or {}).get("label")
        if target in label_index and prediction in label_index:
            profile[
                label_index[target] * len(LABELS) + label_index[prediction]
            ] += 1.0
    total = sum(profile)
    return [value / total for value in profile] if total else profile
