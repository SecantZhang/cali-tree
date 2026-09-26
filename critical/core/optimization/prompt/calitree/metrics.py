"""CaliTree label vocabulary and classification metrics."""

from __future__ import annotations

from typing import Any, Optional

LABELS = ("no", "partial", "yes")
ORDINAL_VALUE = {"no": 0.0, "partial": 0.5, "yes": 1.0}


def ordinal_absolute_error(target: str, prediction: str) -> Optional[float]:
    """Absolute error on the ``no=0, partial=0.5, yes=1`` ordinal scale.

    Returns ``None`` when either label is outside the ordinal vocabulary so unknown
    predictions do not silently count as a perfect or worst-case distance.
    """
    if target not in ORDINAL_VALUE or prediction not in ORDINAL_VALUE:
        return None
    return abs(ORDINAL_VALUE[target] - ORDINAL_VALUE[prediction])


def classification_metrics(
    targets: dict[str, str], predictions: dict[str, str], samples: dict[str, Any]
) -> dict[str, Any]:
    ids = sorted(targets)
    normalized_predictions = {
        item_id: (
            predictions.get(item_id)
            if predictions.get(item_id) in LABELS
            else "invalid"
        )
        for item_id in ids
    }
    correct = sum(
        targets[item_id] == normalized_predictions[item_id] for item_id in ids
    )
    confusion = {
        label: {pred: 0 for pred in (*LABELS, "invalid")} for label in LABELS
    }
    by_editor: dict[str, dict[str, float]] = {}
    distribution = {label: 0 for label in LABELS}
    abs_errors: list[float] = []
    for item_id in ids:
        target, prediction = targets[item_id], normalized_predictions[item_id]
        if target in confusion and prediction in confusion[target]:
            confusion[target][prediction] += 1
        if prediction in distribution:
            distribution[prediction] += 1
        else:
            distribution["invalid"] = distribution.get("invalid", 0) + 1
        editor = str(samples[item_id].get("editor") or samples[item_id].get("model") or "unknown")
        row = by_editor.setdefault(editor, {"correct": 0, "n": 0, "abs_error_sum": 0.0, "n_ordinal": 0})
        row["n"] += 1
        row["correct"] += int(target == prediction)
        abs_error = ordinal_absolute_error(target, prediction)
        if abs_error is not None:
            abs_errors.append(abs_error)
            row["abs_error_sum"] += abs_error
            row["n_ordinal"] += 1
    per_label_accuracy = {
        label: (
            confusion[label][label] / sum(confusion[label].values())
            if sum(confusion[label].values())
            else None
        )
        for label in LABELS
    }
    per_label_precision = {
        label: (
            confusion[label][label]
            / sum(confusion[target][label] for target in LABELS)
            if sum(confusion[target][label] for target in LABELS)
            else None
        )
        for label in LABELS
    }
    per_label_f1 = {
        label: (
            2 * per_label_precision[label] * per_label_accuracy[label]
            / (per_label_precision[label] + per_label_accuracy[label])
            if per_label_precision[label] is not None
            and per_label_accuracy[label] is not None
            and per_label_precision[label] + per_label_accuracy[label] > 0
            else 0.0
            if per_label_precision[label] is not None
            and per_label_accuracy[label] is not None
            else None
        )
        for label in LABELS
    }
    supported = [value for value in per_label_accuracy.values() if value is not None]
    supported_f1 = [value for value in per_label_f1.values() if value is not None]
    return {
        "n": len(ids),
        "accuracy": correct / len(ids) if ids else None,
        "balanced_accuracy": sum(supported) / len(supported) if supported else None,
        "per_label_accuracy": per_label_accuracy,
        "per_label_precision": per_label_precision,
        "per_label_f1": per_label_f1,
        "macro_f1": sum(supported_f1) / len(supported_f1) if supported_f1 else None,
        "ordinal_mae": (sum(abs_errors) / len(abs_errors) if abs_errors else None),
        "confusion": confusion,
        "prediction_distribution": distribution,
        "per_editor": {
            editor: {
                "n": int(row["n"]),
                "accuracy": row["correct"] / row["n"],
                "ordinal_mae": (
                    row["abs_error_sum"] / row["n_ordinal"]
                    if row["n_ordinal"]
                    else None
                ),
            }
            for editor, row in sorted(by_editor.items())
        },
    }
