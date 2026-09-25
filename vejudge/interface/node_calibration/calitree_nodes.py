"""Workflow executors for training, routing, and evaluating Cali-Tree prompt hierarchies."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from ...core.calibration.calitree import CaliTreeBuilder, classification_metrics, route_prompt
from ...core.calibration.rubric_lite import (
    DEFAULT_ORDINAL_THRESHOLDS,
    RubricLiteLearner,
    apply_ordinal_thresholds,
    ordinal_label,
)
from ...core.calibration.textgrad_adapter import textgrad_update
from ...core.judge.parse import parse_json_object
from ...lm_engine import get_engine, load_creds, require_live
from ...lm_engine import openai_compat
from ...lm_engine.health import reorder_creds_by_health
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


def _failure_mode_signature(
    base_label: str, target: str, family: str
) -> str:
    """A residual signature grouping cases by how the base rubric is wrong.

    Uses the base prediction and the training target, so leaves specialize a coherent
    failure mode (e.g. ``no->partial`` for the operation family) rather than an instruction
    cluster. The target is a training-time input only; inference routing never reads it.
    """
    pred = base_label if base_label in {"no", "partial", "yes"} else "invalid"
    return f"{family}:{pred}->{target}"


def _failure_mode_groups(
    base_results: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    ids: list[str],
) -> dict[str, str]:
    return {
        item_id: _failure_mode_signature(
            str((base_results.get(item_id) or {}).get("label") or ""),
            targets[item_id],
            _semantic_edit_type(samples[item_id]),
        )
        for item_id in ids
    }


_RESIDUAL_CONTEXT_LEVELS = (
    "editor_operation_prediction",
    "editor_prediction",
    "operation_prediction",
    "prediction",
)


def _residual_context_key(
    level: str, sample: dict[str, Any], base_label: str
) -> str:
    """Return a target-blind key for prediction-conditioned specialization.

    The top judge's prediction is available at both training and inference.  Adding
    editor/operation context lets a leaf learn a local correction without using the
    hidden target label as a routing feature.
    """
    prediction = base_label if base_label in {"no", "partial", "yes"} else "invalid"
    editor = str(sample.get("editor") or sample.get("model") or "unknown")
    operation = _semantic_edit_type(sample)
    values = {
        "editor_operation_prediction": (editor, operation, prediction),
        "editor_prediction": (editor, prediction),
        "operation_prediction": (operation, prediction),
        "prediction": (prediction,),
    }
    if level not in values:
        raise ValueError(f"Unknown residual context level {level!r}")
    # JSON avoids ambiguous separators when editor names or future feature values contain
    # punctuation. sort_keys is unnecessary for a list but separators keep tree ids compact.
    return f"{level}:{json.dumps(values[level], separators=(',', ':'))}"


def _residual_context_keys(
    sample: dict[str, Any], base_label: str
) -> list[str]:
    """Return observable routing keys from most specific to broadest."""
    return [
        _residual_context_key(level, sample, base_label)
        for level in _RESIDUAL_CONTEXT_LEVELS
    ]


def _fit_residual_context_partition(
    *,
    fit_base_results: dict[str, dict[str, Any]],
    validation_base_results: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    fit_ids: list[str],
    validation_ids: list[str],
    min_fit_support: int,
    min_validation_support: int,
) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
    """Build a disjoint, support-aware residual leaf partition.

    A case takes the most specific observable context with enough fit *and* held-out
    support.  If no context clears both gates, it backs off to the broadest prediction
    bucket.  This is a small decision tree whose split/pruning decisions use no targets;
    targets are consumed later only for prompt optimization and held-out acceptance.
    """
    min_fit_support = max(1, int(min_fit_support))
    min_validation_support = max(1, int(min_validation_support))
    fit_candidates = {
        item_id: _residual_context_keys(
            samples[item_id],
            str((fit_base_results.get(item_id) or {}).get("label") or ""),
        )
        for item_id in fit_ids
    }
    validation_candidates = {
        item_id: _residual_context_keys(
            samples[item_id],
            str((validation_base_results.get(item_id) or {}).get("label") or ""),
        )
        for item_id in validation_ids
    }
    fit_counts = Counter(
        key for keys in fit_candidates.values() for key in keys
    )
    validation_counts = Counter(
        key for keys in validation_candidates.values() for key in keys
    )

    def select(keys: list[str]) -> str:
        for key in keys:
            if (
                fit_counts[key] >= min_fit_support
                and validation_counts[key] >= min_validation_support
            ):
                return key
        # Every case has a prediction key. Keeping that deterministic coarse leaf allows
        # the builder to optimize it, while its own held-out guard still prevents routing
        # if the cohort is too small or fails to improve the top judge.
        return keys[-1]

    fit_groups = {
        item_id: select(keys) for item_id, keys in fit_candidates.items()
    }
    group_ids = set(fit_groups.values())

    def select_existing(keys: list[str]) -> str:
        return next((key for key in keys if key in group_ids), keys[-1])

    validation_groups = {
        item_id: select_existing(keys)
        for item_id, keys in validation_candidates.items()
    }
    policy = {
        "version": "prediction-conditioned-residual-v1",
        "levels": list(_RESIDUAL_CONTEXT_LEVELS),
        "min_fit_support": min_fit_support,
        "min_validation_support": min_validation_support,
        "group_ids": sorted(group_ids),
        "fit_support": {
            key: sum(group == key for group in fit_groups.values())
            for key in sorted(group_ids)
        },
        "validation_support": {
            key: sum(group == key for group in validation_groups.values())
            for key in sorted(group_ids)
        },
        "target_blind": True,
    }
    return fit_groups, validation_groups, policy


def _fit_pareto_prompt_cascade(
    *,
    initial_results: dict[str, dict[str, Any]],
    optimized_results: dict[str, dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    targets: dict[str, str],
    fit_ids: list[str],
    validation_ids: list[str],
    min_fit_support: int,
) -> dict[str, Any]:
    """Select optimized-prompt routes that Pareto-dominate the top prompt.

    This is the optimize→merge bridge for the residual tree: the fixed top prompt first
    predicts a label, then a globally optimized prompt is reused only on observable cohorts
    where it fixes at least one fit error, introduces no fit regression, and introduces no
    held-out regression. A zero-support validation cohort is recorded explicitly and is
    allowed only after the stronger per-example fit dominance and support gates pass.
    """
    min_fit_support = max(1, int(min_fit_support))
    candidate_ids = sorted(set(fit_ids) | set(validation_ids))
    keys_by_id = {
        item_id: _residual_context_keys(
            samples[item_id],
            str((initial_results.get(item_id) or {}).get("label") or ""),
        )
        for item_id in candidate_ids
    }
    # Prefer broad, reusable corrections. More-specific rules are retained only when no
    # accepted ancestor already makes the same optimized-prompt decision.
    accepted: dict[str, dict[str, Any]] = {}
    accepted_broad_values: set[tuple[str, str]] = set()
    for level_index in reversed(range(len(_RESIDUAL_CONTEXT_LEVELS))):
        level = _RESIDUAL_CONTEXT_LEVELS[level_index]
        keys = sorted({keys_by_id[item_id][level_index] for item_id in candidate_ids})
        for key in keys:
            fit_group = [item_id for item_id in fit_ids if keys_by_id[item_id][level_index] == key]
            validation_group = [
                item_id
                for item_id in validation_ids
                if keys_by_id[item_id][level_index] == key
            ]
            if len(fit_group) < min_fit_support:
                continue

            def transitions(ids: list[str]) -> tuple[int, int, int, int]:
                improvements = regressions = initial_correct = optimized_correct = 0
                for item_id in ids:
                    initial_ok = initial_results[item_id].get("label") == targets[item_id]
                    optimized_ok = optimized_results[item_id].get("label") == targets[item_id]
                    initial_correct += int(initial_ok)
                    optimized_correct += int(optimized_ok)
                    improvements += int(optimized_ok and not initial_ok)
                    regressions += int(initial_ok and not optimized_ok)
                return improvements, regressions, initial_correct, optimized_correct

            fit_improvements, fit_regressions, fit_initial, fit_optimized = transitions(fit_group)
            val_improvements, val_regressions, val_initial, val_optimized = transitions(
                validation_group
            )
            if fit_improvements < 1 or fit_regressions or val_regressions:
                continue
            # If a broader key for this same top prediction is already accepted, the
            # narrower rule cannot change the action and would only inflate the tree.
            prediction = str(
                (initial_results.get(fit_group[0]) or {}).get("label") or "invalid"
            )
            if ("prediction", prediction) in accepted_broad_values:
                continue
            accepted[key] = {
                "level": level,
                "fit_ids": sorted(fit_group),
                "fit_support": len(fit_group),
                "fit_improvements": fit_improvements,
                "fit_regressions": fit_regressions,
                "fit_initial_correct": fit_initial,
                "fit_optimized_correct": fit_optimized,
                "validation_support": len(validation_group),
                "validation_improvements": val_improvements,
                "validation_regressions": val_regressions,
                "validation_initial_correct": val_initial,
                "validation_optimized_correct": val_optimized,
            }
            if level == "prediction":
                accepted_broad_values.add(("prediction", prediction))
    return {
        "version": "pareto-prompt-cascade-v1",
        "min_fit_support": min_fit_support,
        "selection_split": "fit_plus_internal_validation_guard",
        "rules": accepted,
    }


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


def _rating_target(sc: Any) -> str:
    try:
        value = float(sc)
    except (TypeError, ValueError):
        return ""
    if math.isclose(value, 0.0):
        return "no"
    if math.isclose(value, 0.5):
        return "partial"
    if math.isclose(value, 1.0):
        return "yes"
    return ""


def _human_label_reliability(
    targets: dict[str, str],
    predictions: dict[str, str],
    labels: dict[str, Any],
) -> dict[str, Any]:
    """Describe the reliability ceiling implied by the individual SC ratings.

    ``modal_rater_agreement_ceiling`` is the best expected agreement with a
    randomly selected annotator if an oracle could emit each item's modal
    rating. It is not a ceiling on agreement with the released median label.
    """
    label_names = ("no", "partial", "yes")
    rows: list[dict[str, Any]] = []
    for item_id in sorted(set(targets) & set(predictions)):
        label = labels.get(item_id)
        raw_ratings = label.get("ratings") if isinstance(label, dict) else None
        rating_labels = [
            mapped
            for rating in (raw_ratings or [])
            if isinstance(rating, dict)
            for mapped in [_rating_target(rating.get("sc"))]
            if mapped
        ]
        if not rating_labels:
            continue
        counts = Counter(rating_labels)
        n_raters = len(rating_labels)
        probabilities = [count / n_raters for count in counts.values()]
        entropy = -sum(
            probability * math.log2(probability)
            for probability in probabilities
        )
        ordered = sorted(
            ({"no": 0, "partial": 1, "yes": 2}[name] for name in rating_labels)
        )
        median_label = (
            label_names[ordered[len(ordered) // 2]]
            if len(ordered) % 2 == 1
            else ""
        )
        target = targets[item_id]
        prediction = predictions[item_id]
        rows.append({
            "target": target,
            "n_raters": n_raters,
            "unanimous": len(counts) == 1,
            "target_has_majority_support": counts[target] > n_raters / 2,
            "target_matches_rating_median": median_label == target,
            "modal_rater_support": max(counts.values()) / n_raters,
            "prediction_rater_support": counts[prediction] / n_raters,
            "entropy_bits": entropy,
        })

    def summarize(selected: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(selected)
        if not n:
            return {"n": 0}

        def mean(key: str) -> float:
            return sum(float(row[key]) for row in selected) / n

        return {
            "n": n,
            "mean_raters": mean("n_raters"),
            "unanimous_fraction": mean("unanimous"),
            "target_majority_support_fraction": mean(
                "target_has_majority_support"
            ),
            "target_matches_rating_median_fraction": mean(
                "target_matches_rating_median"
            ),
            "mean_label_entropy_bits": mean("entropy_bits"),
            "modal_rater_agreement_ceiling": mean("modal_rater_support"),
            "prediction_expected_rater_agreement": mean(
                "prediction_rater_support"
            ),
        }

    report = summarize(rows)
    report["per_target"] = {
        target: summarize([row for row in rows if row["target"] == target])
        for target in label_names
        if any(row["target"] == target for row in rows)
    }
    return report


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
    report["human_label_reliability"] = _human_label_reliability(
        targets,
        predictions,
        labels,
    )
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
    accepted_set = set(accepted_ids)
    review_ids = [item_id for item_id in ids if item_id not in accepted_set]
    error_ids = [
        item_id
        for item_id in ids
        if predictions[item_id] != targets[item_id]
    ]
    reviewed_error_ids = [
        item_id for item_id in error_ids if item_id not in accepted_set
    ]
    partial_ids = [
        item_id for item_id in ids if targets[item_id] == "partial"
    ]
    reviewed_partial_ids = [
        item_id for item_id in partial_ids if item_id not in accepted_set
    ]
    target_coverage: dict[str, dict[str, Any]] = {}
    for target in ("no", "partial", "yes"):
        target_ids = [item_id for item_id in ids if targets[item_id] == target]
        target_accepted = [
            item_id for item_id in target_ids if item_id in accepted_set
        ]
        target_coverage[target] = {
            "n": len(target_ids),
            "n_accepted": len(target_accepted),
            "n_needs_human": len(target_ids) - len(target_accepted),
            "coverage": (
                len(target_accepted) / len(target_ids)
                if target_ids else None
            ),
        }
    decision_distribution = {
        label: sum(
            1
            for item_id in accepted_ids
            if predictions[item_id] == label
        )
        for label in ("no", "partial", "yes")
    }
    decision_distribution["needs_human"] = len(review_ids)
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
        "n_needs_human": len(review_ids),
        "needs_human_outcome_enabled": any(
            result_rows[item_id].get("human_review_mode")
            == "selective_policy"
            for item_id in ids
        ),
        "coverage": (
            len(accepted_ids) / len(ids) if ids else 0.0
        ),
        "review_rate": (
            len(review_ids) / len(ids) if ids else 0.0
        ),
        "error_capture_rate": (
            len(reviewed_error_ids) / len(error_ids)
            if error_ids else None
        ),
        "partial_review_rate": (
            len(reviewed_partial_ids) / len(partial_ids)
            if partial_ids else None
        ),
        "target_coverage": target_coverage,
        "decision_distribution": decision_distribution,
        "reviewed_target_distribution": {
            label: sum(
                1
                for item_id in review_ids
                if targets[item_id] == label
            )
            for label in ("no", "partial", "yes")
        },
        "system_accuracy_with_perfect_human_review": (
            (
                sum(
                    predictions[item_id] == targets[item_id]
                    for item_id in accepted_ids
                )
                + len(review_ids)
            )
            / len(ids)
            if ids else 0.0
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


def _is_referred(row: dict[str, Any]) -> bool:
    """True when a result was sent to human review under any review mode."""
    flag = row.get("needs_human")
    if flag is not None:
        return bool(flag)
    return str(row.get("decision_label") or "") == "needs_human"


def _referral_quality_metrics(
    targets: dict[str, str],
    predictions: dict[str, str],
    samples: dict[str, dict[str, Any]],
    labels: dict[str, Any],
    result_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Metric 3: is ``needs_human`` referral aligned with disputed human consensus?

    Annotation ambiguity (non-unanimous SC ratings) and model risk (model error) are two
    different objectives, so both are reported separately. Consensus-referral
    precision/recall are computed only over cases whose SC ratings are known; error capture
    is computed over every case regardless of rating availability.
    """
    ids = sorted(set(targets) & set(predictions) & set(result_rows))

    def block(subset: list[str]) -> dict[str, Any]:
        buckets = {i: _human_agreement_bucket(labels.get(i)) for i in subset}
        referred = [i for i in subset if _is_referred(result_rows[i])]
        known = [i for i in subset if buckets[i] in {"unanimous", "disputed"}]
        disputed = [i for i in known if buckets[i] == "disputed"]
        referred_known = [i for i in referred if buckets[i] in {"unanimous", "disputed"}]
        referred_disputed = [i for i in referred_known if buckets[i] == "disputed"]
        errors = [i for i in subset if predictions[i] != targets[i]]
        referred_errors = [i for i in referred if predictions[i] != targets[i]]
        partial_targets = [i for i in subset if targets[i] == "partial"]
        referred_partial = [i for i in partial_targets if _is_referred(result_rows[i])]
        precision = (
            len(referred_disputed) / len(referred_known) if referred_known else None
        )
        recall = len(referred_disputed) / len(disputed) if disputed else None
        if precision is None or recall is None:
            f1: Optional[float] = None
        elif precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        return {
            "n": len(subset),
            "n_referred": len(referred),
            "review_rate": (len(referred) / len(subset)) if subset else None,
            "n_disputed": len(disputed),
            "n_rating_known": len(known),
            "consensus_referral_precision": precision,
            "consensus_referral_recall": recall,
            "consensus_referral_f1": f1,
            "error_capture_recall": (
                len(referred_errors) / len(errors) if errors else None
            ),
            "error_prevalence_in_referrals": (
                len(referred_errors) / len(referred) if referred else None
            ),
            "fraction_true_partial_referred": (
                len(referred_partial) / len(partial_targets)
                if partial_targets
                else None
            ),
        }

    overall = block(ids)
    editors: dict[str, list[str]] = {}
    families: dict[str, list[str]] = {}
    for item_id in ids:
        editor = str(
            samples[item_id].get("editor") or samples[item_id].get("model") or "unknown"
        )
        editors.setdefault(editor, []).append(item_id)
        families.setdefault(_semantic_edit_type(samples[item_id]), []).append(item_id)
    overall["by_editor"] = {editor: block(v) for editor, v in sorted(editors.items())}
    overall["by_operation_family"] = {
        family: block(v) for family, v in sorted(families.items())
    }
    return overall


def _route_metrics(route_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Mean inference route depth and fallback-to-root rate from judge route records.

    A case is a root fallback when it is routed at depth zero (the route path never
    descended past the selected root), so this needs no separate root-id list.
    """
    depths: list[int] = []
    fallbacks = 0
    counted = 0
    for row in route_rows.values():
        cal = row.get("calitree") if isinstance(row.get("calitree"), dict) else row
        path = cal.get("route_path")
        routed = cal.get("routed_node")
        if path is None and routed is None:
            continue
        counted += 1
        depth = len(path) - 1 if isinstance(path, list) and path else 0
        depths.append(depth)
        if depth <= 0:
            fallbacks += 1
    return {
        "n_routed": counted,
        "mean_route_depth": (sum(depths) / len(depths) if depths else None),
        "fallback_to_root_rate": (fallbacks / counted if counted else None),
    }


def _tree_metrics(tree: dict[str, Any]) -> dict[str, Any]:
    """Bottom-up compression diagnostics for a persisted prompt tree.

    All fields are derived from the tree's own ``stats``/``timeline``/``nodes``. Routing
    diagnostics (route depth, fallback rate) come from ``_route_metrics`` at eval time,
    since they depend on per-item judge route records rather than tree structure.
    """
    nodes = tree.get("nodes") or {}
    stats = tree.get("stats") or {}
    timeline = tree.get("timeline") or []
    roots = [node_id for node_id in (tree.get("roots") or []) if node_id in nodes]

    timeline_kinds = Counter(str(entry.get("kind") or "") for entry in timeline)
    status_counts = Counter(str(node.get("status") or "") for node in nodes.values())

    leaf_cases = int(stats.get("leaf_cases") or 0)
    n_leaves = int(stats.get("leaves") or status_counts.get("leaf", 0))
    n_final_nodes = len(nodes)

    root_covered: set[str] = set()
    for root in roots:
        root_covered |= set((nodes.get(root) or {}).get("covered_ids") or [])
    root_accuracies = [
        nodes[root].get("validation_accuracy")
        for root in roots
        if nodes[root].get("validation_accuracy") is not None
    ]

    losses: list[float] = []
    for node in nodes.values():
        if node.get("status") not in {"accepted", "partial", "global"}:
            continue
        parent_acc = node.get("validation_accuracy")
        child_accs = [
            nodes[child].get("validation_accuracy")
            for child in (node.get("children") or [])
            if child in nodes and nodes[child].get("validation_accuracy") is not None
        ]
        if parent_acc is None or not child_accs:
            continue
        losses.append(sum(child_accs) / len(child_accs) - float(parent_acc))

    by_depth: dict[int, dict[str, float]] = {}
    for node in nodes.values():
        level = int(node.get("level") or 0)
        row = by_depth.setdefault(
            level, {"n_nodes": 0, "covered": 0, "acc_sum": 0.0, "acc_n": 0}
        )
        row["n_nodes"] += 1
        row["covered"] += len(node.get("covered_ids") or [])
        acc = node.get("validation_accuracy")
        if acc is not None:
            row["acc_sum"] += float(acc)
            row["acc_n"] += 1

    report: dict[str, Any] = {
        "n_leaves": n_leaves,
        "n_leaf_cases": leaf_cases,
        "n_full_merges": int(
            timeline_kinds.get("accepted", 0) or stats.get("accepted_merges", 0)
        ),
        "n_partial_merges": int(timeline_kinds.get("partial", 0)),
        "n_rejected_merges": int(stats.get("rejected_merges", 0)),
        "n_branch_merges": int(timeline_kinds.get("branch", 0)),
        "n_promoted_leaves": int(stats.get("promoted", 0)),
        "n_final_nodes": n_final_nodes,
        "specialization_mode": stats.get("specialization_mode", "replace"),
        "root_source": stats.get("root_source"),
        "accumulated_root": stats.get("accumulated_root"),
        "compression_ratio": (n_leaves / n_final_nodes if n_final_nodes else None),
        "specialized_roots": int(stats.get("specialized_roots", 0)),
        "merge_attempts": int(stats.get("merge_attempts", 0)),
        "merge_budget_exhausted": bool(stats.get("merge_budget_exhausted", False)),
        "status_counts": dict(sorted(status_counts.items())),
        "root_coverage": (len(root_covered) / leaf_cases if leaf_cases else None),
        "root_accuracy": (
            sum(root_accuracies) / len(root_accuracies) if root_accuracies else None
        ),
        "accuracy_loss_child_to_parent": (
            sum(losses) / len(losses) if losses else None
        ),
        "by_depth": {
            str(level): {
                "n_nodes": row["n_nodes"],
                "coverage": (row["covered"] / leaf_cases if leaf_cases else None),
                "mean_validation_accuracy": (
                    row["acc_sum"] / row["acc_n"] if row["acc_n"] else None
                ),
            }
            for level, row in sorted(by_depth.items())
        },
        "token_usage": tree.get("usage"),
    }
    return report


def _selective_acceptance(
    result: dict[str, Any],
    sample: dict[str, Any],
    policy: dict[str, Any],
) -> Optional[bool]:
    """Apply a target-blind persisted policy to one prediction."""
    if not policy:
        return None
    if (
        result.get("selective_policy_version") == policy.get("version")
        and result.get("selective_accepted") is not None
    ):
        return bool(result["selective_accepted"])
    if (
        policy.get("signal") == "ordinal_score"
        and isinstance(result.get("ordinal_score"), (int, float))
    ):
        allowed_labels = set(policy.get("allowed_labels") or [])
        return (
            float(result["ordinal_score"])
            >= float(policy.get("minimum_ordinal_score", 100))
            and (
                not allowed_labels
                or str(result.get("label") or "") in allowed_labels
            )
        )
    editor = str(sample.get("editor") or "unknown")
    branch = (policy.get("editors") or {}).get(editor) or {}
    support_ok = int(result.get("consensus_support") or 0) >= int(
        policy.get("minimum_consensus_support", 3)
    )
    return support_ok and bool(branch.get("active"))


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


EVIDENCE_REFERRAL_RULES = ("disagreement", "routing", "disagreement_or_routing")


def _evidence_signals(
    result: dict[str, Any],
    routed_node: dict[str, Any],
    route_similarity: float,
    *,
    min_route_support: int,
) -> dict[str, bool]:
    """Target-blind evidence signals used to separate ``partial`` from ``needs_human``.

    ``total_disagreement`` fires when the three independent judge paths reach no majority
    (the consensus resolver's ``consensus_tie``); the routing signals fire when the case
    landed on an unsupported or below-threshold node. None of these inspect the human
    target, dataset, editor identity, or instruction text.
    """
    threshold = float(routed_node.get("routing_threshold") or 0.70)
    support = len(routed_node.get("covered_ids") or [])
    return {
        "total_disagreement": bool(result.get("consensus_tie")),
        "low_route_similarity": float(route_similarity) < threshold,
        "unsupported_route": support < int(min_route_support),
    }


def _row_evidence_signals(
    row: dict[str, Any], tree: dict[str, Any], *, min_route_support: int
) -> dict[str, bool]:
    node = (tree.get("nodes") or {}).get(str(row.get("routed_node") or "")) or {}
    return _evidence_signals(
        row,
        node,
        float(row.get("route_similarity") or 0.0),
        min_route_support=min_route_support,
    )


def _evidence_referral(
    signals: dict[str, bool], policy: dict[str, Any]
) -> tuple[bool, str]:
    """Decide referral from evidence signals under a fitted rule. Never reads a label."""
    rule = str(policy.get("rule") or "disagreement_or_routing")
    routing_weak = signals["low_route_similarity"] or signals["unsupported_route"]
    if rule == "disagreement":
        refer = signals["total_disagreement"]
    elif rule == "routing":
        refer = routing_weak
    else:
        refer = signals["total_disagreement"] or routing_weak
    if not refer:
        return False, "evidence_accepted"
    fired = [name for name, value in signals.items() if value]
    return True, "evidence_referral:" + ",".join(fired)


def _fit_evidence_referral_policy(
    result_rows: dict[str, dict[str, Any]],
    tree: dict[str, Any],
    targets: dict[str, str],
    labels: dict[str, Any],
    train_ids: list[str],
    *,
    coverage_floor: float,
    support_candidates: tuple[int, ...] = (1, 2, 3),
) -> dict[str, Any]:
    """Fit an evidence-based referral rule using training labels only.

    Selection maximizes consensus-referral F1 (disputed-rating target) subject to a minimum
    auto-decision coverage floor. Only the referral *rule* and route-support threshold are
    chosen; the underlying three-class prediction is never altered by this policy.
    """
    ids = [item_id for item_id in train_ids if item_id in result_rows]
    disputed = {
        item_id
        for item_id in ids
        if _human_agreement_bucket(labels.get(item_id)) == "disputed"
    }
    known = {
        item_id
        for item_id in ids
        if _human_agreement_bucket(labels.get(item_id)) in {"unanimous", "disputed"}
    }
    errors = {
        item_id
        for item_id in ids
        if str(result_rows[item_id].get("label") or "") != targets.get(item_id)
    }

    candidates: list[dict[str, Any]] = []
    for rule in EVIDENCE_REFERRAL_RULES:
        for support in support_candidates:
            referred = {
                item_id
                for item_id in ids
                if _evidence_referral(
                    _row_evidence_signals(
                        result_rows[item_id], tree, min_route_support=support
                    ),
                    {"rule": rule},
                )[0]
            }
            n = len(ids)
            coverage = (1 - len(referred) / n) if n else 1.0
            referred_known = referred & known
            referred_disputed = referred & disputed
            precision = (
                len(referred_disputed) / len(referred_known)
                if referred_known
                else None
            )
            recall = len(referred_disputed) / len(disputed) if disputed else None
            if precision is None or recall is None or precision + recall == 0:
                f1 = 0.0 if precision is not None and recall is not None else None
            else:
                f1 = 2 * precision * recall / (precision + recall)
            candidates.append(
                {
                    "rule": rule,
                    "min_route_support": support,
                    "coverage": coverage,
                    "review_rate": (len(referred) / n if n else 0.0),
                    "referral_precision": precision,
                    "referral_recall": recall,
                    "referral_f1": f1,
                    "error_capture_recall": (
                        len(referred & errors) / len(errors) if errors else None
                    ),
                }
            )

    def rank(candidate: dict[str, Any]) -> tuple[Any, ...]:
        return (
            candidate["coverage"] >= coverage_floor,
            candidate["referral_f1"] if candidate["referral_f1"] is not None else -1.0,
            candidate["error_capture_recall"]
            if candidate["error_capture_recall"] is not None
            else -1.0,
            candidate["coverage"],
        )

    selected = max(candidates, key=rank) if candidates else {
        "rule": "disagreement",
        "min_route_support": 2,
    }
    return {
        "version": "evidence-referral-v1",
        "selection_split": "official_train",
        "coverage_floor": coverage_floor,
        "rule": selected["rule"],
        "min_route_support": selected["min_route_support"],
        "train_metrics": {
            key: selected.get(key)
            for key in (
                "coverage",
                "review_rate",
                "referral_precision",
                "referral_recall",
                "referral_f1",
                "error_capture_recall",
            )
        },
        "candidates": candidates,
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
    creds = load_creds(engine=config.get("engine_kind") or "gpt")
    if bool(config.get("health_check")):
        reorder_creds_by_health(
            creds,
            model=model,
            logger=ctx.run.logger,
        )
    return get_engine(
        config.get("engine_kind") or "gpt",
        history=ctx.run.history,
        model=model,
        creds=creds,
        max_tokens=int(config.get("max_tokens") or 4096),
        timeout=max(1, int(config.get("timeout") or 300)),
        **kwargs,
    )


def _media(sample: dict[str, Any]) -> list[dict[str, str]]:
    source = str((sample.get("input") or {}).get("source_image_path") or "")
    edited = str((sample.get("output") or {}).get("edited_image_path") or "")
    if not source or not edited:
        raise ValueError(f"Image sample {sample.get('item_id')} is missing source/edited paths")
    return [{"type": "image", "path": source}, {"type": "image", "path": edited}]


def _media_with_change(
    sample: dict[str, Any], descriptor: str, map_path: str
) -> list[dict[str, str]]:
    """SOURCE + EDITED + the localized change map + its textual descriptor."""
    media = _media(sample)
    media.append({"type": "image", "path": str(map_path)})
    media.append({"type": "text", "text": str(descriptor)})
    return media


def _parse_judgment(content: str) -> dict[str, Any]:
    try:
        parsed = parse_json_object(content)
    except (ValueError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        # GPT-4o occasionally follows the rubric reasoning but emits a prose conclusion
        # instead of the requested JSON.  Accept only an explicit final-label marker; never
        # infer a label from incidental words in the rationale. This preserves a useful,
        # auditable judgment and prevents the training loop from repeatedly paying for the
        # same otherwise-complete call.
        prose_labels = re.findall(
            r"(?:final\s+(?:assessment|label|verdict|decision)|"
            r"overall\s+(?:assessment|label|verdict|decision)|"
            r"conclusion|judgment)\s*(?:is|:|-)\s*[*_\s:,-]*"
            r"(?:the\s+(?:edit|label|verdict)\s+is\s+)?"
            r"(no|partial|yes)\b",
            str(content),
            flags=re.IGNORECASE,
        )
        if prose_labels:
            label = prose_labels[-1].lower()
            return {
                "label": label,
                "rationale": str(content).strip(),
                "raw_content": content,
                "valid": True,
                "parser_mode": "explicit_prose_final_label",
                "conflict_reason": "explicit prose final label recovered",
            }
        # Some optimized rubrics express the terminal decision as a presence phrase rather
        # than a categorical token ("fully/partly/not present"). Restrict recovery to an
        # explicit requested-edit phrase so incidental rationale text remains invalid.
        presence_labels = re.findall(
            r"(?:requested\s+(?:edit|change)|the\s+edit|the\s+requested\s+change)"
            r"\s+(?:is\s+)?(?:[*_]+)?"
            r"(not\s+present|absent|partly\s+present|partially\s+present|fully\s+present)\b",
            str(content),
            flags=re.IGNORECASE,
        )
        if presence_labels:
            phrase = " ".join(presence_labels[-1].lower().split())
            label = (
                "no" if phrase in {"not present", "absent"}
                else "partial" if phrase in {"partly present", "partially present"}
                else "yes"
            )
            # Preserve the structured parser's strict scene-continuity rule when the prose
            # scorecard explicitly marks continuity as failed.
            if re.search(
                r"scene\s+continuity[\s\S]{0,160}?(?:label\s*[:=-]\s*)?(?:[*_]+)?no\b",
                str(content),
                flags=re.IGNORECASE,
            ):
                label = "no"
            return {
                "label": label,
                "rationale": str(content).strip(),
                "raw_content": content,
                "valid": True,
                "parser_mode": "explicit_prose_presence_label",
                "conflict_reason": "explicit prose presence label recovered",
            }
        final_sections = re.split(
            r"(?:final\s+assessment|rubric\s+scores)\s*:",
            str(content),
            flags=re.IGNORECASE,
        )
        if len(final_sections) > 1:
            scorecard = final_sections[-1]
            requested_match = re.search(
                r"requested\s+change\s*[*_\s:=-]+(no|partial|yes)\b",
                scorecard,
                flags=re.IGNORECASE,
            )
            scene_match = re.search(
                r"scene\s+continuity\s*[*_\s:=-]+(no|partial|yes)\b",
                scorecard,
                flags=re.IGNORECASE,
            )
            if requested_match:
                requested = requested_match.group(1).lower()
                scene_label = scene_match.group(1).lower() if scene_match else ""
                label = "no" if requested == "no" or scene_label == "no" else requested
                return {
                    "label": label,
                    "rationale": str(content).strip(),
                    "raw_content": content,
                    "valid": True,
                    "parser_mode": "explicit_prose_scorecard",
                    "conflict_reason": "explicit prose scorecard recovered",
                }
        final_presence = re.findall(
            r"(?:final\s+(?:assessment|decision)|conclusion)\s*:\s*[*_\s-]*"
            r"(not\s+present|absent|partly\s+present|partially\s+present|fully\s+present)\b",
            str(content),
            flags=re.IGNORECASE,
        )
        if final_presence:
            phrase = " ".join(final_presence[-1].lower().split())
            label = (
                "no" if phrase in {"not present", "absent"}
                else "partial" if phrase in {"partly present", "partially present"}
                else "yes"
            )
            return {
                "label": label,
                "rationale": str(content).strip(),
                "raw_content": content,
                "valid": True,
                "parser_mode": "explicit_prose_presence_label",
                "conflict_reason": "explicit final presence label recovered",
            }
        return {"label": "", "rationale": "", "raw_content": content, "valid": False}
    # TextGrad's GPT-4o rewrites sometimes retain a structured four-criterion scorecard but
    # omit the redundant top-level label. It is still an unambiguous rubric judgment: the
    # requested-change field controls no/partial/yes, while a failed scene continuity blocks
    # an otherwise affirmative verdict.
    nested_scores = parsed.get("rubric_scores")
    if not parsed.get("label") and isinstance(nested_scores, dict):
        def nested_label(name: str) -> str:
            value = nested_scores.get(name)
            return str(value.get("label") or "").strip().lower() if isinstance(value, dict) else ""
        requested = nested_label("requested_change")
        scene_score = nested_label("scene_continuity")
        if requested in {"no", "partial", "yes"}:
            label = "no" if requested == "no" or scene_score == "no" else requested
            rationale = "\n".join(
                str(value.get("rationale") or "").strip()
                for value in nested_scores.values() if isinstance(value, dict)
            ).strip()
            return {"label": label, "rationale": rationale, "raw_content": content,
                    "valid": True, "parser_mode": "nested_rubric_scores"}
    model_label = str(parsed.get("label") or "").strip().lower()
    label = model_label
    conflict_reason = ""
    conditions = parsed.get("conditions")
    scene = str(parsed.get("scene") or "").strip().lower()
    if isinstance(conditions, list) and conditions:
        evidence = [
            str(condition.get("evidence") or "").strip().lower()
            for condition in conditions
            if isinstance(condition, dict)
        ]
        if len(evidence) == len(conditions) and all(
            value in {"none", "partial", "full"}
            for value in evidence
        ):
            if scene == "replaced" or "none" in evidence:
                label = "no"
                conflict_reason = (
                    "source scene replaced or a required condition has no evidence"
                )
            elif "partial" in evidence:
                label = "partial"
                conflict_reason = "a required condition has only partial evidence"
            elif all(value == "full" for value in evidence):
                label = "yes"
                conflict_reason = "all required conditions have full evidence"
    rubric_votes = parsed.get("rubric_votes")
    if isinstance(rubric_votes, dict):
        vote_labels = [
            str(
                value.get("label") if isinstance(value, dict) else value
            ).strip().lower()
            for value in rubric_votes.values()
        ]
        if len(vote_labels) == 3 and all(
            vote in {"no", "partial", "yes"} for vote in vote_labels
        ):
            counts = Counter(vote_labels)
            winner, support = max(
                counts.items(),
                key=lambda pair: (
                    pair[1], pair[0] == "partial", pair[0]
                ),
            )
            label = winner if support >= 2 else "partial"
            conflict_reason = (
                f"rubric-vote majority maps to {label}"
                if support >= 2
                else "three-way rubric disagreement maps to partial"
            )
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
    if parsed.get("rubric_version") == "rubric-lite-partial-v2":
        progress_conditions = parsed.get("conditions")
        requested_delta = str(
            parsed.get("requested_delta") or ""
        ).strip().lower()
        intended_subject = str(
            parsed.get("intended_subject") or ""
        ).strip().lower()
        progress_scene = str(parsed.get("scene") or "").strip().lower()
        if isinstance(progress_conditions, list) and progress_conditions:
            progress_evidence = [
                str(condition.get("evidence") or "").strip().lower()
                for condition in progress_conditions
                if isinstance(condition, dict)
            ]
            valid_progress_schema = (
                len(progress_evidence) == len(progress_conditions)
                and all(
                    value in {"none", "partial", "full"}
                    for value in progress_evidence
                )
                and requested_delta in {"absent", "recognizable"}
                and intended_subject in {"correct", "wrong"}
                and progress_scene in {"same", "replaced"}
            )
            if valid_progress_schema:
                if (
                    progress_scene == "replaced"
                    or intended_subject == "wrong"
                    or requested_delta == "absent"
                    or all(value == "none" for value in progress_evidence)
                ):
                    label = "no"
                    conflict_reason = (
                        "no recognizable requested progress on the intended subject"
                    )
                elif all(value == "full" for value in progress_evidence):
                    label = "yes"
                    conflict_reason = (
                        "every requested condition is visibly and exactly fulfilled"
                    )
                else:
                    label = "partial"
                    conflict_reason = (
                        "recognizable requested progress exists but fulfillment is incomplete"
                    )
    ordinal_score: Optional[float] = None
    normalized_ordinal_scores: Optional[dict[str, float]] = None
    ordinal_scores = parsed.get("ordinal_scores")
    required_ordinal_fields = (
        "change_evidence",
        "specification_fidelity",
        "source_preservation",
    )
    if (
        parsed.get("rubric_version")
        in {
            "rubric-lite-ordinal-v3",
            "rubric-lite-ordinal-v4",
            "rubric-lite-core-completion-v5",
        }
        and isinstance(ordinal_scores, dict)
        and all(
            isinstance(ordinal_scores.get(field), (int, float))
            and not isinstance(ordinal_scores.get(field), bool)
            and 0 <= float(ordinal_scores[field]) <= 100
            for field in required_ordinal_fields
        )
    ):
        ordinal_score = min(
            float(ordinal_scores[field])
            for field in required_ordinal_fields
        )
        normalized_ordinal_scores = {
            field: float(ordinal_scores[field])
            for field in required_ordinal_fields
        }
        label = ordinal_label(
            ordinal_score, DEFAULT_ORDINAL_THRESHOLDS
        )
        conflict_reason = (
            f"minimum visible-evidence score {ordinal_score:g} maps to {label} "
            "under the uncalibrated default cutpoints"
        )
    if parsed.get("rubric_version") == "rubric-lite-evidence-ledger-v6":
        ledger_conditions = parsed.get("conditions")
        ledger_statuses = [
            str(condition.get("status") or "").strip().lower()
            for condition in (
                ledger_conditions
                if isinstance(ledger_conditions, list)
                else []
            )
            if isinstance(condition, dict)
        ]
        residual_type = str(
            parsed.get("residual_type") or ""
        ).strip().lower()
        scene_validity = str(
            parsed.get("scene_validity") or ""
        ).strip().lower()
        semantic_completion = parsed.get("semantic_completion")
        valid_ledger = (
            isinstance(ledger_conditions, list)
            and 1 <= len(ledger_conditions) <= 4
            and len(ledger_statuses) == len(ledger_conditions)
            and all(
                status in {"absent", "emerging", "mostly", "complete"}
                for status in ledger_statuses
            )
            and residual_type in {
                "none",
                "missing_change",
                "wrong_subject",
                "wrong_identity_or_attribute",
                "incomplete_scope_or_count",
                "residual_old_content",
                "wrong_action_or_relation",
                "scene_replacement",
                "quality_only",
            }
            and scene_validity in {"same", "replaced"}
            and isinstance(semantic_completion, (int, float))
            and not isinstance(semantic_completion, bool)
            and 0 <= float(semantic_completion) <= 100
            and isinstance(parsed.get("achieved_evidence"), str)
            and bool(str(parsed.get("achieved_evidence") or "").strip())
            and isinstance(parsed.get("missing_evidence"), str)
            and bool(str(parsed.get("missing_evidence") or "").strip())
        )
        if valid_ledger:
            ordinal_score = (
                0.0
                if scene_validity == "replaced"
                else float(semantic_completion)
            )
            normalized_ordinal_scores = {
                "semantic_completion": float(semantic_completion),
                "scene_validity_score": (
                    0.0 if scene_validity == "replaced" else 100.0
                ),
            }
            label = ordinal_label(
                ordinal_score, DEFAULT_ORDINAL_THRESHOLDS
            )
            conflict_reason = (
                f"semantic completion score {ordinal_score:g} maps to {label} "
                "under the uncalibrated default cutpoints"
            )
        else:
            ordinal_score = None
            normalized_ordinal_scores = None
            label = ""
            conflict_reason = "invalid rubric-lite-evidence-ledger-v6 schema"
    return {
        "label": label if label in {"no", "partial", "yes"} else "",
        "model_label": model_label if model_label in {"no", "partial", "yes"} else "",
        "rationale": str(parsed.get("rationale") or ""),
        "raw_content": content,
        "parsed": parsed,
        "ordinal_score": ordinal_score,
        "ordinal_scores": normalized_ordinal_scores,
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
        change_signal: str = "off",
    ) -> None:
        self.ctx = ctx
        self.judge_engine = judge_engine
        self.optimizer_engine = optimizer_engine
        self.embedding_model = embedding_model
        self.optimizer_budget = optimizer_budget
        self.prompt_version = prompt_version
        self.concurrency = max(1, int(concurrency))
        self.change_signal = change_signal if change_signal in {"off", "all"} else "off"
        self._change_pre = None
        if self.change_signal != "off":
            from ...preprocessing.localized_change import LocalizedChangePreprocessor
            self._change_pre = LocalizedChangePreprocessor()
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

    def _judge_media(self, sample: dict[str, Any]) -> tuple[list[dict[str, str]], str, str]:
        """Media + an extra user note + a checkpoint-key component for the change signal.

        The key component stays empty when the signal is off, so existing image-less
        checkpoints (and cross-run resume) reuse unchanged; a non-empty component makes a
        change-augmented judgment a distinct cache entry.
        """
        if self.change_signal == "all" and self._change_pre is not None:
            try:
                evidence = self._change_pre.run(sample)
            except (ValueError, OSError, KeyError):
                return _media(sample), "", ""
            note = (
                " A third image is the SOURCE→EDITED change map; use it and the change "
                "descriptor to judge whether the requested edit is fully, partly, or not present."
            )
            return (
                _media_with_change(
                    sample, evidence["descriptor"], evidence["change_map_path"]
                ),
                note,
                str(evidence.get("cache_key") or ""),
            )
        return _media(sample), "", ""

    def judge(self, prompt: str, sample: dict[str, Any]) -> dict[str, Any]:
        media, note, change_key = self._judge_media(sample)
        key_parts = [prompt, sample.get("item_id")]
        if change_key:
            key_parts.append(change_key)
        key = f"{self.ctx.node_id}::calitree::judge::{_hash(*key_parts)}"
        if self.ctx.checkpoint.has(key):
            return self.ctx.checkpoint.get(key)
        instruction = str((sample.get("input") or {}).get("instruction") or "")
        result = self.judge_engine.generate(
            f"Instruction: {instruction}\nThe first image is SOURCE; the second is EDITED."
            + note,
            media_inputs=media,
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
            embedding_creds = load_creds(model=self.embedding_model)
            if embedding_creds.provider == "gemini":
                raise ValueError("CaliTree embeddings require an OpenAI text-embedding model; native Gemini embeddings are not supported")
            result = openai_compat.embeddings(
                endpoints=embedding_creds.endpoints,
                token=embedding_creds.token,
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
        "clustering_algorithm": {
            "type": "enum", "default": "semantic_complete_link",
            "options": ["semantic_complete_link", "behavioral_complete_link"],
        },
        "semantic_similarity_weight": {
            "type": "number", "default": 0.35, "min": 0, "max": 1,
        },
        "behavior_similarity_weight": {
            "type": "number", "default": 0.25, "min": 0, "max": 1,
        },
        "cross_generalization_weight": {
            "type": "number", "default": 0.40, "min": 0, "max": 1,
        },
        "behavioral_probe_cap": {
            "type": "number", "default": 48, "min": 1,
        },
        "cross_generalization_cap": {
            "type": "number", "default": 6, "min": 1,
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
        "evidence_referral_coverage_floor": {
            "type": "number", "default": 0.5, "min": 0, "max": 1,
        },
        "specialization_mode": {
            "type": "enum", "default": "replace",
            "options": ["replace", "additive"],
        },
        "leaf_grouping": {
            "type": "enum", "default": "task",
            "options": ["task", "failure_mode", "residual_context", "per_case"],
        },
        "min_leaf_fit_support": {
            "type": "number", "default": 4, "min": 1,
        },
        "root_objective": {
            "type": "enum", "default": "balanced",
            "options": ["balanced", "coverage"],
        },
        "change_signal": {
            "type": "enum", "default": "off",
            "options": ["off", "all"],
        },
        "architecture": {
            "type": "enum", "default": "hierarchical",
            "options": ["hierarchical", "rubric_lite"],
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
        architecture = str(ctx.params.get("architecture") or "hierarchical")
        if architecture not in {"hierarchical", "rubric_lite"}:
            return NodeRunResult(
                status="error",
                error=f"Unknown architecture {architecture!r}",
            )
        # The flat architecture is one global prompt with no embedding-based routing, so it
        # trains the same consensus/editor-prior/selective-policy machinery (below) without an
        # embedding model at all -- mirrors calitree_judge's existing single_global_rubric path.
        embedding_model = str(ctx.params.get("embedding_model") or "").strip()
        if not embedding_model and not ctx.dry_run and architecture != "rubric_lite":
            return NodeRunResult(status="error", error="embedding_model must be configured")
        prompt_version = str(ctx.params.get("prompt_version") or "calitree_v2")
        if prompt_version not in PROMPT_VERSIONS:
            return NodeRunResult(
                status="error",
                error=f"Unknown prompt_version {prompt_version!r}",
            )
        specialization_mode = str(ctx.params.get("specialization_mode") or "replace")
        if specialization_mode not in {"replace", "additive"}:
            return NodeRunResult(
                status="error",
                error=f"Unknown specialization_mode {specialization_mode!r}",
            )
        leaf_grouping = str(ctx.params.get("leaf_grouping") or "task")
        if leaf_grouping not in {
            "task", "failure_mode", "residual_context", "per_case"
        }:
            return NodeRunResult(
                status="error",
                error=f"Unknown leaf_grouping {leaf_grouping!r}",
            )
        clustering_algorithm = str(
            ctx.params.get("clustering_algorithm") or "semantic_complete_link"
        )
        if clustering_algorithm not in {
            "semantic_complete_link", "behavioral_complete_link"
        }:
            return NodeRunResult(
                status="error",
                error=f"Unknown clustering_algorithm {clustering_algorithm!r}",
            )
        change_signal = str(ctx.params.get("change_signal") or "off")
        if change_signal not in {"off", "all"}:
            return NodeRunResult(
                status="error",
                error=f"Unknown change_signal {change_signal!r}",
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
            estimated_calls = (
                {
                    "warm_start_judge_max": 0,
                    "task_leaf_optimizer_max": 0,
                    "task_leaf_judge_max": 0,
                    "component_extraction_max": 0,
                    "merge_optimizer_max": 0,
                    "warm_start_judge_max": (
                        (len(fit_ids) + len(validation_ids)) * (max_steps + 1)
                    ),
                    "warm_start_optimizer_max": max_steps,
                    "global_judge_max": len(train_ids) + len(test_ids),
                    "test_judge_min": len(test_ids),
                    "consensus_judge_max": (
                        3 * (len(train_ids) + len(test_ids))
                        if bool(ctx.params.get("run_conflict_resolver", True))
                        else 0
                    ),
                }
                if architecture == "rubric_lite"
                else {
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
                    "behavioral_cluster_judge_max": (
                        min(len(fit_ids), int(ctx.params.get("behavioral_probe_cap", 48)))
                        * (len(fit_tasks) + int(ctx.params.get("max_merge_attempts", 20)))
                        if clustering_algorithm == "behavioral_complete_link"
                        else 0
                    ),
                    "behavioral_transfer_judge_max": (
                        2
                        * min(
                            int(ctx.params.get("cross_generalization_cap", 6)),
                            len(fit_ids),
                        )
                        * int(ctx.params.get("max_merge_attempts", 20))
                        if clustering_algorithm == "behavioral_complete_link"
                        else 0
                    ),
                    "test_judge_min": len(test_ids),
                    "consensus_judge_max": (
                        3 * (len(train_ids) + len(test_ids))
                        if bool(ctx.params.get("run_conflict_resolver", True))
                        else 0
                    ),
                }
            )
            return NodeRunResult(
                outputs={"prompt_tree": {}, "calitree_report": {}},
                meta={
                    "dry_run": True,
                    "architecture": architecture,
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
                    "optimizer_completion_token_budget": (
                        0 if architecture == "rubric_lite" else budget
                    ),
                    "estimated_calls": estimated_calls,
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
            change_signal=change_signal,
        )
        targets = {item_id: _target(labels[item_id]) for item_id in fit_ids}
        initial_prompt = _prompt("initial_rubric.txt", prompt_version)
        all_ids = train_ids + test_ids
        router_base_results: dict[str, dict[str, Any]] = {}
        residual_router_policy: Optional[dict[str, Any]] = None
        cascade_textgrad_results: dict[str, dict[str, Any]] = {}
        if architecture == "rubric_lite":
            # No embeddings, no leaves, no clustering, no merges: one global node covering
            # every case. This flows into the exact same consensus / editor-prior /
            # selective-policy fitting below as the hierarchical path, so it is a clean test
            # of whether that machinery needs a tree underneath it at all.
            tree: dict[str, Any] = {
                "roots": ["rubric:global"],
                "nodes": {
                    "rubric:global": {
                        "id": "rubric:global",
                        "prompt": initial_prompt,
                        "covered_ids": [],
                        "children": [],
                        "embedding": [],
                        "centroid": [],
                        "validated": True,
                        "state": "global",
                    },
                },
                "config": {},
                "architecture": "rubric_lite",
                "timeline": [],
                "stats": {
                    "leaves": 1,
                    "leaf_cases": len(fit_ids),
                    "accepted_merges": 0,
                    "rejected_merges": 0,
                    "promoted": 0,
                    "roots": 1,
                    "specialized_roots": 0,
                    "merge_attempts": 0,
                    "merge_budget_exhausted": False,
                    "specialization_mode": specialization_mode,
                    "root_source": None,
                    "accumulated_root": None,
                },
            }
            # The three-way consensus below compares "initial" against "textgrad"
            # (tree["warm_start_prompt"], falling back to initial_prompt if unset). Without
            # a genuine second candidate, initial and textgrad would be the identical prompt
            # and the consensus would degenerate to "trust initial unless critic ties" --
            # not a real test of the mechanism. Run the same one-global-prompt TextGrad loop
            # RubricLiteTrainNodeExecutor uses so the flat path gets a real optimized rival.
            warm_start_targets = {
                item_id: _target(labels[item_id])
                for item_id in fit_ids + validation_ids
            }
            warm_started = RubricLiteLearner(
                judge_many=runtime.judge_many,
                optimize=runtime.optimize,
                format_feedback=lambda ids, case_samples, case_targets, results: _format_feedback(
                    ids,
                    case_samples,
                    case_targets,
                    results,
                    prompt_version=prompt_version,
                ),
                max_steps=max_steps,
                progress=ctx.progress_cb,
            ).fit(
                initial_prompt=initial_prompt,
                samples={
                    item_id: samples[item_id]
                    for item_id in fit_ids + validation_ids
                },
                targets=warm_start_targets,
                fit_ids=fit_ids,
                validation_ids=validation_ids,
            )
            tree["warm_start_prompt"] = warm_started.prompt
            tree["warm_start_accuracy"] = float(
                warm_started.report["selected"]["validation"].get("accuracy") or 0.0
            )
            tree["warm_start_report"] = warm_started.report
            routed_prompts = {
                item_id: route_prompt(tree, []) for item_id in all_ids
            }
        else:
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
                clustering_algorithm=clustering_algorithm,
                semantic_similarity_weight=float(
                    ctx.params.get("semantic_similarity_weight", 0.35)
                ),
                behavior_similarity_weight=float(
                    ctx.params.get("behavior_similarity_weight", 0.25)
                ),
                cross_generalization_weight=float(
                    ctx.params.get("cross_generalization_weight", 0.40)
                ),
                behavioral_probe_cap=int(
                    ctx.params.get("behavioral_probe_cap", 48)
                ),
                cross_generalization_cap=int(
                    ctx.params.get("cross_generalization_cap", 6)
                ),
                specialization_mode=specialization_mode,
                root_objective=str(ctx.params.get("root_objective") or "balanced"),
                progress=ctx.progress_cb,
            )
            # Failure-mode clustering groups leaves by how the base rubric errs rather than by
            # instruction semantics, so each leaf specializes one coherent, well-supported failure
            # mode. It needs the base rubric's own predictions first; the pass is checkpointed and
            # reused by the builder's warm start, so it is not billed twice.
            if leaf_grouping == "failure_mode":
                base_results = runtime.judge_many(
                    initial_prompt,
                    {item_id: samples[item_id] for item_id in fit_ids},
                )
                groups = _failure_mode_groups(base_results, samples, targets, fit_ids)
                leaf_groups_arg: Optional[dict[str, str]] = groups
                validation_target_map = {
                    item_id: _target(labels[item_id]) for item_id in validation_ids
                }
                validation_base_results = runtime.judge_many(
                    initial_prompt,
                    {item_id: samples[item_id] for item_id in validation_ids},
                )
                validation_leaf_groups_arg: Optional[dict[str, str]] = (
                    _failure_mode_groups(
                        validation_base_results,
                        samples,
                        validation_target_map,
                        validation_ids,
                    )
                )
                semantic_groups_arg = groups
            elif leaf_grouping == "residual_context":
                # The top judge supplies a coarse prediction first. Leaves are optimized on
                # supported observable contexts of that prediction, never on a target-bearing
                # failure signature. This makes training and inference routing identical.
                fit_base_results = runtime.judge_many(
                    initial_prompt,
                    {item_id: samples[item_id] for item_id in fit_ids},
                )
                validation_base_results = runtime.judge_many(
                    initial_prompt,
                    {item_id: samples[item_id] for item_id in validation_ids},
                )
                (
                    leaf_groups_arg,
                    validation_leaf_groups_arg,
                    residual_router_policy,
                ) = _fit_residual_context_partition(
                    fit_base_results=fit_base_results,
                    validation_base_results=validation_base_results,
                    samples=samples,
                    fit_ids=fit_ids,
                    validation_ids=validation_ids,
                    min_fit_support=int(
                        ctx.params.get("min_leaf_fit_support", 4)
                    ),
                    min_validation_support=int(
                        ctx.params.get("min_routing_support", 2)
                    ),
                )
                router_base_results.update(fit_base_results)
                router_base_results.update(validation_base_results)
                semantic_groups_arg = {
                    item_id: _semantic_edit_type(samples[item_id])
                    for item_id in fit_ids
                }
            elif leaf_grouping == "per_case":
                leaf_groups_arg = None
                validation_leaf_groups_arg = None
                semantic_groups_arg = {
                    item_id: _semantic_edit_type(samples[item_id]) for item_id in fit_ids
                }
            else:  # "task" — the frozen v2 default
                leaf_groups_arg = {
                    item_id: _task_uid(item_id, samples[item_id], labels[item_id])
                    for item_id in fit_ids
                }
                validation_leaf_groups_arg = None
                semantic_groups_arg = {
                    item_id: _semantic_edit_type(samples[item_id]) for item_id in fit_ids
                }
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
                validation_leaf_groups=validation_leaf_groups_arg,
                semantic_groups=semantic_groups_arg,
                leaf_groups=leaf_groups_arg,
            )
            routing_vectors = runtime.embed(
                [_routing_text(samples[item_id]) for item_id in all_ids]
            )
            if residual_router_policy is not None:
                router_base_results = runtime.judge_many(
                    initial_prompt,
                    {item_id: samples[item_id] for item_id in all_ids},
                )
                residual_router_policy.update({
                    "router_prompt": initial_prompt,
                    "router_prompt_hash": _hash(initial_prompt),
                    "routes": {
                        group_id: f"leaf:{group_id}"
                        for group_id in residual_router_policy["group_ids"]
                    },
                    "fallback": tree["roots"][0],
                })
                tree["prediction_conditioned_router"] = residual_router_policy
                cascade_prompt = str(tree.get("warm_start_prompt") or initial_prompt)
                cascade_textgrad_results = runtime.judge_many(
                    cascade_prompt,
                    {item_id: samples[item_id] for item_id in all_ids},
                )
                cascade_policy = _fit_pareto_prompt_cascade(
                    initial_results=router_base_results,
                    optimized_results=cascade_textgrad_results,
                    samples=samples,
                    targets={
                        item_id: _target(labels[item_id]) for item_id in all_ids
                    },
                    fit_ids=fit_ids,
                    validation_ids=validation_ids,
                    min_fit_support=int(
                        ctx.params.get("min_leaf_fit_support", 4)
                    ),
                )
                root_id = tree["roots"][0]
                root_embedding = list(
                    ((tree.get("nodes") or {}).get(root_id) or {}).get("embedding")
                    or []
                )
                for key, rule in cascade_policy["rules"].items():
                    node_id = f"cascade:textgrad:{_hash(key)}"
                    tree["nodes"][node_id] = {
                        "id": node_id,
                        "prompt": cascade_prompt,
                        "covered_ids": rule["fit_ids"],
                        "embedding": root_embedding,
                        "components": {},
                        "level": 1,
                        "status": "cascade",
                        "children": [],
                        "validation_accuracy": (
                            rule["validation_optimized_correct"]
                            / rule["validation_support"]
                            if rule["validation_support"] else 0.0
                        ),
                        "routing_threshold": -1.0,
                        "routing_eligible": True,
                        "routing_support": rule["fit_support"],
                        "routing_validation_support": rule["validation_support"],
                        "routing_validation_accuracy": (
                            rule["validation_optimized_correct"]
                            / rule["validation_support"]
                            if rule["validation_support"] else None
                        ),
                        "routing_baseline_accuracy": (
                            rule["validation_initial_correct"]
                            / rule["validation_support"]
                            if rule["validation_support"] else None
                        ),
                        "behavior_profile": [],
                        "semantic_groups": [],
                        "criteria_embedding": [],
                        "member_embeddings": [],
                        "conflict_reason": "",
                        "generalization_accuracy": None,
                    }
                    tree["prediction_conditioned_router"]["routes"][key] = node_id
                    tree["nodes"][root_id].setdefault("children", []).append(node_id)
                tree["pareto_prompt_cascade"] = cascade_policy
                tree["stats"]["cascade_routes"] = len(cascade_policy["rules"])
                routed_prompts = {
                    item_id: route_prompt(
                        tree,
                        vector,
                        routing_keys=_residual_context_keys(
                            samples[item_id],
                            str(router_base_results[item_id].get("label") or ""),
                        ),
                    )
                    for item_id, vector in zip(all_ids, routing_vectors)
                }
            else:
                routed_prompts = {
                    item_id: route_prompt(tree, vector)
                    for item_id, vector in zip(all_ids, routing_vectors)
                }
        tree["embedding_model"] = embedding_model
        tree["prompt_version"] = prompt_version
        tree["change_signal"] = change_signal
        tree["leaf_grouping"] = leaf_grouping
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
            initial_results = (
                router_base_results
                if set(router_base_results) == set(all_ids)
                else runtime.judge_many(initial_prompt, all_samples)
            )
            textgrad_prompt = str(
                tree.get("warm_start_prompt") or initial_prompt
            )
            textgrad_results = (
                cascade_textgrad_results
                if set(cascade_textgrad_results) == set(all_ids)
                else runtime.judge_many(textgrad_prompt, all_samples)
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
        evidence_referral_policy = _fit_evidence_referral_policy(
            tree_results,
            tree,
            all_targets,
            labels,
            calibration_train_ids,
            coverage_floor=float(
                ctx.params.get("evidence_referral_coverage_floor", 0.5)
            ),
        )
        tree["evidence_referral_policy"] = evidence_referral_policy
        # The routed judge node commonly consumes the same samples immediately after
        # training. Preserve those exact, already-paid judgments so evaluation is both
        # reproducible and free of duplicate model calls. Cache hits are accepted only
        # when the newly routed prompt has the identical content hash.
        tree["prediction_cache"] = {
            item_id: {
                "prompt_hash": _hash("calitree_prediction", routed_prompts[item_id]["prompt"]),
                "result": tree_results[item_id],
                **(
                    {
                        "routing_keys": _residual_context_keys(
                            samples[item_id],
                            str(router_base_results[item_id].get("label") or ""),
                        )
                    }
                    if residual_router_policy is not None
                    else {}
                ),
            }
            for item_id in all_ids
        }
        tree_predictions = {item_id: row["label"] for item_id, row in tree_results.items()}
        report: dict[str, Any] = {
            "version": "calitree-v2",
            "architecture": architecture,
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
            "evidence_referral_policy": tree.get("evidence_referral_policy"),
            "tree_metrics": _tree_metrics(tree),
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
            report["baseline_predictions"] = {
                item_id: {
                    "initial": initial_results[item_id].get("label"),
                    "textgrad": textgrad_results[item_id].get("label"),
                    "target": all_targets[item_id],
                    "split": samples[item_id].get("split"),
                    "editor": samples[item_id].get("editor"),
                    "operation": _semantic_edit_type(samples[item_id]),
                }
                for item_id in all_ids
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
    param_schema: dict[str, Any] = {
        "human_review_mode": {
            "type": "enum",
            "default": "off",
            "options": ["off", "selective_policy", "evidence_policy"],
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        tree = ctx.inputs.get("prompt_tree")
        engine_config = ctx.inputs.get("judge_engine")
        if samples is None or tree is None or engine_config is None:
            return NodeRunResult(
                status="error",
                error="Cali-Tree Judge requires samples, prompt_tree, and judge_engine",
            )
        human_review_mode = str(ctx.params.get("human_review_mode") or "off")
        if human_review_mode not in {"off", "selective_policy", "evidence_policy"}:
            return NodeRunResult(
                status="error",
                error=f"Unsupported human_review_mode: {human_review_mode}",
            )
        # The persisted-policy guards fail before any billable call. In a dry run the tree
        # is empty (training does not build it), so the guard is a no-op there.
        if (
            not ctx.dry_run
            and human_review_mode == "selective_policy"
            and not tree.get("selective_policy")
        ):
            return NodeRunResult(
                status="error",
                error=(
                    "human_review_mode=selective_policy requires a "
                    "prompt_tree with a persisted selective_policy"
                ),
            )
        if (
            not ctx.dry_run
            and human_review_mode == "evidence_policy"
            and not tree.get("evidence_referral_policy")
        ):
            return NodeRunResult(
                status="error",
                error=(
                    "human_review_mode=evidence_policy requires a "
                    "prompt_tree with a persisted evidence_referral_policy"
                ),
            )
        if ctx.dry_run:
            prediction_conditioned = bool(
                tree.get("prediction_conditioned_router")
            )
            return NodeRunResult(
                outputs={"judge_result": {}},
                meta={
                    "dry_run": True,
                    "estimated_calls": len(samples) * (
                        2 if prediction_conditioned else 1
                    ),
                    "prediction_conditioned_routing": prediction_conditioned,
                    "human_review_mode": human_review_mode,
                },
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
            # Routed judging reuses the change signal the tree was trained with, so training
            # and inference see the same evidence.
            change_signal=str(tree.get("change_signal") or "off"),
        )
        single_global_rubric = tree.get("architecture") == "rubric_lite"
        if not runtime.embedding_model and not single_global_rubric:
            return NodeRunResult(status="error", error="prompt_tree has no embedding_model")
        output: dict[str, Any] = {}
        routed_by_item: dict[str, dict[str, Any]] = {}
        grouped: dict[str, dict[str, dict[str, Any]]] = {}
        cached_results: dict[str, dict[str, Any]] = {}
        prediction_cache = tree.get("prediction_cache") or {}
        item_ids = sorted(samples)
        if single_global_rubric:
            routed_rows = [
                route_prompt(tree, []) for _item_id in item_ids
            ]
        else:
            routing_vectors = runtime.embed(
                [_routing_text(samples[item_id]) for item_id in item_ids]
            )
            residual_router = tree.get("prediction_conditioned_router") or {}
            if residual_router:
                router_prompt = str(residual_router.get("router_prompt") or "")
                if not router_prompt:
                    return NodeRunResult(
                        status="error",
                        error="prediction-conditioned tree has no router_prompt",
                    )
                routing_keys_by_id: dict[str, list[str]] = {}
                needs_router: dict[str, dict[str, Any]] = {}
                for item_id in item_ids:
                    stored_keys = (
                        prediction_cache.get(item_id) or {}
                    ).get("routing_keys")
                    if isinstance(stored_keys, list) and all(
                        isinstance(key, str) for key in stored_keys
                    ):
                        routing_keys_by_id[item_id] = stored_keys
                    else:
                        needs_router[item_id] = samples[item_id]
                router_results = (
                    runtime.judge_many(router_prompt, needs_router)
                    if needs_router else {}
                )
                for item_id, result in router_results.items():
                    routing_keys_by_id[item_id] = _residual_context_keys(
                        samples[item_id], str(result.get("label") or "")
                    )
                routed_rows = [
                    route_prompt(
                        tree,
                        vector,
                        routing_keys=routing_keys_by_id[item_id],
                    )
                    for item_id, vector in zip(item_ids, routing_vectors)
                ]
            else:
                routed_rows = [
                    route_prompt(tree, vector) for vector in routing_vectors
                ]
        for item_id, routed in zip(item_ids, routed_rows):
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
        if single_global_rubric and tree.get("ordinal_thresholds"):
            try:
                judged = apply_ordinal_thresholds(
                    judged,
                    tree["ordinal_thresholds"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                return NodeRunResult(
                    status="error",
                    error=f"Invalid Rubric-Lite ordinal thresholds: {exc}",
                )
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
        evidence_referral_policy = tree.get("evidence_referral_policy") or {}
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
        for item_id in item_ids:
            routed = routed_by_item[item_id]
            result = dict(judged[item_id])
            selective_accepted = _selective_acceptance(
                result, samples[item_id], selective_policy
            )
            if selective_accepted is not None:
                result["selective_accepted"] = selective_accepted
                result["selective_policy_version"] = selective_policy.get(
                    "version"
                )
            if human_review_mode == "selective_policy":
                needs_human = selective_accepted is False
                review_reason = (
                    "selective_policy_accepted"
                    if selective_accepted
                    else "selective_policy_rejected"
                )
            elif human_review_mode == "evidence_policy":
                signals = _evidence_signals(
                    result,
                    routed,
                    float(routed.get("route_similarity") or 0.0),
                    min_route_support=int(
                        evidence_referral_policy.get("min_route_support", 2)
                    ),
                )
                needs_human, review_reason = _evidence_referral(
                    signals, evidence_referral_policy
                )
                result["evidence_signals"] = signals
                result["evidence_referral_policy_version"] = (
                    evidence_referral_policy.get("version")
                )
            else:
                needs_human = False
                review_reason = "human_review_disabled"
            # The underlying three-class label is preserved even when referred, so that
            # full-coverage classification can be measured independently of the policy.
            result["decision_label"] = (
                "needs_human" if needs_human else result["label"]
            )
            result["needs_human"] = needs_human
            result["human_review_mode"] = human_review_mode
            result["review_reason"] = review_reason
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
                "human_review_mode": human_review_mode,
                "n_needs_human": sum(
                    bool(
                        (row.get("calitree") or {}).get("needs_human")
                    )
                    for row in output.values()
                ),
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
            "referral_quality": {
                "overall": _referral_quality_metrics(
                    targets, predictions, samples, labels, result_rows
                )
            },
            "tree_metrics": {"routing": _route_metrics(result_rows)},
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
            report["referral_quality"][split] = _referral_quality_metrics(
                {i: targets[i] for i in split_ids},
                {i: predictions[i] for i in split_ids},
                samples,
                labels,
                {i: result_rows[i] for i in split_ids},
            )
        ctx.run.write_json(f"calitree_eval_{ctx.node_id}.json", report)
        return NodeRunResult(outputs={"metrics_report": report}, meta={"n_items": len(ids)})
