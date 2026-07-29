"""Workflow executors for training, routing, and evaluating Cali-Tree prompt hierarchies."""

from __future__ import annotations

import hashlib
import json
import random
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from ...core.calibration.calitree import CaliTreeBuilder, classification_metrics, route_prompt
from ...core.calibration.textgrad_adapter import textgrad_update
from ...core.judge.parse import parse_json_object
from ...lm_engine import get_engine, load_creds, require_live
from ...lm_engine import openai_compat
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "core" / "prompts" / "templates"
PROMPT_VERSIONS = ("calitree_v1", "calitree_v2", "calitree_v3", "calitree_v4")


def _prompt(name: str, version: str = "calitree_v2") -> str:
    if version not in PROMPT_VERSIONS:
        raise ValueError(f"Unknown Cali-Tree prompt version {version!r}")
    return (PROMPT_ROOT / version / name).read_text(encoding="utf-8").strip()


def _hash(*parts: Any) -> str:
    body = json.dumps(parts, sort_keys=True, default=str).encode()
    return hashlib.sha256(body).hexdigest()[:20]


def _target(label: Any) -> str:
    if isinstance(label, dict):
        return str(label.get("target_label") or "")
    return str(getattr(label, "target_label", ""))


def _routing_text(sample: dict[str, Any]) -> str:
    """Target-blind routing representation available identically at train and inference."""
    instruction = str((sample.get("input") or {}).get("instruction") or "")
    editor = str(sample.get("editor") or sample.get("model") or "unknown")
    return (
        f"edit instruction: {instruction}\n"
        f"editor family: {editor}\n"
        f"semantic edit type: {_semantic_edit_type(sample)}"
    )


def _fit_conflict_policy(
    base_results: dict[str, dict[str, Any]],
    critic_results: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    train_ids: list[str],
    *,
    min_support: int,
    min_gain: float,
) -> dict[str, Any]:
    """Fit a small pruned decision tree using training labels only.

    Rules split first by editor+base-label when supported, then fall back to a base-label
    rule. A critic branch survives pruning only when it improves training accuracy by more
    than ``min_gain``; test labels never participate.
    """
    rules: dict[str, dict[str, Any]] = {}
    global_ids = list(train_ids)
    global_base_correct = sum(
        base_results[i].get("label") == targets[i] for i in global_ids
    )
    global_critic_correct = sum(
        critic_results[i].get("label") == targets[i] for i in global_ids
    )
    global_base_accuracy = global_base_correct / len(global_ids) if global_ids else 0.0
    global_critic_accuracy = global_critic_correct / len(global_ids) if global_ids else 0.0
    global_action = (
        "critic"
        if global_critic_accuracy > global_base_accuracy + min_gain
        else "base"
    )
    rules["*::*"] = {
        "editor": "*",
        "base_label": "*",
        "n": len(global_ids),
        "base_accuracy": global_base_accuracy,
        "critic_accuracy": global_critic_accuracy,
        "gain": global_critic_accuracy - global_base_accuracy,
        "action": global_action,
        "scope": "global",
    }
    groups: dict[tuple[str, str], list[str]] = {}
    for item_id in train_ids:
        base_label = str(base_results[item_id].get("label") or "")
        editor = str(samples[item_id].get("editor") or "unknown")
        groups.setdefault(("*", base_label), []).append(item_id)
        groups.setdefault((editor, base_label), []).append(item_id)
    for (editor, base_label), ids in sorted(groups.items()):
        if len(ids) < min_support:
            continue
        base_correct = sum(base_results[i].get("label") == targets[i] for i in ids)
        critic_correct = sum(critic_results[i].get("label") == targets[i] for i in ids)
        base_accuracy = base_correct / len(ids)
        critic_accuracy = critic_correct / len(ids)
        selected_accuracy = (
            critic_accuracy if global_action == "critic" else base_accuracy
        )
        alternative_action = "base" if global_action == "critic" else "critic"
        alternative_accuracy = (
            base_accuracy if alternative_action == "base" else critic_accuracy
        )
        # A narrower branch exists only when it beats the already selected global action.
        # Otherwise it is pruned and inherits the global decision.
        if alternative_accuracy <= selected_accuracy + min_gain:
            continue
        key = f"{editor}::{base_label}"
        rules[key] = {
            "editor": editor,
            "base_label": base_label,
            "n": len(ids),
            "base_accuracy": base_accuracy,
            "critic_accuracy": critic_accuracy,
            "gain": critic_accuracy - base_accuracy,
            "action": alternative_action,
            "scope": "editor_label" if editor != "*" else "base_label",
        }
    return {
        "version": "conflict-tree-v1",
        "selection_split": "train",
        "min_support": min_support,
        "min_gain": min_gain,
        "rules": rules,
    }


def _conflict_action(
    policy: dict[str, Any], sample: dict[str, Any], base_label: str
) -> tuple[str, str]:
    rules = policy.get("rules") or {}
    editor = str(sample.get("editor") or "unknown")
    for key in (f"{editor}::{base_label}", f"*::{base_label}", "*::*"):
        rule = rules.get(key)
        if isinstance(rule, dict):
            return str(rule.get("action") or "base"), key
    return "base", "pruned:no_supported_rule"


def _consensus_result(
    candidates: dict[str, dict[str, Any]],
    *,
    fallback: dict[str, Any],
    tie_label: str = "partial",
) -> dict[str, Any]:
    """Resolve independent rubric variants without consulting evaluation labels."""
    labels = {
        name: str(result.get("label") or "")
        for name, result in candidates.items()
        if str(result.get("label") or "") in {"no", "partial", "yes"}
    }
    counts = Counter(labels.values())
    if not counts:
        selected_label = str(fallback.get("label") or "")
        selected_name = "routed"
        selected = fallback
        is_tie = False
    else:
        selected_label, support = max(
            counts.items(),
            key=lambda pair: (pair[1], pair[0] == tie_label, pair[0]),
        )
        is_tie = support < 2 and len(counts) >= 3
        if is_tie:
            selected_label = tie_label
        selected_name = next(
            (
                name
                for name in ("critic", "textgrad", "initial")
                if labels.get(name) == selected_label
            ),
            next(iter(labels)),
        )
        selected = candidates[selected_name]
    return {
        **selected,
        "label": selected_label,
        "consensus_label": selected_label,
        "consensus_source": selected_name,
        "candidate_labels": labels,
        "consensus_support": counts.get(selected_label, 0),
        "consensus_tie": is_tie,
    }


def _semantic_edit_type(sample: dict[str, Any]) -> str:
    """Deterministic, target-blind preprocessing of an edit instruction."""
    instruction = str(
        (sample.get("input") or {}).get("instruction") or ""
    ).lower()
    patterns = (
        ("remove", r"\b(remove|delete|erase|eliminate|without)\b|get rid of"),
        ("add", r"\b(add|insert|include|introduce)\b"),
        ("count", r"\b(second|another|two|three|double|duplicate)\b"),
        ("spatial", r"\b(left|right|behind|beside|near|above|below)\b|in front of|on top of"),
        ("style_material", r"\b(style|painting|sketch|cartoon|wooden|metal|glass|fabric)\b"),
        ("color", r"\b(red|blue|green|yellow|black|white|orange|purple|pink|brown|gray|grey)\b"),
        ("replace", r"\b(replace|swap)\b|\bchange\b.+\b(into|to)\b"),
        ("state_action", r"\b(open|close|closed|turn on|turn off|smile|bark|lick|pose|wear)\b"),
        ("background", r"\b(background|sky|floor|ground|wall)\b"),
    )
    for name, pattern in patterns:
        if re.search(pattern, instruction):
            return name
    return "attribute_other"


def _task_uid(
    item_id: str,
    sample: dict[str, Any],
    label: Optional[dict[str, Any]] = None,
) -> str:
    """Return the source-task identity shared by all editor outputs."""
    return str(
        sample.get("task_uid")
        or (label or {}).get("task_uid")
        or item_id.rsplit("::", 1)[0]
    )


def _candidate_pattern(
    candidates: dict[str, dict[str, Any]]
) -> str:
    return "|".join(
        str((candidates.get(name) or {}).get("label") or "invalid")
        for name in ("initial", "textgrad", "critic")
    )


def _calibration_feature(
    level: str,
    sample: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
) -> str:
    editor = str(sample.get("editor") or "unknown")
    operation = _semantic_edit_type(sample)
    pattern = _candidate_pattern(candidates)
    values = {
        "pattern": pattern,
        "editor": editor,
        "operation": operation,
        "editor_pattern": f"{editor}::{pattern}",
        "operation_pattern": f"{operation}::{pattern}",
        "editor_operation": f"{editor}::{operation}",
        "editor_operation_pattern": (
            f"{editor}::{operation}::{pattern}"
        ),
    }
    return values[level]


def _fit_calibration_rules(
    *,
    ids: list[str],
    candidates: dict[str, dict[str, dict[str, Any]]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    levels: list[str],
    min_support: int,
    min_gain: float,
) -> dict[str, Any]:
    base_labels = {
        item_id: _consensus_result(
            candidates[item_id],
            fallback=candidates[item_id].get("initial") or {},
        )["label"]
        for item_id in ids
    }
    rules: dict[str, dict[str, Any]] = {}
    for level in levels:
        groups: dict[str, list[str]] = {}
        for item_id in ids:
            value = _calibration_feature(
                level, samples[item_id], candidates[item_id]
            )
            groups.setdefault(value, []).append(item_id)
        for value, group_ids in sorted(groups.items()):
            if len(group_ids) < min_support:
                continue
            counts = Counter(targets[item_id] for item_id in group_ids)
            best_label, best_correct = max(
                counts.items(),
                key=lambda pair: (
                    pair[1],
                    pair[0] == "partial",
                    pair[0],
                ),
            )
            base_correct = sum(
                base_labels[item_id] == targets[item_id]
                for item_id in group_ids
            )
            gain = (best_correct - base_correct) / len(group_ids)
            if best_label == "" or gain <= min_gain:
                continue
            rules[f"{level}::{value}"] = {
                "level": level,
                "value": value,
                "n": len(group_ids),
                "label": best_label,
                "counts": {
                    label: counts.get(label, 0)
                    for label in ("no", "partial", "yes")
                },
                "base_accuracy": base_correct / len(group_ids),
                "rule_accuracy": best_correct / len(group_ids),
                "gain": gain,
            }
    return {
        "levels": levels,
        "min_support": min_support,
        "min_gain": min_gain,
        "rules": rules,
    }


def _apply_consensus_calibrator(
    policy: dict[str, Any],
    *,
    sample: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    consensus = _consensus_result(
        candidates,
        fallback=fallback,
        tie_label=str(policy.get("tie_label") or "partial"),
    )
    for level in policy.get("levels") or []:
        value = _calibration_feature(level, sample, candidates)
        key = f"{level}::{value}"
        rule = (policy.get("rules") or {}).get(key)
        if not isinstance(rule, dict):
            continue
        label = str(rule.get("label") or "")
        selected_name = next(
            (
                name
                for name in ("critic", "textgrad", "initial")
                if str((candidates.get(name) or {}).get("label") or "")
                == label
            ),
            str(consensus.get("consensus_source") or "consensus"),
        )
        selected = candidates.get(selected_name) or consensus
        return {
            **selected,
            "label": label,
            "consensus_label": consensus["label"],
            "consensus_source": consensus["consensus_source"],
            "candidate_labels": consensus["candidate_labels"],
            "consensus_support": consensus["consensus_support"],
            "consensus_tie": consensus["consensus_tie"],
            "calibration_action": "override",
            "calibration_rule": key,
            "calibration_rule_support": rule.get("n"),
            "calibration_rule_gain": rule.get("gain"),
        }
    consensus["calibration_action"] = "consensus"
    consensus["calibration_rule"] = "consensus"
    return consensus


def _select_consensus_calibrator(
    *,
    fit_ids: list[str],
    validation_ids: list[str],
    train_ids: list[str],
    candidates: dict[str, dict[str, dict[str, Any]]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    min_gain: float = 0.0,
) -> dict[str, Any]:
    """Select rule capacity on grouped validation, then refit on all training data."""
    configurations = (
        [],
        ["pattern"],
        ["operation_pattern", "pattern"],
        ["editor_pattern", "pattern"],
        ["operation_pattern", "editor_pattern", "pattern"],
        [
            "editor_operation_pattern",
            "operation_pattern",
            "editor_pattern",
            "pattern",
        ],
    )
    supports = (4, 8, 12)
    validation_targets = {
        item_id: targets[item_id] for item_id in validation_ids
    }
    baseline_predictions = {
        item_id: _consensus_result(
            candidates[item_id],
            fallback=candidates[item_id].get("initial") or {},
        )["label"]
        for item_id in validation_ids
    }
    baseline_metrics = classification_metrics(
        validation_targets, baseline_predictions, samples
    )
    best = {
        "levels": [],
        "min_support": 0,
        "accuracy": baseline_metrics["accuracy"],
        "balanced_accuracy": baseline_metrics["balanced_accuracy"],
        "rules": {},
    }
    trials: list[dict[str, Any]] = []
    if validation_ids:
        for levels in configurations[1:]:
            for min_support in supports:
                fitted = _fit_calibration_rules(
                    ids=fit_ids,
                    candidates=candidates,
                    samples=samples,
                    targets=targets,
                    levels=list(levels),
                    min_support=min_support,
                    min_gain=min_gain,
                )
                predictions = {
                    item_id: _apply_consensus_calibrator(
                        fitted,
                        sample=samples[item_id],
                        candidates=candidates[item_id],
                        fallback=candidates[item_id].get("initial") or {},
                    )["label"]
                    for item_id in validation_ids
                }
                metrics = classification_metrics(
                    validation_targets, predictions, samples
                )
                trial = {
                    "levels": list(levels),
                    "min_support": min_support,
                    "n_rules": len(fitted["rules"]),
                    "accuracy": metrics["accuracy"],
                    "balanced_accuracy": metrics["balanced_accuracy"],
                }
                trials.append(trial)
                score = (
                    metrics["accuracy"],
                    metrics["balanced_accuracy"],
                    -len(fitted["rules"]),
                    -len(levels),
                    min_support,
                )
                best_score = (
                    best["accuracy"],
                    best["balanced_accuracy"],
                    -len(best["rules"]),
                    -len(best["levels"]),
                    best["min_support"],
                )
                if score > best_score:
                    best = {**trial, "rules": fitted["rules"]}

    selected_levels = list(best["levels"])
    selected_support = int(best["min_support"] or 4)
    deployed = _fit_calibration_rules(
        ids=train_ids,
        candidates=candidates,
        samples=samples,
        targets=targets,
        levels=selected_levels,
        min_support=selected_support,
        min_gain=min_gain,
    )
    return {
        "version": "hierarchical-consensus-v1",
        "selection_split": "task_grouped_internal_validation",
        "tie_label": "partial",
        **deployed,
        "selection": {
            "baseline_accuracy": baseline_metrics["accuracy"],
            "baseline_balanced_accuracy": baseline_metrics[
                "balanced_accuracy"
            ],
            "selected_accuracy": best["accuracy"],
            "selected_balanced_accuracy": best["balanced_accuracy"],
            "selected_levels": selected_levels,
            "selected_min_support": selected_support,
            "trials": trials,
        },
    }


def _fit_editor_prior(
    population_labels: dict[str, Any],
    *,
    threshold: float,
    min_support: int,
) -> dict[str, Any]:
    """Fit high-confidence editor branches from the official training partition only."""
    counts: dict[str, Counter[str]] = {}
    for label in population_labels.values():
        if not isinstance(label, dict) or label.get("split") != "train":
            continue
        target = _target(label)
        editor = str(label.get("editor") or "unknown")
        if target in {"no", "partial", "yes"}:
            counts.setdefault(editor, Counter())[target] += 1
    branches: dict[str, dict[str, Any]] = {}
    for editor, row in sorted(counts.items()):
        n = sum(row.values())
        label, support = row.most_common(1)[0]
        confidence = support / n
        branches[editor] = {
            "n": n,
            "counts": {name: row.get(name, 0) for name in ("no", "partial", "yes")},
            "label": label,
            "confidence": confidence,
            "active": n >= min_support and confidence >= threshold,
        }
    return {
        "version": "editor-prior-v1",
        "selection_split": "train",
        "threshold": threshold,
        "min_support": min_support,
        "branches": branches,
    }


def _editor_prior_action(
    policy: dict[str, Any], sample: dict[str, Any]
) -> tuple[str | None, str]:
    editor = str(sample.get("editor") or "unknown")
    branch = (policy.get("branches") or {}).get(editor)
    if isinstance(branch, dict) and branch.get("active"):
        return str(branch.get("label") or ""), f"editor_prior:{editor}"
    return None, "editor_prior:pruned"


def _human_agreement_bucket(label: Any) -> str:
    ratings = label.get("ratings") if isinstance(label, dict) else None
    sc_values = {
        float(row["sc"])
        for row in (ratings or [])
        if isinstance(row, dict) and row.get("sc") is not None
    }
    if not ratings or not sc_values:
        return "unknown"
    return "unanimous" if len(sc_values) == 1 else "disputed"


def _metrics_with_human_agreement(
    targets: dict[str, str],
    predictions: dict[str, str],
    samples: dict[str, dict[str, Any]],
    labels: dict[str, Any],
) -> dict[str, Any]:
    report = classification_metrics(targets, predictions, samples)
    groups: dict[str, list[str]] = {}
    for item_id in sorted(set(targets) & set(predictions)):
        task_uid = str(samples[item_id].get("task_uid") or item_id.split("::", 1)[0])
        groups.setdefault(task_uid, []).append(item_id)
    if len(groups) >= 2:
        group_ids = sorted(groups)
        accuracy_draws: list[float] = []
        balanced_draws: list[float] = []
        rng = random.Random(44)
        for _repeat in range(1000):
            drawn = [
                item_id
                for _ in group_ids
                for item_id in groups[rng.choice(group_ids)]
            ]
            accuracy_draws.append(
                sum(targets[item_id] == predictions[item_id] for item_id in drawn)
                / len(drawn)
            )
            label_scores = [
                sum(
                    predictions[item_id] == label
                    for item_id in drawn
                    if targets[item_id] == label
                )
                / sum(targets[item_id] == label for item_id in drawn)
                for label in ("no", "partial", "yes")
                if any(targets[item_id] == label for item_id in drawn)
            ]
            balanced_draws.append(sum(label_scores) / len(label_scores))

        def interval(values: list[float]) -> list[float]:
            ordered = sorted(values)
            return [ordered[24], ordered[974]]

        report["grouped_bootstrap_95_ci"] = {
            "unit": "task_uid",
            "repeats": 1000,
            "accuracy": interval(accuracy_draws),
            "balanced_accuracy": interval(balanced_draws),
        }
    buckets: dict[str, list[str]] = {
        "unanimous": [],
        "disputed": [],
        "unknown": [],
    }
    for item_id in sorted(set(targets) & set(predictions)):
        buckets[_human_agreement_bucket(labels.get(item_id))].append(
            item_id
        )
    report["human_agreement"] = {
        bucket: classification_metrics(
            {item_id: targets[item_id] for item_id in ids},
            {item_id: predictions[item_id] for item_id in ids},
            samples,
        )
        for bucket, ids in buckets.items()
        if ids
    }
    return report


def _selective_metrics(
    targets: dict[str, str],
    predictions: dict[str, str],
    samples: dict[str, dict[str, Any]],
    labels: dict[str, Any],
    result_rows: dict[str, dict[str, Any]],
    *,
    min_consensus_support: int = 3,
    policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Score target-blind abstention using consensus and train-fitted editor reliability."""
    ids = sorted(set(targets) & set(predictions) & set(result_rows))
    policy_support = int(
        (policy or {}).get("minimum_consensus_support")
        or min_consensus_support
    )
    branches = (policy or {}).get("editors") or {}

    def accepted(item_id: str) -> bool:
        explicit = result_rows[item_id].get("selective_accepted")
        if explicit is not None:
            return bool(explicit)
        if int(result_rows[item_id].get("consensus_support") or 0) < policy_support:
            return False
        if not policy:
            return True
        editor = str(samples[item_id].get("editor") or "unknown")
        branch = branches.get(editor)
        return isinstance(branch, dict) and bool(branch.get("active"))

    accepted_ids = [
        item_id
        for item_id in ids
        if accepted(item_id)
    ]
    has_persisted_decision = any(
        "selective_accepted" in result_rows[item_id] for item_id in ids
    )
    return {
        "confidence_signal": (
            "consensus_support+training_editor_reliability"
            if policy
            else (
                "persisted_training_selective_policy"
                if has_persisted_decision
                else "consensus_support"
            )
        ),
        "minimum_support": policy_support,
        "policy": policy,
        "n_total": len(ids),
        "n_accepted": len(accepted_ids),
        "n_abstained": len(ids) - len(accepted_ids),
        "coverage": (
            len(accepted_ids) / len(ids) if ids else 0.0
        ),
        "accepted": _metrics_with_human_agreement(
            {item_id: targets[item_id] for item_id in accepted_ids},
            {
                item_id: predictions[item_id]
                for item_id in accepted_ids
            },
            samples,
            labels,
        ),
    }


def _fit_selective_policy(
    result_rows: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    train_ids: list[str],
    *,
    minimum_consensus_support: int,
    editor_min_support: int,
    editor_accuracy_threshold: float,
) -> dict[str, Any]:
    """Fit a deployable selective operating point using training labels only."""
    counts: dict[str, list[int]] = {}
    for item_id in train_ids:
        row = result_rows.get(item_id) or {}
        if int(row.get("consensus_support") or 0) < minimum_consensus_support:
            continue
        editor = str(samples[item_id].get("editor") or "unknown")
        stats = counts.setdefault(editor, [0, 0])
        stats[1] += 1
        stats[0] += int(str(row.get("label") or "") == targets.get(item_id))
    editors = {}
    for editor, (correct, n) in sorted(counts.items()):
        accuracy = correct / n if n else 0.0
        editors[editor] = {
            "n": n,
            "correct": correct,
            "accuracy": accuracy,
            "active": (
                n >= editor_min_support
                and accuracy >= editor_accuracy_threshold
            ),
        }
    return {
        "version": "consensus-editor-reliability-v1",
        "selection_split": "filtered_official_train",
        "minimum_consensus_support": minimum_consensus_support,
        "editor_min_support": editor_min_support,
        "editor_accuracy_threshold": editor_accuracy_threshold,
        "editors": editors,
        "active_editors": sorted(
            editor for editor, row in editors.items() if row["active"]
        ),
    }


def _calibration_split(
    train_ids: list[str],
    labels: dict[str, Any],
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    """Deterministic task-grouped fit/validation split within official training data."""
    if validation_fraction <= 0:
        return sorted(train_ids), []
    task_groups: dict[str, list[str]] = {}
    for item_id in train_ids:
        label = labels[item_id]
        task_uid = (
            str(label.get("task_uid") or item_id.split("::", 1)[0])
            if isinstance(label, dict)
            else item_id.split("::", 1)[0]
        )
        task_groups.setdefault(task_uid, []).append(item_id)
    if len(task_groups) < 2:
        return sorted(train_ids), []

    n_validation_groups = max(
        1, round(len(task_groups) * validation_fraction)
    )
    n_validation_groups = min(
        n_validation_groups, len(task_groups) - 1
    )
    label_names = ("no", "partial", "yes")
    total_counts = Counter(
        _target(labels[item_id]) for item_id in train_ids
    )
    target_counts = {
        label: total_counts[label] * validation_fraction
        for label in label_names
    }
    group_counts = {
        task_uid: Counter(
            _target(labels[item_id]) for item_id in item_ids
        )
        for task_uid, item_ids in task_groups.items()
    }
    selected_groups: list[str] = []
    selected_counts: Counter[str] = Counter()
    remaining = set(task_groups)
    while len(selected_groups) < n_validation_groups:
        def score(task_uid: str) -> tuple[float, str]:
            candidate = selected_counts + group_counts[task_uid]
            distance = sum(
                (
                    (candidate[label] - target_counts[label])
                    / max(1.0, target_counts[label])
                ) ** 2
                for label in label_names
            )
            digest = hashlib.sha256(
                f"{seed}:{task_uid}".encode()
            ).hexdigest()
            return distance, digest

        chosen = min(remaining, key=score)
        selected_groups.append(chosen)
        selected_counts.update(group_counts[chosen])
        remaining.remove(chosen)

    validation = sorted(
        item_id
        for task_uid in selected_groups
        for item_id in task_groups[task_uid]
    )
    validation_set = set(validation)
    fit = sorted(
        item_id for item_id in train_ids
        if item_id not in validation_set
    )
    return sorted(fit), sorted(validation)


def _engine_from(config: dict[str, Any], ctx: NodeRunContext) -> Any:
    model = str(config.get("model") or "").strip()
    if not model:
        raise ValueError("Cali-Tree requires an explicitly configured engine model")
    temperature = config.get("temperature")
    kwargs: dict[str, Any] = {} if temperature is None else {"temperature": temperature}
    return get_engine(
        config.get("engine_kind") or "gpt",
        history=ctx.run.history,
        model=model,
        creds=load_creds(),
        max_tokens=int(config.get("max_tokens") or 4096),
        **kwargs,
    )


def _media(sample: dict[str, Any]) -> list[dict[str, str]]:
    source = str((sample.get("input") or {}).get("source_image_path") or "")
    edited = str((sample.get("output") or {}).get("edited_image_path") or "")
    if not source or not edited:
        raise ValueError(f"Image sample {sample.get('item_id')} is missing source/edited paths")
    return [{"type": "image", "path": source}, {"type": "image", "path": edited}]


def _parse_judgment(content: str) -> dict[str, Any]:
    try:
        parsed = parse_json_object(content)
    except (ValueError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        return {"label": "", "rationale": "", "raw_content": content, "valid": False}
    model_label = str(parsed.get("label") or "").strip().lower()
    label = model_label
    conflict_reason = ""
    scores = parsed.get("rubric_scores")
    if parsed.get("rubric_version") == "sc-v3" and isinstance(scores, dict):
        requested = str(scores.get("requested_change") or "").strip().lower()
        subject = str(scores.get("subject_identity") or "").strip().lower()
        spatial = str(scores.get("spatial_relation") or "").strip().lower()
        scene = str(scores.get("scene_continuity") or "").strip().lower()
        if requested == "none":
            label = "no"
            conflict_reason = "requested change has no visible evidence"
        elif subject == "wrong":
            label = "no"
            conflict_reason = "the edit changes the wrong subject"
        elif spatial == "wrong":
            label = "no"
            conflict_reason = "an explicit spatial condition is not followed"
        elif scene == "replaced":
            label = "no"
            conflict_reason = "the source editing scene is replaced"
        elif (
            requested == "partial"
            or subject == "ambiguous"
            or spatial == "partial"
        ):
            label = "partial"
            conflict_reason = "at least one requested semantic condition is only partial"
        elif (
            requested == "full"
            and subject in {"correct", "not_applicable"}
            and spatial in {"correct", "not_applicable"}
        ):
            label = "yes"
            conflict_reason = "all requested semantic conditions are visibly fulfilled"
    fulfillment = str(parsed.get("fulfillment") or "").strip().lower()
    if fulfillment in {"none", "partial", "full"}:
        label = {"none": "no", "partial": "partial", "full": "yes"}[fulfillment]
        conflict_reason = f"fulfillment={fulfillment} deterministically maps to {label}"
    return {
        "label": label if label in {"no", "partial", "yes"} else "",
        "model_label": model_label if model_label in {"no", "partial", "yes"} else "",
        "rationale": str(parsed.get("rationale") or ""),
        "raw_content": content,
        "parsed": parsed,
        "valid": label in {"no", "partial", "yes"},
        "conflict_resolved": (
            label in {"no", "partial", "yes"}
            and model_label in {"no", "partial", "yes"}
            and label != model_label
        ),
        "conflict_reason": conflict_reason if label != model_label else "",
    }


def _format_feedback(
    ids: list[str],
    samples: dict[str, Any],
    targets: dict[str, str],
    results: dict[str, dict[str, Any]],
    *,
    prompt_version: str = "calitree_v2",
) -> str:
    template = _prompt("gradient_feedback.txt", prompt_version)
    return "\n\n".join(
        template.format(
            instruction=str((samples[item_id].get("input") or {}).get("instruction") or ""),
            prediction=str(results[item_id].get("label") or ""),
            target=targets[item_id],
            rationale=str(results[item_id].get("rationale") or ""),
        )
        for item_id in ids
    )


class _CaliTreeRuntime:
    def __init__(
        self,
        ctx: NodeRunContext,
        *,
        judge_engine: Any,
        optimizer_engine: Any,
        embedding_model: str,
        optimizer_budget: int,
        prompt_version: str = "calitree_v2",
        concurrency: int = 1,
    ) -> None:
        self.ctx = ctx
        self.judge_engine = judge_engine
        self.optimizer_engine = optimizer_engine
        self.embedding_model = embedding_model
        self.optimizer_budget = optimizer_budget
        self.prompt_version = prompt_version
        self.concurrency = max(1, int(concurrency))
        self.optimizer_completion_tokens = 0
        self._usage_lock = threading.Lock()
        self.usage = {
            "judge_calls": 0, "optimizer_calls": 0, "embedding_calls": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        }

    def _record(self, result: dict[str, Any], kind: str) -> None:
        with self._usage_lock:
            self.usage[f"{kind}_calls"] += 1
            for source, target in (
                ("promptTokens", "prompt_tokens"),
                ("completionTokens", "completion_tokens"),
                ("totalTokens", "total_tokens"),
            ):
                self.usage[target] += int(result.get(source) or 0)
            if kind == "optimizer":
                self.optimizer_completion_tokens += int(result.get("completionTokens") or 0)

    def reset_optimizer_budget(self) -> None:
        self.optimizer_completion_tokens = 0

    def judge(self, prompt: str, sample: dict[str, Any]) -> dict[str, Any]:
        key = f"{self.ctx.node_id}::calitree::judge::{_hash(prompt, sample.get('item_id'))}"
        if self.ctx.checkpoint.has(key):
            return self.ctx.checkpoint.get(key)
        instruction = str((sample.get("input") or {}).get("instruction") or "")
        result = self.judge_engine.generate(
            f"Instruction: {instruction}\nThe first image is SOURCE; the second is EDITED.",
            media_inputs=_media(sample),
            system=prompt,
        )
        self._record(result, "judge")
        parsed = _parse_judgment(str(result.get("content") or ""))
        if parsed["valid"]:
            self.ctx.checkpoint.put(key, parsed)
        return parsed

    def judge_many(
        self, prompt: str, samples: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        if self.concurrency <= 1 or len(samples) <= 1:
            return {
                item_id: self.judge(prompt, sample)
                for item_id, sample in samples.items()
            }
        output: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(samples))) as executor:
            futures = {
                executor.submit(self.judge, prompt, sample): item_id
                for item_id, sample in samples.items()
            }
            for future in as_completed(futures):
                output[futures[future]] = future.result()
        return {item_id: output[item_id] for item_id in sorted(output)}

    def critic(
        self,
        prompt: str,
        sample: dict[str, Any],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        key = (
            f"{self.ctx.node_id}::calitree::critic::"
            f"{_hash(prompt, sample.get('item_id'), candidate.get('label'), candidate.get('rationale'))}"
        )
        if self.ctx.checkpoint.has(key):
            return self.ctx.checkpoint.get(key)
        instruction = str((sample.get("input") or {}).get("instruction") or "")
        user = (
            f"Instruction: {instruction}\n"
            "The first image is SOURCE; the second is EDITED.\n"
            f"Untrusted candidate label: {candidate.get('label')}\n"
            f"Untrusted candidate rationale: {candidate.get('rationale')}"
        )
        result = self.judge_engine.generate(
            user,
            media_inputs=_media(sample),
            system=prompt,
        )
        self._record(result, "judge")
        parsed = _parse_judgment(str(result.get("content") or ""))
        if parsed["valid"]:
            self.ctx.checkpoint.put(key, parsed)
        return parsed

    def critic_many(
        self,
        prompt: str,
        samples: dict[str, dict[str, Any]],
        candidates: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        if self.concurrency <= 1 or len(samples) <= 1:
            return {
                item_id: self.critic(prompt, sample, candidates[item_id])
                for item_id, sample in samples.items()
            }
        output: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(samples))) as executor:
            futures = {
                executor.submit(
                    self.critic, prompt, sample, candidates[item_id]
                ): item_id
                for item_id, sample in samples.items()
            }
            for future in as_completed(futures):
                output[futures[future]] = future.result()
        return {item_id: output[item_id] for item_id in sorted(output)}

    def optimize(self, prompt: str, feedback: str) -> str:
        if self.optimizer_completion_tokens >= self.optimizer_budget:
            return prompt
        key = f"{self.ctx.node_id}::calitree::opt::{_hash(prompt, feedback)}"
        if self.ctx.checkpoint.has(key):
            return str(self.ctx.checkpoint.get(key))

        def record(result: dict[str, Any]) -> None:
            self._record(result, "optimizer")

        updated = textgrad_update(
            prompt,
            feedback,
            engine=self.optimizer_engine,
            usage_cb=record,
            log_dir=self.ctx.run.run_dir / "textgrad",
        )
        self.ctx.checkpoint.put(key, updated)
        return updated

    def extract(self, prompt: str) -> dict[str, list[str]]:
        key = (
            f"{self.ctx.node_id}::calitree::components::"
            f"{_hash(self.prompt_version, prompt)}"
        )
        if self.ctx.checkpoint.has(key):
            return self.ctx.checkpoint.get(key)
        query = _prompt("extract_components.txt", self.prompt_version).format(rubric=prompt)
        result = self.optimizer_engine.generate(query)
        self._record(result, "optimizer")
        try:
            parsed = parse_json_object(str(result.get("content") or ""))
        except (ValueError, TypeError):
            parsed = {}
        components = {
            name: [str(value) for value in (parsed.get(name) or [])]
            for name in ("criteria", "priorities", "constraints")
        }
        if not any(components.values()):
            components["criteria"] = [prompt]
        self.ctx.checkpoint.put(key, components)
        return components

    def embed(self, texts: list[str]) -> list[list[float]]:
        keys = [f"{self.ctx.node_id}::calitree::embedding::{_hash(self.embedding_model, text)}"
                for text in texts]
        vectors: list[list[float] | None] = [
            self.ctx.checkpoint.get(key) if self.ctx.checkpoint.has(key) else None
            for key in keys
        ]
        missing_indices = [index for index, value in enumerate(vectors) if value is None]
        if missing_indices:
            result = openai_compat.embeddings(
                endpoints=self.judge_engine.creds.endpoints,
                token=self.judge_engine.creds.token,
                model=self.embedding_model,
                inputs=[texts[index] for index in missing_indices],
            )
            self.usage["embedding_calls"] += 1
            self.usage["prompt_tokens"] += result.prompt_tokens
            self.usage["total_tokens"] += result.total_tokens
            self.ctx.run.history.record(
                engine="openai-compatible-embeddings",
                model=self.embedding_model,
                prompt="\n\n".join(texts[index] for index in missing_indices),
                response=f"[{len(result.vectors)} embedding vectors]",
                prompt_tokens=result.prompt_tokens,
                total_tokens=result.total_tokens,
                latency_s=result.latency_s,
                endpoint=result.endpoint_host,
            )
            for index, vector in zip(missing_indices, result.vectors):
                vectors[index] = vector
                self.ctx.checkpoint.put(keys[index], vector)
        return [list(value or []) for value in vectors]

    def merge(self, left: str, right: str) -> dict[str, Any]:
        key = (
            f"{self.ctx.node_id}::calitree::merge::"
            f"{_hash(self.prompt_version, left, right)}"
        )
        if self.ctx.checkpoint.has(key):
            return self.ctx.checkpoint.get(key)
        query = _prompt("merge_prompts.txt", self.prompt_version).format(
            left=left, right=right
        )
        result = self.optimizer_engine.generate(query)
        self._record(result, "optimizer")
        try:
            parsed = parse_json_object(str(result.get("content") or ""))
        except (ValueError, TypeError):
            parsed = {"conflict": True, "conflict_reason": "invalid merge response", "prompt": ""}
        merged = {
            "conflict": bool(parsed.get("conflict")),
            "conflict_reason": str(parsed.get("conflict_reason") or ""),
            "prompt": str(parsed.get("prompt") or ""),
        }
        self.ctx.checkpoint.put(key, merged)
        return merged


@register
class CaliTreeTrainNodeExecutor(NodeExecutor):
    node_type = "calitree_train"
    category = "node_calibration"
    subcategory = "prompt"
    input_sockets = {
        "samples": "samples",
        "labels": "labels",
        "population_labels": "raw_labels",
        "judge_engine": "engine_config",
        "optimizer_engine": "engine_config",
    }
    output_sockets = {"prompt_tree": "prompt_tree", "calitree_report": "calitree_report"}
    param_schema = {
        "embedding_model": {"type": "string", "default": ""},
        "prompt_version": {
            "type": "enum",
            "options": list(PROMPT_VERSIONS),
            "default": "calitree_v2",
        },
        "max_steps": {"type": "number", "default": 3, "min": 1, "max": 10},
        "merge_acceptance": {"type": "number", "default": 0.8, "min": 0, "max": 1},
        "similarity_start": {"type": "number", "default": 0.9, "min": 0, "max": 1},
        "similarity_decay": {"type": "number", "default": 0.05, "min": 0.01, "max": 1},
        "similarity_floor": {"type": "number", "default": 0.7, "min": 0, "max": 1},
        "warm_start": {"type": "bool", "default": True},
        "merge_validation_cap": {"type": "number", "default": 6, "min": 0},
        "merge_regression_tolerance": {
            "type": "number", "default": 0.05, "min": 0, "max": 1,
        },
        "merge_generalization_floor": {
            "type": "number", "default": 0.8, "min": 0, "max": 1,
        },
        "routing_margin": {"type": "number", "default": 0.02, "min": 0, "max": 1},
        "min_routing_support": {"type": "number", "default": 2, "min": 1},
        "singleton_exact_threshold": {
            "type": "number", "default": 0.995, "min": 0, "max": 1,
        },
        "global_min_validation_gain": {
            "type": "number", "default": 0.0, "min": 0, "max": 1,
        },
        "max_merge_attempts": {
            "type": "number", "default": 20, "min": 0,
        },
        "semantic_premerge_levels": {
            "type": "number", "default": 2, "min": 0, "max": 10,
        },
        "validation_fraction": {
            "type": "number", "default": 0.25, "min": 0, "max": 0.5,
        },
        "split_seed": {"type": "number", "default": 44, "min": 0},
        "run_baselines": {"type": "bool", "default": True},
        "run_conflict_resolver": {"type": "bool", "default": True},
        "conflict_min_support": {"type": "number", "default": 4, "min": 1},
        "conflict_min_gain": {
            "type": "number", "default": 0.0, "min": 0, "max": 1,
        },
        "consensus_min_gain": {
            "type": "number", "default": 0.0, "min": 0, "max": 1,
        },
        "calibration_agreement_filter": {
            "type": "enum",
            "options": ["all", "unanimous"],
            "default": "all",
        },
        "selective_min_consensus_support": {
            "type": "number", "default": 3, "min": 1, "max": 3,
        },
        "selective_editor_min_support": {
            "type": "number", "default": 10, "min": 1,
        },
        "selective_editor_accuracy_threshold": {
            "type": "number", "default": 0.85, "min": 0, "max": 1,
        },
        "editor_prior_threshold": {
            "type": "number", "default": 0.98, "min": 0, "max": 1,
        },
        "editor_prior_min_support": {
            "type": "number", "default": 20, "min": 1,
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        labels = ctx.inputs.get("labels")
        population_labels = ctx.inputs.get("population_labels") or labels
        judge_config = ctx.inputs.get("judge_engine")
        optimizer_config = ctx.inputs.get("optimizer_engine")
        if not all(value is not None for value in (samples, labels, judge_config, optimizer_config)):
            return NodeRunResult(
                status="error",
                error="Cali-Tree Train requires samples, labels, judge_engine, and optimizer_engine",
            )
        embedding_model = str(ctx.params.get("embedding_model") or "").strip()
        if not embedding_model and not ctx.dry_run:
            return NodeRunResult(status="error", error="embedding_model must be configured")
        prompt_version = str(ctx.params.get("prompt_version") or "calitree_v2")
        if prompt_version not in PROMPT_VERSIONS:
            return NodeRunResult(
                status="error",
                error=f"Unknown prompt_version {prompt_version!r}",
            )
        train_ids = sorted(
            item_id for item_id in set(samples) & set(labels)
            if samples[item_id].get("split") == "train" and _target(labels[item_id])
        )
        test_ids = sorted(
            item_id for item_id in set(samples) & set(labels)
            if samples[item_id].get("split") == "test" and _target(labels[item_id])
        )
        fit_ids, validation_ids = _calibration_split(
            train_ids,
            labels,
            validation_fraction=float(ctx.params.get("validation_fraction", 0.25)),
            seed=int(ctx.params.get("split_seed", 44)),
        )
        calibration_agreement_filter = str(
            ctx.params.get("calibration_agreement_filter") or "all"
        )
        if calibration_agreement_filter not in {"all", "unanimous"}:
            return NodeRunResult(
                status="error",
                error=(
                    "calibration_agreement_filter must be one of "
                    "'all' or 'unanimous'"
                ),
            )
        calibration_train_ids = [
            item_id
            for item_id in train_ids
            if (
                calibration_agreement_filter == "all"
                or _human_agreement_bucket(labels[item_id])
                == calibration_agreement_filter
            )
        ]
        calibration_fit_ids, calibration_validation_ids = (
            _calibration_split(
                calibration_train_ids,
                labels,
                validation_fraction=float(
                    ctx.params.get("validation_fraction", 0.25)
                ),
                seed=int(ctx.params.get("split_seed", 44)),
            )
        )
        if train_ids and not calibration_train_ids:
            return NodeRunResult(
                status="error",
                error=(
                    "Cali-Tree found no training labels matching "
                    f"calibration_agreement_filter={calibration_agreement_filter!r}"
                ),
            )
        if not train_ids and not ctx.dry_run:
            return NodeRunResult(
                status="error",
                error="Cali-Tree found no labelled training cases (expected split='train')",
            )
        max_steps = int(ctx.params.get("max_steps") or 3)
        max_tokens = int(optimizer_config.get("max_tokens") or 4096)
        budget = max_steps * len(train_ids) * max_tokens
        fit_tasks = {
            _task_uid(item_id, samples[item_id], labels[item_id])
            for item_id in fit_ids
        }
        if ctx.dry_run:
            return NodeRunResult(
                outputs={"prompt_tree": {}, "calitree_report": {}},
                meta={
                    "dry_run": True,
                    "n_train": len(train_ids),
                    "n_fit": len(fit_ids),
                    "n_fit_tasks": len(fit_tasks),
                    "n_validation": len(validation_ids),
                    "n_calibration_train": len(
                        calibration_train_ids
                    ),
                    "n_calibration_fit": len(calibration_fit_ids),
                    "n_calibration_validation": len(
                        calibration_validation_ids
                    ),
                    "calibration_agreement_filter": (
                        calibration_agreement_filter
                    ),
                    "n_test": len(test_ids),
                    "optimizer_completion_token_budget": budget,
                    "estimated_calls": {
                        "warm_start_judge_max": (
                            len(fit_ids) * (max_steps + 1)
                        ),
                        "task_leaf_optimizer_max": (
                            len(fit_tasks) * max_steps
                        ),
                        "task_leaf_judge_max": (
                            len(fit_ids) * max_steps
                        ),
                        "component_extraction_max": (
                            len(fit_tasks)
                            + int(ctx.params.get("max_merge_attempts", 20))
                            + 1
                        ),
                        "merge_optimizer_max": (
                            int(ctx.params.get("max_merge_attempts", 20))
                            * (max_steps + 1)
                        ),
                        "test_judge_min": len(test_ids),
                        "consensus_judge_max": (
                            3 * (len(train_ids) + len(test_ids))
                            if bool(ctx.params.get("run_conflict_resolver", True))
                            else 0
                        ),
                    },
                },
            )
        try:
            require_live(ctx.allow_live, context="Cali-Tree training")
            judge_engine = _engine_from(judge_config, ctx)
            optimizer_engine = _engine_from(optimizer_config, ctx)
        except (ValueError, RuntimeError) as exc:
            return NodeRunResult(status="error", error=str(exc))
        runtime = _CaliTreeRuntime(
            ctx,
            judge_engine=judge_engine,
            optimizer_engine=optimizer_engine,
            embedding_model=embedding_model,
            optimizer_budget=budget,
            prompt_version=prompt_version,
            concurrency=int(judge_config.get("concurrency") or 1),
        )
        targets = {item_id: _target(labels[item_id]) for item_id in fit_ids}
        builder = CaliTreeBuilder(
            judge=runtime.judge,
            judge_many=runtime.judge_many,
            optimize=runtime.optimize,
            extract_components=runtime.extract,
            embed=runtime.embed,
            merge_prompts=runtime.merge,
            format_feedback=lambda ids, case_samples, case_targets, results: _format_feedback(
                ids,
                case_samples,
                case_targets,
                results,
                prompt_version=prompt_version,
            ),
            max_steps=max_steps,
            merge_acceptance=float(ctx.params.get("merge_acceptance") or 0.8),
            similarity_start=float(ctx.params.get("similarity_start") or 0.9),
            similarity_decay=float(ctx.params.get("similarity_decay") or 0.05),
            similarity_floor=float(ctx.params.get("similarity_floor") or 0.7),
            warm_start=bool(ctx.params.get("warm_start", True)),
            merge_validation_cap=int(ctx.params.get("merge_validation_cap", 6)),
            merge_regression_tolerance=float(
                ctx.params.get("merge_regression_tolerance", 0.05)
            ),
            merge_generalization_floor=float(
                ctx.params.get("merge_generalization_floor", 0.8)
            ),
            routing_margin=float(ctx.params.get("routing_margin", 0.02)),
            min_routing_support=int(ctx.params.get("min_routing_support", 2)),
            singleton_exact_threshold=float(
                ctx.params.get("singleton_exact_threshold", 0.995)
            ),
            global_min_validation_gain=float(
                ctx.params.get("global_min_validation_gain", 0.0)
            ),
            max_merge_attempts=int(ctx.params.get("max_merge_attempts", 20)),
            semantic_premerge_levels=int(
                ctx.params.get("semantic_premerge_levels", 2)
            ),
            progress=ctx.progress_cb,
        )
        initial_prompt = _prompt("initial_rubric.txt", prompt_version)
        tree = builder.build(
            initial_prompt=initial_prompt,
            samples={item_id: samples[item_id] for item_id in fit_ids},
            targets=targets,
            routing_texts={
                item_id: _routing_text(samples[item_id]) for item_id in fit_ids
            },
            validation_samples={
                item_id: samples[item_id] for item_id in validation_ids
            },
            validation_targets={
                item_id: _target(labels[item_id]) for item_id in validation_ids
            },
            validation_routing_texts={
                item_id: _routing_text(samples[item_id]) for item_id in validation_ids
            },
            semantic_groups={
                item_id: _semantic_edit_type(samples[item_id])
                for item_id in fit_ids
            },
            leaf_groups={
                item_id: _task_uid(
                    item_id, samples[item_id], labels[item_id]
                )
                for item_id in fit_ids
            },
        )
        tree["embedding_model"] = embedding_model
        tree["prompt_version"] = prompt_version
        all_ids = train_ids + test_ids
        routing_vectors = runtime.embed(
            [_routing_text(samples[item_id]) for item_id in all_ids]
        )
        routed_prompts = {
            item_id: route_prompt(tree, vector)
            for item_id, vector in zip(all_ids, routing_vectors)
        }
        results_by_prompt: dict[str, dict[str, dict[str, Any]]] = {}
        prompt_routes: dict[str, dict[str, Any]] = {}
        for item_id, routed in routed_prompts.items():
            prompt = str(routed["prompt"])
            results_by_prompt.setdefault(prompt, {})[item_id] = samples[item_id]
            prompt_routes[item_id] = routed
        judged: dict[str, dict[str, Any]] = {}
        for prompt, prompt_samples in results_by_prompt.items():
            judged.update(runtime.judge_many(prompt, prompt_samples))
        tree_results = {
            item_id: {
                **judged[item_id],
                "routed_node": prompt_routes[item_id]["id"],
                "route_path": prompt_routes[item_id]["route_path"],
                "route_similarity": prompt_routes[item_id]["route_similarity"],
            }
            for item_id in all_ids
        }
        run_baselines = bool(ctx.params.get("run_baselines", True))
        run_conflict_resolver = bool(
            ctx.params.get("run_conflict_resolver", True)
        )
        initial_results: dict[str, dict[str, Any]] = {}
        textgrad_results: dict[str, dict[str, Any]] = {}
        if run_baselines or run_conflict_resolver:
            all_samples = {
                item_id: samples[item_id] for item_id in all_ids
            }
            initial_results = runtime.judge_many(initial_prompt, all_samples)
            textgrad_prompt = str(
                tree.get("warm_start_prompt") or initial_prompt
            )
            textgrad_results = runtime.judge_many(
                textgrad_prompt, all_samples
            )
        if run_conflict_resolver:
            critic_prompt = _prompt("conflict_resolver.txt", "calitree_v2")
            global_node = (tree.get("nodes") or {}).get((tree.get("roots") or [""])[0]) or {}
            policy_prompt = str(global_node.get("prompt") or initial_prompt)
            policy_base_results = (
                initial_results
                if policy_prompt == initial_prompt
                else runtime.judge_many(
                    policy_prompt,
                    {item_id: samples[item_id] for item_id in all_ids},
                )
            )
            critic_results = runtime.critic_many(
                critic_prompt,
                {item_id: samples[item_id] for item_id in all_ids},
                policy_base_results,
            )
            all_targets = {item_id: _target(labels[item_id]) for item_id in all_ids}
            conflict_policy = _fit_conflict_policy(
                policy_base_results,
                critic_results,
                samples,
                all_targets,
                calibration_train_ids,
                min_support=int(ctx.params.get("conflict_min_support", 4)),
                min_gain=float(ctx.params.get("conflict_min_gain", 0.0)),
            )
            candidates_by_id = {
                item_id: {
                    "initial": initial_results[item_id],
                    "textgrad": textgrad_results[item_id],
                    "critic": critic_results[item_id],
                }
                for item_id in all_ids
            }
            consensus_calibrator = _select_consensus_calibrator(
                fit_ids=calibration_fit_ids,
                validation_ids=calibration_validation_ids,
                train_ids=calibration_train_ids,
                candidates=candidates_by_id,
                samples=samples,
                targets=all_targets,
                min_gain=float(
                    ctx.params.get("consensus_min_gain", 0.0)
                ),
            )
            conflict_policy["base_prompt_hash"] = _hash(policy_prompt)
            conflict_policy["base_distribution"] = "global_root"
            conflict_policy["strategy"] = (
                "hierarchical_consensus_calibration"
            )
            conflict_policy["tie_label"] = "partial"
            conflict_policy["critic_base_prompt"] = policy_prompt
            conflict_policy["consensus_calibrator"] = (
                consensus_calibrator
            )
            for item_id in all_ids:
                base = tree_results[item_id]
                selected = _apply_consensus_calibrator(
                    consensus_calibrator,
                    sample=samples[item_id],
                    candidates=candidates_by_id[item_id],
                    fallback=base,
                )
                tree_results[item_id] = {
                    **selected,
                    "pre_resolution_label": base.get("label"),
                    "pre_resolution_rationale": base.get("rationale"),
                    "routed_node": base["routed_node"],
                    "route_path": base["route_path"],
                    "route_similarity": base["route_similarity"],
                    "conflict_action": selected.get(
                        "calibration_action"
                    ),
                    "conflict_rule": selected.get(
                        "calibration_rule"
                    ),
                    "policy_base_label": policy_base_results[item_id].get("label"),
                }
            tree["conflict_policy"] = conflict_policy
            tree["conflict_prompt"] = critic_prompt
        prior_population_labels = population_labels
        if calibration_agreement_filter != "all":
            prior_population_labels = {
                item_id: (
                    label
                    if _human_agreement_bucket(label)
                    == calibration_agreement_filter
                    else {**label, "split": "excluded"}
                )
                for item_id, label in population_labels.items()
                if isinstance(label, dict)
            }
        editor_prior_policy = _fit_editor_prior(
            prior_population_labels,
            threshold=float(ctx.params.get("editor_prior_threshold", 0.98)),
            min_support=int(ctx.params.get("editor_prior_min_support", 20)),
        )
        for item_id in all_ids:
            prior_label, prior_rule = _editor_prior_action(
                editor_prior_policy, samples[item_id]
            )
            if prior_label in {"no", "partial", "yes"}:
                previous = tree_results[item_id]
                tree_results[item_id] = {
                    **previous,
                    "pre_prior_label": previous.get("label"),
                    "label": prior_label,
                    "prior_action": "override",
                    "prior_rule": prior_rule,
                }
            else:
                tree_results[item_id]["prior_action"] = "base"
                tree_results[item_id]["prior_rule"] = prior_rule
        tree["editor_prior_policy"] = editor_prior_policy
        all_targets = {item_id: _target(labels[item_id]) for item_id in all_ids}
        selective_policy = _fit_selective_policy(
            tree_results,
            samples,
            all_targets,
            calibration_train_ids,
            minimum_consensus_support=int(
                ctx.params.get("selective_min_consensus_support", 3)
            ),
            editor_min_support=int(
                ctx.params.get("selective_editor_min_support", 10)
            ),
            editor_accuracy_threshold=float(
                ctx.params.get(
                    "selective_editor_accuracy_threshold", 0.85
                )
            ),
        )
        tree["selective_policy"] = selective_policy
        for item_id in all_ids:
            editor = str(samples[item_id].get("editor") or "unknown")
            branch = (selective_policy.get("editors") or {}).get(editor) or {}
            support_ok = int(
                tree_results[item_id].get("consensus_support") or 0
            ) >= int(selective_policy["minimum_consensus_support"])
            tree_results[item_id]["selective_accepted"] = (
                support_ok and bool(branch.get("active"))
            )
            tree_results[item_id]["selective_policy_version"] = (
                selective_policy["version"]
            )
        # The routed judge node commonly consumes the same samples immediately after
        # training. Preserve those exact, already-paid judgments so evaluation is both
        # reproducible and free of duplicate model calls. Cache hits are accepted only
        # when the newly routed prompt has the identical content hash.
        tree["prediction_cache"] = {
            item_id: {
                "prompt_hash": _hash("calitree_prediction", routed_prompts[item_id]["prompt"]),
                "result": tree_results[item_id],
            }
            for item_id in all_ids
        }
        tree_predictions = {item_id: row["label"] for item_id, row in tree_results.items()}
        report: dict[str, Any] = {
            "version": "calitree-v2",
            "prompt_version": prompt_version,
            "n_train": len(train_ids),
            "n_fit": len(fit_ids),
            "n_validation": len(validation_ids),
            "calibration_training": {
                "agreement_filter": calibration_agreement_filter,
                "n_train": len(calibration_train_ids),
                "n_fit": len(calibration_fit_ids),
                "n_validation": len(calibration_validation_ids),
            },
            "n_test": len(test_ids),
            "optimizer_completion_token_budget": budget,
            "usage": runtime.usage,
            "tree_stats": tree["stats"],
            "conflict_policy": tree.get("conflict_policy"),
            "consensus_calibrator": (
                (tree.get("conflict_policy") or {}).get(
                    "consensus_calibrator"
                )
            ),
            "editor_prior_policy": tree.get("editor_prior_policy"),
            "selective_policy": selective_policy,
            "timeline": tree["timeline"],
            "calitree": {
                "train": _metrics_with_human_agreement(
                    {i: all_targets[i] for i in train_ids},
                    {i: tree_predictions[i] for i in train_ids},
                    samples,
                    labels,
                ),
                "test": _metrics_with_human_agreement(
                    {i: all_targets[i] for i in test_ids},
                    {i: tree_predictions[i] for i in test_ids},
                    samples,
                    labels,
                ),
            },
            "selective": {
                "train": _selective_metrics(
                    {i: all_targets[i] for i in train_ids},
                    {i: tree_predictions[i] for i in train_ids},
                    samples,
                    labels,
                    tree_results,
                    policy=selective_policy,
                ),
                "test": _selective_metrics(
                    {i: all_targets[i] for i in test_ids},
                    {i: tree_predictions[i] for i in test_ids},
                    samples,
                    labels,
                    tree_results,
                    policy=selective_policy,
                ),
            },
            "predictions": tree_results,
            "cases": {
                item_id: {
                    "item_id": item_id,
                    "instruction": str(
                        (samples[item_id].get("input") or {}).get("instruction") or ""
                    ),
                    "source_image_path": str(
                        (samples[item_id].get("input") or {}).get("source_image_path") or ""
                    ),
                    "edited_image_path": str(
                        (samples[item_id].get("output") or {}).get("edited_image_path") or ""
                    ),
                    "editor": samples[item_id].get("editor"),
                    "split": samples[item_id].get("split"),
                    "target_label": all_targets[item_id],
                }
                for item_id in all_ids
            },
        }
        if run_baselines:
            # The builder's global warm start is the matched-budget TextGrad baseline and
            # the initialization for every leaf. Reusing it avoids training the same
            # baseline twice and makes tree gains attributable to specialization/merging.
            for name, results in (
                ("initial", initial_results),
                ("textgrad", textgrad_results),
            ):
                predictions = {item_id: row["label"] for item_id, row in results.items()}
                report[name] = {
                    "train": _metrics_with_human_agreement(
                        {i: all_targets[i] for i in train_ids},
                        {i: predictions[i] for i in train_ids},
                        samples,
                        labels,
                    ),
                    "test": _metrics_with_human_agreement(
                        {i: all_targets[i] for i in test_ids},
                        {i: predictions[i] for i in test_ids},
                        samples,
                        labels,
                    ),
                }
        ctx.run.write_json(f"calitree_tree_{ctx.node_id}.json", tree)
        ctx.run.write_json(f"calitree_{ctx.node_id}.json", report)
        return NodeRunResult(
            outputs={"prompt_tree": tree, "calitree_report": report},
            meta={
                "n_train": len(train_ids),
                "n_fit": len(fit_ids),
                "n_validation": len(validation_ids),
                "n_test": len(test_ids),
                "usage": runtime.usage,
            },
        )


@register
class CaliTreeJudgeNodeExecutor(NodeExecutor):
    node_type = "calitree_judge"
    category = "node_vejudge"
    input_sockets = {
        "samples": "samples",
        "prompt_tree": "prompt_tree",
        "judge_engine": "engine_config",
    }
    output_sockets = {"judge_result": "judge_result"}
    param_schema: dict[str, Any] = {}

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        tree = ctx.inputs.get("prompt_tree")
        engine_config = ctx.inputs.get("judge_engine")
        if samples is None or tree is None or engine_config is None:
            return NodeRunResult(
                status="error",
                error="Cali-Tree Judge requires samples, prompt_tree, and judge_engine",
            )
        if ctx.dry_run:
            return NodeRunResult(
                outputs={"judge_result": {}},
                meta={"dry_run": True, "estimated_calls": len(samples)},
            )
        try:
            require_live(ctx.allow_live, context="Cali-Tree routed judging")
            engine = _engine_from(engine_config, ctx)
        except (ValueError, RuntimeError) as exc:
            return NodeRunResult(status="error", error=str(exc))
        runtime = _CaliTreeRuntime(
            ctx,
            judge_engine=engine,
            optimizer_engine=engine,
            embedding_model=str(tree.get("embedding_model") or ""),
            optimizer_budget=0,
            prompt_version=str(tree.get("prompt_version") or "calitree_v2"),
            concurrency=int(engine_config.get("concurrency") or 1),
        )
        if not runtime.embedding_model:
            return NodeRunResult(status="error", error="prompt_tree has no embedding_model")
        output: dict[str, Any] = {}
        routed_by_item: dict[str, dict[str, Any]] = {}
        grouped: dict[str, dict[str, dict[str, Any]]] = {}
        cached_results: dict[str, dict[str, Any]] = {}
        prediction_cache = tree.get("prediction_cache") or {}
        item_ids = sorted(samples)
        routing_vectors = runtime.embed(
            [_routing_text(samples[item_id]) for item_id in item_ids]
        )
        for item_id, vector in zip(item_ids, routing_vectors):
            routed = route_prompt(tree, vector)
            routed_by_item[item_id] = routed
            prompt = str(routed["prompt"])
            cached = prediction_cache.get(item_id) or {}
            cached_result = cached.get("result")
            if (
                cached.get("prompt_hash")
                == _hash("calitree_prediction", prompt)
                and isinstance(cached_result, dict)
                and cached_result.get("label") in {"no", "partial", "yes"}
            ):
                cached_results[item_id] = cached_result
            else:
                grouped.setdefault(prompt, {})[item_id] = samples[item_id]
        judged: dict[str, dict[str, Any]] = {}
        for prompt, prompt_samples in grouped.items():
            judged.update(runtime.judge_many(prompt, prompt_samples))
        judged.update(cached_results)
        uncached_ids = [item_id for item_id in item_ids if item_id not in cached_results]
        conflict_policy = tree.get("conflict_policy")
        conflict_prompt = str(tree.get("conflict_prompt") or "")
        if conflict_policy and conflict_prompt and uncached_ids:
            global_node = (
                (tree.get("nodes") or {}).get((tree.get("roots") or [""])[0]) or {}
            )
            global_prompt = str(global_node.get("prompt") or "")
            policy_base_results = {item_id: judged[item_id] for item_id in uncached_ids}
            needs_global = {
                item_id: samples[item_id]
                for item_id in uncached_ids
                if str(routed_by_item[item_id].get("prompt") or "") != global_prompt
            }
            if needs_global:
                policy_base_results.update(
                    runtime.judge_many(global_prompt, needs_global)
                )
            critic_results = runtime.critic_many(
                conflict_prompt,
                {item_id: samples[item_id] for item_id in uncached_ids},
                policy_base_results,
            )
            consensus_initial_results: dict[str, dict[str, Any]] = {}
            consensus_textgrad_results: dict[str, dict[str, Any]] = {}
            consensus_strategy = str(
                conflict_policy.get("strategy") or ""
            )
            if consensus_strategy in {
                "three_way_consensus",
                "hierarchical_consensus_calibration",
            }:
                prompt_version = str(tree.get("prompt_version") or "calitree_v2")
                consensus_initial_prompt = _prompt(
                    "initial_rubric.txt", prompt_version
                )
                uncached_samples = {
                    item_id: samples[item_id] for item_id in uncached_ids
                }
                consensus_initial_results = runtime.judge_many(
                    consensus_initial_prompt, uncached_samples
                )
                consensus_textgrad_results = runtime.judge_many(
                    str(
                        tree.get("warm_start_prompt")
                        or consensus_initial_prompt
                    ),
                    uncached_samples,
                )
            for item_id in uncached_ids:
                base = judged[item_id]
                if consensus_strategy in {
                    "three_way_consensus",
                    "hierarchical_consensus_calibration",
                }:
                    candidates = {
                        "initial": consensus_initial_results[item_id],
                        "textgrad": consensus_textgrad_results[item_id],
                        "critic": critic_results[item_id],
                    }
                    if (
                        consensus_strategy
                        == "hierarchical_consensus_calibration"
                    ):
                        selected = _apply_consensus_calibrator(
                            conflict_policy.get(
                                "consensus_calibrator"
                            ) or {},
                            sample=samples[item_id],
                            candidates=candidates,
                            fallback=base,
                        )
                    else:
                        selected = _consensus_result(
                            candidates,
                            fallback=base,
                            tie_label=str(
                                conflict_policy.get("tie_label")
                                or "partial"
                            ),
                        )
                    judged[item_id] = {
                        **selected,
                        "pre_resolution_label": base.get("label"),
                        "pre_resolution_rationale": base.get("rationale"),
                        "conflict_action": selected.get(
                            "calibration_action", "consensus"
                        ),
                        "conflict_rule": selected.get(
                            "calibration_rule",
                            "three_way_majority",
                        ),
                        "policy_base_label": policy_base_results[item_id].get("label"),
                    }
                else:
                    action, rule = _conflict_action(
                        conflict_policy,
                        samples[item_id],
                        str(policy_base_results[item_id].get("label") or ""),
                    )
                    if action == "critic" and critic_results[item_id].get("valid"):
                        judged[item_id] = {
                            **critic_results[item_id],
                            "pre_resolution_label": base.get("label"),
                            "pre_resolution_rationale": base.get("rationale"),
                            "conflict_action": action,
                            "conflict_rule": rule,
                            "policy_base_label": policy_base_results[item_id].get("label"),
                        }
                    else:
                        base["critic_label"] = critic_results[item_id].get("label")
                        base["critic_rationale"] = critic_results[item_id].get("rationale")
                        base["conflict_action"] = "base"
                        base["conflict_rule"] = rule
                        base["policy_base_label"] = policy_base_results[item_id].get("label")
        editor_prior_policy = tree.get("editor_prior_policy") or {}
        selective_policy = tree.get("selective_policy") or {}
        for item_id in uncached_ids:
            prior_label, prior_rule = _editor_prior_action(
                editor_prior_policy, samples[item_id]
            )
            if prior_label in {"no", "partial", "yes"}:
                judged[item_id]["pre_prior_label"] = judged[item_id].get("label")
                judged[item_id]["label"] = prior_label
                judged[item_id]["prior_action"] = "override"
                judged[item_id]["prior_rule"] = prior_rule
            else:
                judged[item_id]["prior_action"] = "base"
                judged[item_id]["prior_rule"] = prior_rule
            if selective_policy:
                editor = str(samples[item_id].get("editor") or "unknown")
                branch = (
                    selective_policy.get("editors") or {}
                ).get(editor) or {}
                support_ok = int(
                    judged[item_id].get("consensus_support") or 0
                ) >= int(
                    selective_policy.get(
                        "minimum_consensus_support", 3
                    )
                )
                judged[item_id]["selective_accepted"] = (
                    support_ok and bool(branch.get("active"))
                )
                judged[item_id]["selective_policy_version"] = (
                    selective_policy.get("version")
                )
        for item_id in item_ids:
            routed = routed_by_item[item_id]
            result = judged[item_id]
            parsed_output = dict(result.get("parsed") or {})
            parsed_output.update({
                "label": result["label"],
                "rationale": result["rationale"],
            })
            output[item_id] = {"calitree": {
                **result,
                "parsed": parsed_output,
                "routed_node": routed["id"],
                "route_path": routed["route_path"],
                "route_similarity": routed["route_similarity"],
            }}
        return NodeRunResult(
            outputs={"judge_result": output},
            meta={
                "usage": runtime.usage,
                "cache_hits": len(cached_results),
                "base_judge_calls": len(item_ids) - len(cached_results),
                "judge_calls": runtime.usage["judge_calls"],
            },
        )


@register
class CaliTreeEvalNodeExecutor(NodeExecutor):
    node_type = "calitree_eval"
    category = "node_eval"
    input_sockets = {"judge_result": "judge_result", "labels": "labels", "samples": "samples"}
    output_sockets = {"metrics_report": "metrics_report"}
    param_schema: dict[str, Any] = {}

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        results = ctx.inputs.get("judge_result")
        labels = ctx.inputs.get("labels")
        samples = ctx.inputs.get("samples")
        if results is None or labels is None or samples is None:
            return NodeRunResult(
                status="error", error="Cali-Tree Eval requires judge_result, labels, and samples"
            )
        ids = sorted(set(results) & set(labels) & set(samples))
        targets = {item_id: _target(labels[item_id]) for item_id in ids}
        predictions = {
            item_id: str((results[item_id].get("calitree") or {}).get("label") or "")
            for item_id in ids
        }
        result_rows = {
            item_id: results[item_id].get("calitree") or {}
            for item_id in ids
        }
        report: dict[str, Any] = {
            "overall": _metrics_with_human_agreement(
                targets, predictions, samples, labels
            ),
            "selective": {
                "overall": _selective_metrics(
                    targets,
                    predictions,
                    samples,
                    labels,
                    result_rows,
                )
            },
        }
        for split in ("train", "test"):
            split_ids = [item_id for item_id in ids if samples[item_id].get("split") == split]
            report[split] = _metrics_with_human_agreement(
                {i: targets[i] for i in split_ids},
                {i: predictions[i] for i in split_ids},
                samples,
                labels,
            )
            report["selective"][split] = _selective_metrics(
                {i: targets[i] for i in split_ids},
                {i: predictions[i] for i in split_ids},
                samples,
                labels,
                result_rows,
            )
        ctx.run.write_json(f"calitree_eval_{ctx.node_id}.json", report)
        return NodeRunResult(outputs={"metrics_report": report}, meta={"n_items": len(ids)})
