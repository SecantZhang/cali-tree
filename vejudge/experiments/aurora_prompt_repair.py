"""AURORA per-case prompt calibration with repeated VLM judgments.

The module keeps dataset selection, metrics, prompt guards, and repair-state
transitions pure.  :mod:`run.aurora_prompt_repair` owns filesystem orchestration and
the explicit live-call gate.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
from collections import Counter
from typing import Any, Iterable, Optional, Sequence

LABELS = ("no", "partial", "yes")
LABEL_TO_ORDINAL = {"no": 0, "partial": 1, "yes": 2}


def stable_rank(seed: int, value: str) -> str:
    """Return a platform-independent seeded ordering key."""
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def prompt_digest(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def sample_quotas(size: int) -> dict[str, int]:
    """Split ``size`` as evenly as possible, assigning the remainder in label order."""
    if size < len(LABELS):
        raise ValueError("sample size must be at least three")
    base, remainder = divmod(size, len(LABELS))
    return {
        label: base + (1 if index < remainder else 0)
        for index, label in enumerate(LABELS)
    }


def _case_row(
    item_id: str, sample: dict[str, Any], label: dict[str, Any]
) -> dict[str, Any]:
    inputs = sample.get("input") or {}
    outputs = sample.get("output") or {}
    return {
        "item_id": item_id,
        "task_uid": str(sample.get("task_uid") or label.get("task_uid") or ""),
        "task": str(sample.get("task") or label.get("task") or ""),
        "model": str(sample.get("model") or label.get("model") or ""),
        "instruction": str(inputs.get("instruction") or inputs.get("user_prompt") or ""),
        "source_image_path": str(inputs.get("source_image_path") or ""),
        "edited_image_path": str(outputs.get("edited_image_path") or ""),
        "human_score": float(label["human_score"]),
        "target_score": int(label["target_score"]),
        "target_label": str(label["target_label"]),
        "source_split": str(sample.get("split") or label.get("split") or ""),
    }


def build_balanced_sample(
    samples: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    *,
    size: int = 100,
    seed: int = 44,
) -> dict[str, Any]:
    """Select label-balanced outputs while allowing only one output per task.

    Scarce classes are selected first.  Within a class, the greedy score prefers
    underrepresented model and task-category cells, then globally underrepresented
    models/categories, and finally a stable seeded rank.
    """
    quotas = sample_quotas(size)
    rows = [
        _case_row(item_id, sample, labels[item_id])
        for item_id, sample in sorted(samples.items())
        if item_id in labels and labels[item_id].get("target_label") in LABELS
    ]
    if not rows:
        raise ValueError("no judge-ready AURORA cases were found")

    selected: list[dict[str, Any]] = []
    used_tasks: set[str] = set()
    by_label_model: Counter[tuple[str, str]] = Counter()
    by_label_task: Counter[tuple[str, str]] = Counter()
    by_model: Counter[str] = Counter()
    by_task: Counter[str] = Counter()

    for target_label in ("yes", "partial", "no"):
        for _ in range(quotas[target_label]):
            eligible = [
                row
                for row in rows
                if row["target_label"] == target_label
                and row["task_uid"] not in used_tasks
            ]
            if not eligible:
                raise ValueError(
                    f"cannot satisfy unique-task quota for {target_label!r}: "
                    f"selected {sum(r['target_label'] == target_label for r in selected)} "
                    f"of {quotas[target_label]}"
                )
            chosen = min(
                eligible,
                key=lambda row: (
                    by_label_model[(target_label, row["model"])],
                    by_label_task[(target_label, row["task"])],
                    by_model[row["model"]],
                    by_task[row["task"]],
                    stable_rank(seed, row["item_id"]),
                ),
            )
            selected.append(chosen)
            used_tasks.add(chosen["task_uid"])
            by_label_model[(target_label, chosen["model"])] += 1
            by_label_task[(target_label, chosen["task"])] += 1
            by_model[chosen["model"]] += 1
            by_task[chosen["task"]] += 1

    selected.sort(key=lambda row: (LABELS.index(row["target_label"]), row["item_id"]))
    clean_holdout = [row for row in rows if row["task_uid"] not in used_tasks]
    excluded_siblings = [
        row["item_id"]
        for row in rows
        if row["task_uid"] in used_tasks
        and row["item_id"] not in {case["item_id"] for case in selected}
    ]
    return {
        "schema_version": 1,
        "dataset": "AURORA-Bench",
        "seed": seed,
        "sample_size": size,
        "quotas": quotas,
        "selection_order": ["yes", "partial", "no"],
        "cases": selected,
        "selected_task_uids": sorted(used_tasks),
        "excluded_sibling_item_ids": sorted(excluded_siblings),
        "clean_holdout": clean_holdout,
        "counts": {
            "sample": _group_counts(selected),
            "clean_holdout": _group_counts(clean_holdout),
            "excluded_siblings": len(excluded_siblings),
        },
    }


def _group_counts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    return {
        "total": len(materialized),
        "tasks": len({row["task_uid"] for row in materialized}),
        "labels": dict(sorted(Counter(row["target_label"] for row in materialized).items())),
        "models": dict(sorted(Counter(row["model"] for row in materialized).items())),
        "task_categories": dict(sorted(Counter(row["task"] for row in materialized).items())),
    }


def parse_judgment(content: str) -> dict[str, Any]:
    """Parse the compact CaliTree contract without raising on model output."""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        return {
            "label": "",
            "rationale": "",
            "valid": False,
            "parse_error": f"{type(exc).__name__}: {exc}",
        }
    label = str(parsed.get("label") or "").strip().lower() if isinstance(parsed, dict) else ""
    rationale = str(parsed.get("rationale") or "") if isinstance(parsed, dict) else ""
    return {
        "label": label if label in LABELS else "",
        "rationale": rationale,
        "valid": label in LABELS,
        "parse_error": None if label in LABELS else f"invalid label {label!r}",
    }


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def robustness_stats(
    predictions: Sequence[dict[str, Any]], target_label: str, *, required: int = 7
) -> dict[str, Any]:
    counts = Counter(
        str(row.get("label") or "invalid")
        if row.get("valid") and row.get("label") in LABELS
        else "invalid"
        for row in predictions
    )
    total = len(predictions)
    hits = counts[target_label]
    valid_counts = {label: counts[label] for label in LABELS}
    modal_vocabulary = (*LABELS, "invalid")
    modal_label = max(
        modal_vocabulary,
        key=lambda label: (counts[label], -modal_vocabulary.index(label)),
    )
    modal_count = counts[modal_label]
    entropy = 0.0
    if total:
        for count in counts.values():
            if count:
                probability = count / total
                entropy -= probability * math.log2(probability)
    return {
        "n": total,
        "required_correct": required,
        "target_hits": hits,
        "target_hit_rate": hits / total if total else 0.0,
        "robust": total > 0 and hits >= required,
        "label_distribution": {**valid_counts, "invalid": counts["invalid"]},
        "modal_label": modal_label,
        "modal_share": modal_count / total if total else 0.0,
        "entropy_bits": entropy,
        "invalid_rate": counts["invalid"] / total if total else 0.0,
        "wilson_95": wilson_interval(hits, total),
        "confidence_note": (
            "Empirical stability under repeated calls; the 10-run Wilson interval is "
            "reported because a 7/10 threshold is not strong statistical confidence."
        ),
    }


def classification_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compute three-class and ordinal metrics without an sklearn dependency."""
    confusion = {target: {pred: 0 for pred in (*LABELS, "invalid")} for target in LABELS}
    for row in rows:
        target = str(row["target_label"])
        prediction = str((row.get("initial") or {}).get("label") or "invalid")
        if prediction not in LABELS:
            prediction = "invalid"
        confusion[target][prediction] += 1

    total = len(rows)
    correct = sum(confusion[label][label] for label in LABELS)
    recalls: list[float] = []
    f1s: list[float] = []
    per_label: dict[str, Any] = {}
    ordinal_errors: list[float] = []
    for label in LABELS:
        support = sum(confusion[label].values())
        predicted = sum(confusion[target][label] for target in LABELS)
        true_positive = confusion[label][label]
        recall = true_positive / support if support else None
        precision = true_positive / predicted if predicted else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else 0.0
        )
        if recall is not None:
            recalls.append(recall)
        f1s.append(f1)
        per_label[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    for row in rows:
        prediction = str((row.get("initial") or {}).get("label") or "")
        if prediction in LABEL_TO_ORDINAL:
            ordinal_errors.append(
                abs(
                    LABEL_TO_ORDINAL[str(row["target_label"])]
                    - LABEL_TO_ORDINAL[prediction]
                )
            )

    return {
        "n": total,
        "invalid_predictions": sum(confusion[label]["invalid"] for label in LABELS),
        "valid_prediction_rate": (
            sum(sum(confusion[target][label] for label in LABELS) for target in LABELS)
            / total
            if total
            else None
        ),
        "accuracy": correct / total if total else None,
        "balanced_accuracy": sum(recalls) / len(recalls) if recalls else None,
        "macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "ordinal_mae_0_2": (
            sum(ordinal_errors) / len(ordinal_errors) if ordinal_errors else None
        ),
        "ordinal_mae_note": "computed over valid predictions; invalid count is reported separately",
        "quadratic_weighted_kappa": quadratic_weighted_kappa(rows),
        "per_label": per_label,
        "confusion": confusion,
    }


def quadratic_weighted_kappa(rows: Sequence[dict[str, Any]]) -> Optional[float]:
    valid = [
        row
        for row in rows
        if str((row.get("initial") or {}).get("label") or "") in LABELS
    ]
    if not valid:
        return None
    matrix = [[0.0] * 3 for _ in range(3)]
    actual = [0.0] * 3
    predicted = [0.0] * 3
    for row in valid:
        left = LABEL_TO_ORDINAL[str(row["target_label"])]
        right = LABEL_TO_ORDINAL[str(row["initial"]["label"])]
        matrix[left][right] += 1
        actual[left] += 1
        predicted[right] += 1
    total = float(len(valid))
    observed = 0.0
    expected = 0.0
    for left in range(3):
        for right in range(3):
            weight = ((left - right) ** 2) / 4.0
            observed += weight * matrix[left][right] / total
            expected += weight * (actual[left] * predicted[right]) / (total * total)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - observed / expected


def repair_reason(row: dict[str, Any]) -> Optional[str]:
    initial_wrong = (row.get("initial") or {}).get("label") != row.get("target_label")
    unstable = not bool((row.get("robustness") or {}).get("robust"))
    if initial_wrong and unstable:
        return "initial_error_and_unstable"
    if initial_wrong:
        return "initial_error"
    if unstable:
        return "unstable_only"
    return None


def select_anchors(
    baseline_rows: Sequence[dict[str, Any]],
    *,
    per_label: int = 2,
    seed: int = 44,
    allow_fallback: bool = False,
    exclude_item_ids: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    """Pick initially correct high-consensus proxy anchors.

    Robust cases are always preferred. When ``allow_fallback`` is true and a label
    has too few robust cases, fill the remaining slots with the initially correct
    cases having the highest repeat target-hit count. Every returned row records its
    selection tier so a degraded guard can never be mistaken for six robust anchors.
    """
    excluded = exclude_item_ids or set()
    selected: list[dict[str, Any]] = []
    for label in LABELS:
        prototype = float(LABEL_TO_ORDINAL[label])
        initially_correct = [
            row
            for row in baseline_rows
            if row.get("target_label") == label
            and (row.get("initial") or {}).get("label") == label
            and str(row.get("item_id") or "") not in excluded
        ]
        robust = [
            row
            for row in initially_correct
            if bool((row.get("robustness") or {}).get("robust"))
        ]
        robust.sort(
            key=lambda row: (
                abs(float(row["human_score"]) - prototype),
                -int(row["robustness"]["target_hits"]),
                -float(row["robustness"]["modal_share"]),
                stable_rank(seed, str(row["item_id"])),
            )
        )
        chosen = [(row, "robust") for row in robust[:per_label]]
        if len(chosen) < per_label and allow_fallback:
            robust_ids = {str(row["item_id"]) for row in robust}
            fallback = [
                row for row in initially_correct
                if str(row["item_id"]) not in robust_ids
            ]
            fallback.sort(
                key=lambda row: (
                    -int((row.get("robustness") or {}).get("target_hits") or 0),
                    abs(float(row["human_score"]) - prototype),
                    -float((row.get("robustness") or {}).get("modal_share") or 0.0),
                    stable_rank(seed, str(row["item_id"])),
                )
            )
            chosen.extend(
                (row, "best_available_nonrobust")
                for row in fallback[: per_label - len(chosen)]
            )
        if len(chosen) < per_label:
            raise ValueError(
                f"anchor preflight failed: label {label!r} has {len(robust)} robust "
                f"and {len(initially_correct)} total initially-correct cases; need "
                f"{per_label} distinct anchors"
            )
        for row, tier in chosen:
            selected.append({
                **row,
                "anchor_selection": {
                    "tier": tier,
                    "baseline_robust": bool(
                        (row.get("robustness") or {}).get("robust")
                    ),
                    "baseline_target_hits": int(
                        (row.get("robustness") or {}).get("target_hits") or 0
                    ),
                },
            })
    return selected


def normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def lint_candidate(prompt: str, focal_case: dict[str, Any]) -> dict[str, Any]:
    """Reject malformed or plainly target-leaking per-case prompt rewrites."""
    errors: list[str] = []
    normalized = normalize_text(prompt)
    if not prompt.strip():
        errors.append("empty_prompt")
    for token in ("no", "partial", "yes", "label", "rationale"):
        if not re.search(rf"\b{re.escape(token)}\b", normalized):
            errors.append(f"missing_contract_token:{token}")
    for field in ("item_id", "task_uid", "model"):
        value = normalize_text(str(focal_case.get(field) or ""))
        if value and len(value) >= 5 and value in normalized:
            errors.append(f"contains_identifier:{field}")
    instruction = normalize_text(str(focal_case.get("instruction") or ""))
    if instruction and len(instruction) >= 12 and instruction in normalized:
        errors.append("copies_focal_instruction")
    target = re.escape(str(focal_case.get("target_label") or ""))
    target_directives = (
        rf"(?:choose|predict|return|output|assign|use) (?:the )?(?:label )?{target} "
        rf"(?:for|on) (?:this|the) (?:case|example|image)",
        rf"(?:this|the) (?:case|example|image) (?:is|should be|must be) (?:labeled )?{target}",
    )
    if any(re.search(pattern, normalized) for pattern in target_directives):
        errors.append("direct_target_answer")
    return {"valid": not errors, "errors": errors}


def candidate_rank(
    *, target_hits: int, anchor_correct: int, screen_correct: bool, prompt: str
) -> tuple[int, int, int, int]:
    return (target_hits, anchor_correct, int(screen_correct), -len(prompt))


def prompt_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="parent_prompt",
            tofile="candidate_prompt",
        )
    )


def optimizer_feedback(
    focal: dict[str, Any],
    baseline: dict[str, Any],
    previous_round: Optional[dict[str, Any]],
    *,
    include_anchor_feedback: bool = True,
) -> str:
    """Build reusable-boundary feedback for TextGrad or GEPA reflection."""
    current = previous_round or {}
    screen = current.get("screen") or baseline.get("initial") or {}
    robust = current.get("robustness") or baseline.get("robustness") or {}
    anchors = current.get("anchors") or []
    anchor_failures = [
        {
            "target": row.get("target_label"),
            "prediction": (row.get("prediction") or {}).get("label") or "invalid",
        }
        for row in anchors
        if not row.get("correct")
    ]
    anchor_line = (
        f"Anchor regressions by label only: {json.dumps(anchor_failures)}\n"
        if include_anchor_feedback
        else ""
    )
    return (
        "Revise the general Semantic Consistency rubric, not this item's answer.\n"
        f"Observed prediction: {screen.get('label') or 'invalid'}\n"
        f"Human target: {focal['target_label']}\n"
        f"Judge rationale: {screen.get('rationale') or ''}\n"
        f"Instruction: {focal['instruction']}\n"
        f"Repeated label distribution: {json.dumps(robust.get('label_distribution') or {})}\n"
        f"Repeated target hits: {robust.get('target_hits', 0)}/{robust.get('n', 0)}\n"
        f"{anchor_line}\n"
        "Diagnose the reusable no/partial/yes boundary that failed. Return a complete, "
        "standalone rubric preserving exactly the compact JSON label/rationale contract. "
        "Do not include item IDs, editor/model names, the focal instruction, distinctive "
        "image details, or a rule that directly assigns this case's target label."
    )


def baseline_summary(
    rows: Sequence[dict[str, Any]], *, required_correct: int = 7
) -> dict[str, Any]:
    metrics = classification_metrics(rows)
    repair_rows = [row for row in rows if repair_reason(row)]
    robust_count = sum(bool(row["robustness"]["robust"]) for row in rows)
    metrics.update(
        {
            "robust_count": robust_count,
            "robust_coverage": robust_count / len(rows) if rows else None,
            "repair_pool_size": len(repair_rows),
            "repair_reasons": dict(
                sorted(Counter(repair_reason(row) for row in repair_rows).items())
            ),
            "confidence_note": (
                f"Robust means empirically stable at >={required_correct}/10 correct fresh "
                "temperature-0.3 "
                "calls; it is not a high-confidence statistical guarantee."
            ),
        }
    )
    return metrics
