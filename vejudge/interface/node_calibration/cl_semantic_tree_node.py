"""Semantic Tree Calibration Node — an ontology-grounded sibling of the Rule/Tree node.

Same Model Calibration fitter contract (an upstream Adversarial Calibration node's
``calibration_results`` + labels + a critic engine → ``judge_rule``), but instead of a plain
CART over opaque ``qN`` booleans it fits an **ontology-weighted** semantic decision tree
whose deployment-safe decisions are concept-labeled independent-critic answers:

  ``prompt context → rule:<concept>:qN → score-aware calibrated leaf``

Grounded debate failure-mode counts are deliberately excluded from fitted features because
they depend on human-label access that is unavailable for a fresh deployment item.

Prompt routing is fixed, learned splits are semantic-only, and raw score statistics are
restricted to regularized leaf models. Split selection is biased by
``ontology.concept_importance`` for the metric being
calibrated, and the report carries a ``semantic`` comparator alongside base/bias/linear/tree
so the Rule Comparison node shows the semantic tree head-to-head with the CART baseline on
the same frozen training/validation split.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ...core.calibration import PromptRoutedSemanticTreeCalibrator, SemanticDecisionTreeCalibrator
from ...core.calibration import ontology as onto
from ...core.calibration.debate.eval.concept_tagging import tag_questions_to_concepts
from ...core.calibration.debate.eval.critic_extraction import extract_critic_features
from ...core.calibration.debate.eval.question_bank import build_question_bank
from ...core.calibration.debate.eval.rule_extraction import extract_candidate_questions
from ...core.calibration.debate.eval.rule_fit import fit_and_evaluate
from ...core.calibration.debate.eval.joint_features import (
    build_joint_feature_rows,
    build_joint_observations,
    filter_joint_constant_questions,
    group_calibration_variants,
)
from ...core.calibration.debate.eval.rubric_bank import (
    combine_joint_banks,
    combine_with_debate_bank,
)
from ...core.calibration.debate.eval.semantic_selection import select_semantic_tree_config
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeRunContext, NodeRunResult, register
from ._templates import CalibrationFitterNode
from .cl_adversarial_node import _DIMENSIONS_FOR_METRIC, _human_targets
from .cl_rule_tree_node import _DEFAULT_ENGINE_KIND, _judge_rationale
from .evaluation_support import (
    build_observations,
    evaluation_cache_suffix,
    filter_constant_questions,
    impute_missing_semantic_values,
    preflight_diagnostics,
    semantic_summary_text,
    stable_holdout_split,
)

@register
class ClSemanticTreeNodeExecutor(CalibrationFitterNode):
    # Model Calibration role — inherits the fitter I/O contract (samples +
    # calibration_results + labels + critic_engine -> judge_rule) from CalibrationFitterNode.
    node_type = "cl_semantic_tree"
    multi_input_sockets = frozenset({"calibration_results"})
    param_schema = {
        "max_questions": {"type": "number", "default": 12, "min": 1},
        "tree_max_depth": {"type": "number", "default": 3, "min": 1, "max": 6},
        "tree_min_items_leaf": {"type": "number", "default": 1, "min": 1},
        "auto_tune_tree": {"type": "boolean", "default": True},
        "batch_size": {"type": "number", "default": 1, "min": 1},
        "human_dimension_override": {
            "type": "enum", "options": ["", *HUMAN_DIMENSIONS], "default": "",
        },
        "evaluation_mode": {
            "type": "enum",
            "options": ["frozen_holdout", "grouped_loo_exploratory"],
            "default": "frozen_holdout",
        },
        "validation_fraction": {"type": "number", "default": 0.2, "min": 0.1, "max": 0.5},
        "split_seed": {"type": "number", "default": 0, "min": 0},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        p = ctx.params
        samples = ctx.inputs.get("samples")
        calibration_input = ctx.inputs.get("calibration_results")
        calibration_sources = (
            calibration_input if isinstance(calibration_input, list) else [calibration_input]
        )
        calibration_results = calibration_sources[0] if len(calibration_sources) == 1 else None
        labels = ctx.inputs.get("labels")
        critic_config = ctx.inputs.get("critic_engine")
        for name, val in (("samples", samples), ("calibration_results", calibration_input),
                          ("labels", labels), ("critic_engine", critic_config)):
            if val is None:
                return NodeRunResult(
                    status="error",
                    error=f"Semantic Tree Calibration Node requires a '{name}' input.",
                )
        if len(calibration_sources) > 1:
            return self._run_joint(
                ctx, samples=samples, calibration_sources=calibration_sources,
                labels=labels, critic_config=critic_config,
            )
        assert calibration_results is not None
        overlap = sorted(set(samples) & set(calibration_results))
        usable_cr = {
            it: calibration_results[it] for it in overlap
            if calibration_results[it].get("transcript")
            and isinstance(calibration_results[it].get("original_score"), (int, float))
        }
        if not usable_cr:
            return NodeRunResult(
                status="error",
                error="No overlapping items with a usable debate transcript + base score "
                "in 'calibration_results' — wire an Adversarial Calibration node that ran.",
            )
        metric_id = next(iter(usable_cr.values())).get("metric_id")

        if ctx.dry_run:
            mode = p.get("evaluation_mode") or "grouped_loo_exploratory"
            train_ids = list(usable_cr)
            if mode == "frozen_holdout":
                train_ids, _ = stable_holdout_split(
                    train_ids,
                    validation_fraction=float(p.get("validation_fraction") or 0.2),
                    split_seed=int(p.get("split_seed") or 0),
                )
            return NodeRunResult(
                outputs={"judge_rule": {}},
                meta={"dry_run": True, "n_items": len(usable_cr),
                      "estimated_calls": {
                          "rule_extraction_calls": len(train_ids),
                          "bank_calls": 1 if train_ids else 0,
                          "critic_calls": len(usable_cr),
                          "tagging_calls": 1 if train_ids else 0,
                      }},
            )

        try:
            require_live(ctx.allow_live, context=f"Semantic Tree Calibration over {len(usable_cr)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        override = p.get("human_dimension_override") or None
        dims = [override] if override else _DIMENSIONS_FOR_METRIC.get(metric_id, [])
        anchored: dict[str, dict[str, Any]] = {}
        skipped: dict[str, str] = {}
        for it, cr in usable_cr.items():
            agg = labels.get(it) if labels else None
            targets = _human_targets(agg, dims)
            if targets:
                anchored[it] = {"cr": cr, "humans": targets,
                                "base": float(cr["original_score"])}
            else:
                skipped[it] = "no_usable_metric_aligned_human_target"
        if not anchored:
            return NodeRunResult(
                status="error",
                error=f"No items with usable human targets for metric {metric_id} "
                "(check 'labels' cover the metric's mapped dimensions).",
            )

        temp_kw = {} if critic_config.get("temperature") is None else {"temperature": critic_config["temperature"]}
        critic_engine = get_engine(
            critic_config.get("engine_kind") or _DEFAULT_ENGINE_KIND.get(
                JUDGE_METRICS[metric_id].modality, "gpt"),
            history=ctx.run.history, model=critic_config.get("model"), creds=load_creds(),
            max_tokens=int(critic_config.get("max_tokens") or 4096), **temp_kw,
        )

        evaluation_mode = p.get("evaluation_mode") or "grouped_loo_exploratory"
        all_item_ids = list(anchored)
        if evaluation_mode == "frozen_holdout":
            training_ids, validation_ids = stable_holdout_split(
                all_item_ids,
                validation_fraction=float(p.get("validation_fraction") or 0.2),
                split_seed=int(p.get("split_seed") or 0),
            )
        else:
            training_ids, validation_ids = all_item_ids, all_item_ids
        max_questions = max(1, int(p.get("max_questions") or 12))
        cache_suffix = evaluation_cache_suffix(
            metric_id=metric_id, training_ids=training_ids,
            max_questions=max_questions, critic_config=critic_config,
        )
        training_summaries = {
            it: semantic_summary_text(anchored[it]["cr"]) for it in training_ids
        }
        missing_summary_items = [it for it, text in training_summaries.items() if not text]
        concurrency = max(1, int(critic_config.get("concurrency") or 1))

        bank_key = f"{ctx.node_id}::rule_bank::{cache_suffix}"
        if ctx.checkpoint.has(bank_key):
            bank = ctx.checkpoint.get(bank_key)
        else:
            candidates: list[dict[str, Any]] = []
            extraction_tasks: list[str] = []
            for it in training_ids:
                summary_text = training_summaries[it]
                if not summary_text:
                    continue
                candidate_key = f"{ctx.node_id}::{it}::rule_candidates::{cache_suffix}"
                if ctx.checkpoint.has(candidate_key):
                    candidates.extend(ctx.checkpoint.get(candidate_key))
                else:
                    extraction_tasks.append(it)
            with ThreadPoolExecutor(max_workers=concurrency) as ex:
                futures = {
                    ex.submit(
                        extract_candidate_questions,
                        transcript_text=training_summaries[it], metric_id=metric_id,
                        engine=critic_engine,
                    ): it
                    for it in extraction_tasks
                }
                for future in as_completed(futures):
                    it = futures[future]
                    item_candidates = future.result()
                    ctx.checkpoint.put(
                        f"{ctx.node_id}::{it}::rule_candidates::{cache_suffix}",
                        item_candidates,
                    )
                    candidates.extend(item_candidates)
            debate_bank = build_question_bank(candidates=candidates, engine=critic_engine,
                                              max_questions=max_questions)
            bank = combine_with_debate_bank(
                metric_id=metric_id, debate_bank=debate_bank, max_questions=max_questions,
            )
            ctx.checkpoint.put(bank_key, bank)

        # --- tag each mined rule to a taxonomy concept (checkpointed) ---
        tags_key = f"{ctx.node_id}::concept_tags::{cache_suffix}"
        if ctx.checkpoint.has(tags_key):
            tags = ctx.checkpoint.get(tags_key)
        else:
            tags = tag_questions_to_concepts(bank=bank, engine=critic_engine)
            ctx.checkpoint.put(tags_key, tags)

        # --- independent critic answers the bank per item (concurrent, checkpointed) ---
        item_ids = all_item_ids
        booleans: dict[str, list[int]] = {}
        semantic_values: dict[str, list[float]] = {}
        missing: dict[str, list[str]] = {}
        tasks: list[str] = []
        for it in item_ids:
            fkey = f"{ctx.node_id}::{it}::rule_features::{cache_suffix}"
            if ctx.checkpoint.has(fkey):
                cached = ctx.checkpoint.get(fkey)
                booleans[it] = cached["booleans"]
                semantic_values[it] = cached.get(
                    "semantic_values", [float(value) for value in cached["booleans"]],
                )
                missing[it] = cached["missing"]
            else:
                tasks.append(it)

        if ctx.progress_cb:
            ctx.progress_cb("calibration_progress_init", {"total": len(tasks)})

        item_timings: list[dict[str, Any]] = []

        def _run(it: str) -> tuple[str, dict[str, Any], float]:
            if ctx.progress_cb:
                ctx.progress_cb("calibration_item_start", {"item_id": it})
            t0 = time.perf_counter()
            feats = extract_critic_features(
                sample=samples[it], judge_rationale=_judge_rationale(anchored[it]["cr"]),
                questions=bank, critic_engine=critic_engine,
            )
            return it, feats, round((time.perf_counter() - t0) * 1000, 1)

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(_run, it) for it in tasks]
            for fut in as_completed(futs):
                if fut.cancelled():
                    continue
                it, feats, ms = fut.result()
                booleans[it] = feats["booleans"]
                semantic_values[it] = feats.get("semantic_values", feats["booleans"])
                missing[it] = feats["missing"]
                item_timings.append({"item_id": it, "ms": ms})
                ctx.checkpoint.put(f"{ctx.node_id}::{it}::rule_features::{cache_suffix}", feats)
                if ctx.progress_cb:
                    ctx.progress_cb("calibration_item_done", {"item_id": it})
                if ctx.should_stop and ctx.should_stop():
                    for f in futs:
                        if not f.done():
                            f.cancel()

        # Keep question-level deployment features. Grounded transcript failure-mode counts
        # are deliberately excluded because they require held-out human labels.
        imputed_values, imputation = impute_missing_semantic_values(
            semantic_values, missing, training_ids,
        )
        filtered_bank, filtered_values, prevalence, dropped = filter_constant_questions(
            bank, imputed_values, training_ids,
        )
        dropped_indices = {entry["question_index"] for entry in dropped}
        kept_indices = [entry["question_index"] for entry in prevalence
                        if entry["question_index"] not in dropped_indices]
        filtered_booleans = {
            item: [values[index] for index in kept_indices if index < len(values)]
            for item, values in booleans.items()
        }
        filtered_tags = [tags[index] if index < len(tags) else None for index in kept_indices]
        feature_names = ["base_score"]
        for index in range(len(filtered_bank)):
            tag = filtered_tags[index] or "untagged"
            prefix = tag if tag.startswith("rubric:") else f"rule:{tag}"
            feature_names.append(f"{prefix}:q{index + 1}")
        observation_ids, observation_item, bases, humans, feats_full, weights = build_observations(
            anchored, filtered_values,
        )
        feature_weights = {
            n: onto.concept_importance(onto.concept_for_feature(n), metric_id)
            for n in feature_names
        }

        # --- fit + evaluate (base/bias/linear/tree(CART) + semantic), in-sample + LOO ---
        tree_max_depth = max(1, min(6, int(p.get("tree_max_depth") or 3)))
        tree_min_leaf = max(1, int(p.get("tree_min_items_leaf") or 1))
        selection_scores: list[dict[str, Any]] = []
        semantic_feature_names = [
            name for name in feature_names if name.startswith(("rubric:", "rule:"))
        ]
        leaf_feature_names = [name for name in feature_names if name == "base_score"]
        allowed_feature_names: list[str] = semantic_feature_names
        selected_feature_set = "all"
        selection_metadata: dict[str, Any] = {}
        if bool(p.get("auto_tune_tree", True)) and len(training_ids) >= 5:
            selected, selection_scores = select_semantic_tree_config(
                observation_ids=observation_ids,
                observation_item=observation_item,
                humans=humans,
                features=feats_full,
                weights=weights,
                feature_names=feature_names,
                feature_weights=feature_weights,
                training_items=training_ids,
                max_depth=tree_max_depth,
                min_leaf_floor=tree_min_leaf,
                leaf_feature_names=leaf_feature_names,
            )
            tree_max_depth = selected["max_depth"]
            tree_min_leaf = selected["min_samples_leaf"]
            allowed_feature_names = selected["allowed_feature_names"]
            selected_feature_set = selected["feature_set"]
            selection_metadata = {
                key: value for key, value in selected.items()
                if key not in {"feature_set", "allowed_feature_names", "max_depth",
                               "min_samples_leaf"}
            }
        semantic_factory = lambda: SemanticDecisionTreeCalibrator(
            feature_weights=feature_weights,
            allowed_feature_names=allowed_feature_names,
            leaf_feature_names=leaf_feature_names,
            max_depth=tree_max_depth,
            min_samples_leaf=tree_min_leaf,
        )
        report = fit_and_evaluate(
            item_ids=observation_ids, bases=bases, humans=humans,
            feats_full=feats_full, feature_names=feature_names,
            loo_groups=observation_item,
            observation_weights=weights,
            train_groups=training_ids if evaluation_mode == "frozen_holdout" else None,
            validation_groups=validation_ids if evaluation_mode == "frozen_holdout" else None,
            extra_calibrators={
                "semantic": semantic_factory,
            },
        )

        # The exported tree + rule text should be the SEMANTIC tree (what this node is about),
        # not the CART one fit_and_evaluate exports by default. Refit on all items for display.
        display_ids = [obs for obs in observation_ids
                       if observation_item[obs] in set(training_ids)]
        if len(set(observation_item[obs] for obs in display_ids)) >= 2:
            semantic = semantic_factory().fit(
                [feats_full[i] for i in display_ids],
                [humans[i] for i in display_ids],
                feature_names=feature_names,
                sample_weight=[weights[i] for i in display_ids],
            )
            sem_meta = semantic.metadata()
            report["tree"] = sem_meta.get("tree")
            report["tree_rule"] = sem_meta.get("rule_text", "")
            report["feature_importances"] = sem_meta.get("feature_importances", [])
            def collect_split_features(node: dict[str, Any] | None) -> list[str]:
                if not node or node.get("leaf"):
                    return []
                return [
                    str(node.get("feature")),
                    *collect_split_features(node.get("left")),
                    *collect_split_features(node.get("right")),
                ]

            split_features = collect_split_features(sem_meta.get("tree"))
            report["semantic_split_features"] = split_features
            report["semantic_split_count"] = len(split_features)
            report["raw_score_split_count"] = 0
            report["leaf_feature_names"] = leaf_feature_names
            report["tree_architecture"] = "semantic_splits_score_aware_leaves"

        report["metric"] = metric_id
        report["bank"] = filtered_bank
        report["candidate_bank"] = bank
        report["concept_tags"] = filtered_tags
        report["feature_prevalence"] = prevalence
        report["dropped_features"] = dropped
        report["feature_weights"] = feature_weights
        report["semantic_imputation"] = imputation
        report["semantic_tree_selection"] = {
            "selected": {
                "feature_set": selected_feature_set,
                "allowed_feature_names": allowed_feature_names or feature_names,
                "max_depth": tree_max_depth,
                "min_samples_leaf": tree_min_leaf,
                **selection_metadata,
            },
            "training_grouped_loo": selection_scores,
            "validation_labels_used": False,
        }
        # Self-contained labels for the UI tree tooltip: concept features -> concept label,
        # base_score -> a plain gloss.
        labels_map = {
            name: f"critic: {onto.CONCEPTS[tag].label}" if tag in onto.CONCEPTS else "critic rule"
            for name, tag in zip(feature_names[1:], filtered_tags)
        }
        labels_map["base_score"] = "the judge's own 1–5 score"
        report["feature_labels"] = {n: labels_map.get(n, n) for n in feature_names}
        report["per_item"] = {
            it: {"base": anchored[it]["base"],
                 "human": [round(v, 2) for v in anchored[it]["humans"]]
                 if len(anchored[it]["humans"]) > 1 else round(anchored[it]["humans"][0], 2),
                 "booleans": filtered_booleans.get(it, []),
                 "semantic_values": filtered_values.get(it, []),
                 "missing": missing.get(it, [])}
            for it in item_ids
        }
        diagnostics, warnings = preflight_diagnostics(
            metric_id=metric_id, dimensions=dims, usable_cr=usable_cr, anchored=anchored,
            skipped=skipped, training_ids=training_ids, validation_ids=validation_ids,
        )
        if dropped:
            warnings.append(f"Dropped {len(dropped)} constant rule question(s) using training data only.")
        if missing_summary_items:
            warnings.append(
                f"Ignored {len(missing_summary_items)} training item(s) without a validated semantic summary."
            )
        n_imputed_items = sum(bool(entries) for entries in missing.values())
        if n_imputed_items:
            warnings.append(
                f"Imputed missing critic evidence for {n_imputed_items} item(s) using "
                "training-only per-question medians."
            )
        report["diagnostics"] = diagnostics
        report["warnings"] = warnings
        meta = {"n_items": len(item_ids), "warning": " ".join(warnings) if warnings else None}
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)

    def _run_joint(
        self, ctx: NodeRunContext, *, samples: dict[str, Any],
        calibration_sources: list[dict[str, Any]], labels: dict[str, Any],
        critic_config: dict[str, Any],
    ) -> NodeRunResult:
        """Fit one prompt-aware tree over metric tasks and temperature variants."""
        p = ctx.params
        tasks = group_calibration_variants(calibration_sources)
        tasks = {
            key: task for key, task in tasks.items()
            if task["item_id"] in samples
            and any(variant["result"].get("transcript") for variant in task["variants"])
        }
        if not tasks:
            if ctx.dry_run:
                source_count = len(calibration_sources)
                train_count = len(samples)
                if (p.get("evaluation_mode") or "grouped_loo_exploratory") == "frozen_holdout":
                    train_ids, _ = stable_holdout_split(
                        list(samples),
                        validation_fraction=float(p.get("validation_fraction") or 0.2),
                        split_seed=int(p.get("split_seed") or 0),
                    )
                    train_count = len(train_ids)
                return NodeRunResult(outputs={"judge_rule": {}}, meta={
                    "dry_run": True,
                    "n_items": len(samples),
                    "n_prompt_tasks": len(samples) * source_count,
                    "estimated_calls": {
                        "rule_extraction_calls": train_count * source_count,
                        "bank_calls": source_count,
                        "critic_calls": len(samples) * source_count,
                        "tagging_calls": 1,
                    },
                    "estimate_note": "Prompt count inferred from dry upstream fan-in.",
                })
            return NodeRunResult(
                status="error",
                error="No usable prompt/temperature calibration variants overlap with samples.",
            )

        override = p.get("human_dimension_override") or None
        skipped: dict[str, str] = {}
        for task_key, task in list(tasks.items()):
            dimensions = [override] if override else _DIMENSIONS_FOR_METRIC.get(task["metric_id"], [])
            targets = _human_targets(labels.get(task["item_id"]), dimensions)
            if not targets:
                skipped[task_key] = "no_usable_metric_aligned_human_target"
                tasks.pop(task_key)
                continue
            task["humans"] = targets
            task["dimensions"] = dimensions
        if not tasks:
            return NodeRunResult(
                status="error",
                error="No joint prompt tasks have usable metric-aligned human targets.",
            )

        metric_ids = sorted({task["metric_id"] for task in tasks.values()})
        all_item_ids = sorted({task["item_id"] for task in tasks.values()})
        evaluation_mode = p.get("evaluation_mode") or "grouped_loo_exploratory"
        if evaluation_mode == "frozen_holdout":
            training_ids, validation_ids = stable_holdout_split(
                all_item_ids,
                validation_fraction=float(p.get("validation_fraction") or 0.2),
                split_seed=int(p.get("split_seed") or 0),
            )
        else:
            training_ids, validation_ids = all_item_ids, all_item_ids
        training_set = set(training_ids)
        training_task_keys = [
            key for key, task in tasks.items() if task["item_id"] in training_set
        ]
        max_questions_per_metric = max(1, int(p.get("max_questions") or 12))

        if ctx.dry_run:
            return NodeRunResult(outputs={"judge_rule": {}}, meta={
                "dry_run": True,
                "n_items": len(all_item_ids),
                "n_prompt_tasks": len(tasks),
                "metrics": metric_ids,
                "estimated_calls": {
                    "rule_extraction_calls": len(training_task_keys),
                    "bank_calls": len(metric_ids),
                    "critic_calls": len(tasks),
                    "tagging_calls": 1,
                },
            })

        try:
            require_live(ctx.allow_live, context=(
                f"Joint Semantic Tree Calibration over {len(tasks)} prompt task(s)"
            ))
        except LiveCallNotAllowed as error:
            return NodeRunResult(status="error", error=str(error))

        temp_kw = (
            {} if critic_config.get("temperature") is None
            else {"temperature": critic_config["temperature"]}
        )
        default_kind = "gemini" if any(
            JUDGE_METRICS[metric].modality == "video" for metric in metric_ids
        ) else "gpt"
        critic_engine = get_engine(
            critic_config.get("engine_kind") or default_kind,
            history=ctx.run.history, model=critic_config.get("model"), creds=load_creds(),
            max_tokens=int(critic_config.get("max_tokens") or 4096), **temp_kw,
        )
        concurrency = max(1, int(critic_config.get("concurrency") or 1))
        training_summaries = {
            task_key: "\n".join(
                filter(None, (
                    semantic_summary_text(variant["result"])
                    for variant in task["variants"]
                ))
            )
            for task_key, task in tasks.items()
            if task["item_id"] in training_set
        }
        cache_payload = {
            "version": "joint-semantic-v1-lookahead",
            "metrics": metric_ids,
            "training_ids": training_ids,
            "max_questions_per_metric": max_questions_per_metric,
            "critic": critic_config,
            "variants": {
                key: {
                    "scores": [variant["score"] for variant in task["variants"]],
                    "temperatures": task["temperatures"],
                }
                for key, task in tasks.items()
            },
        }
        cache_suffix = hashlib.sha256(
            json.dumps(cache_payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        bank_key = f"{ctx.node_id}::joint_rule_bank::{cache_suffix}"
        if ctx.checkpoint.has(bank_key):
            bank = ctx.checkpoint.get(bank_key)
        else:
            candidates_by_metric: dict[str, list[dict[str, Any]]] = {
                metric: [] for metric in metric_ids
            }
            extraction_tasks: list[str] = []
            for task_key in training_task_keys:
                if not training_summaries.get(task_key):
                    continue
                candidate_key = f"{ctx.node_id}::{task_key}::joint_candidates::{cache_suffix}"
                if ctx.checkpoint.has(candidate_key):
                    candidates_by_metric[tasks[task_key]["metric_id"]].extend(
                        ctx.checkpoint.get(candidate_key)
                    )
                else:
                    extraction_tasks.append(task_key)
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {
                    executor.submit(
                        extract_candidate_questions,
                        transcript_text=training_summaries[task_key],
                        metric_id=tasks[task_key]["metric_id"], engine=critic_engine,
                    ): task_key
                    for task_key in extraction_tasks
                }
                for future in as_completed(futures):
                    task_key = futures[future]
                    candidates = future.result()
                    ctx.checkpoint.put(
                        f"{ctx.node_id}::{task_key}::joint_candidates::{cache_suffix}",
                        candidates,
                    )
                    candidates_by_metric[tasks[task_key]["metric_id"]].extend(candidates)
            debate_banks = {
                metric: build_question_bank(
                    candidates=candidates_by_metric[metric], engine=critic_engine,
                    max_questions=max_questions_per_metric,
                )
                for metric in metric_ids
            }
            bank = combine_joint_banks(
                metric_ids=metric_ids, debate_banks=debate_banks,
                max_questions_per_metric=max_questions_per_metric,
            )
            ctx.checkpoint.put(bank_key, bank)

        tags_key = f"{ctx.node_id}::joint_concept_tags::{cache_suffix}"
        if ctx.checkpoint.has(tags_key):
            tags = ctx.checkpoint.get(tags_key)
        else:
            tags = tag_questions_to_concepts(bank=bank, engine=critic_engine)
            ctx.checkpoint.put(tags_key, tags)

        booleans: dict[str, list[int]] = {}
        semantic_values: dict[str, list[float]] = {}
        missing: dict[str, list[str]] = {}
        pending: list[str] = []
        for task_key in tasks:
            feature_key = f"{ctx.node_id}::{task_key}::joint_features::{cache_suffix}"
            if ctx.checkpoint.has(feature_key):
                cached = ctx.checkpoint.get(feature_key)
                applicable_count = sum(
                    1 for question in bank
                    if not question.get("metric_ids")
                    or tasks[task_key]["metric_id"] in question["metric_ids"]
                )
                # Older runs could cache a completely failed critic call as an all-zero
                # feature row. Treat that row as unfinished so Resume repairs it.
                if applicable_count and len(cached.get("missing") or []) >= applicable_count:
                    pending.append(task_key)
                else:
                    booleans[task_key] = cached["booleans"]
                    semantic_values[task_key] = cached["semantic_values"]
                    missing[task_key] = cached["missing"]
            else:
                pending.append(task_key)
        if ctx.progress_cb:
            ctx.progress_cb("calibration_progress_init", {"total": len(pending)})
        item_timings: list[dict[str, Any]] = []

        def run_critic(task_key: str) -> tuple[str, dict[str, Any], float]:
            task = tasks[task_key]
            applicable = [
                (index, question) for index, question in enumerate(bank)
                if not question.get("metric_ids")
                or task["metric_id"] in question["metric_ids"]
            ]
            rationale = "\n\n".join(filter(None, (
                _judge_rationale(variant["result"]) for variant in task["variants"]
            )))
            started = time.perf_counter()
            local = extract_critic_features(
                sample=samples[task["item_id"]], judge_rationale=rationale,
                questions=[question for _index, question in applicable],
                critic_engine=critic_engine,
            )
            expanded_booleans = [0] * len(bank)
            expanded_values = [0.0] * len(bank)
            expanded_missing: list[str] = []
            local_missing = set(local.get("missing") or [])
            for local_index, (global_index, _question) in enumerate(applicable):
                expanded_booleans[global_index] = local["booleans"][local_index]
                expanded_values[global_index] = local["semantic_values"][local_index]
                if f"q{local_index + 1}" in local_missing:
                    expanded_missing.append(f"q{global_index + 1}")
            return task_key, {
                **local, "booleans": expanded_booleans,
                "semantic_values": expanded_values, "missing": expanded_missing,
            }, round((time.perf_counter() - started) * 1000, 1)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_critic, task_key) for task_key in pending]
            for future in as_completed(futures):
                task_key, result, elapsed = future.result()
                booleans[task_key] = result["booleans"]
                semantic_values[task_key] = result["semantic_values"]
                missing[task_key] = result["missing"]
                item_timings.append({"item_id": task_key, "ms": elapsed})
                applicable_count = sum(
                    1 for question in bank
                    if not question.get("metric_ids")
                    or tasks[task_key]["metric_id"] in question["metric_ids"]
                )
                # Keep a rare exhausted failure usable through imputation for this run,
                # but do not call it completed: Resume should try it again.
                if not applicable_count or len(result.get("missing") or []) < applicable_count:
                    ctx.checkpoint.put(
                        f"{ctx.node_id}::{task_key}::joint_features::{cache_suffix}", result,
                    )
                if ctx.progress_cb:
                    ctx.progress_cb("calibration_item_done", {"item_id": task_key})

        imputed_values, imputation = impute_missing_semantic_values(
            semantic_values, missing, training_task_keys,
        )
        filtered_bank, filtered_values, prevalence, dropped, kept_indices = (
            filter_joint_constant_questions(
                bank, imputed_values, tasks, training_ids,
            )
        )
        filtered_booleans = {
            key: [row[index] for index in kept_indices] for key, row in booleans.items()
        }
        filtered_tags = [tags[index] if index < len(tags) else None for index in kept_indices]
        base_feature_names, task_feature_rows = build_joint_feature_rows(
            tasks, filtered_values, metric_ids,
        )
        semantic_feature_names: list[str] = []
        for index, question in enumerate(filtered_bank):
            tag = filtered_tags[index] or "untagged"
            prefix = tag if tag.startswith("rubric:") else f"rule:{tag}"
            metric = (question.get("metric_ids") or ["shared"])[0]
            semantic_feature_names.append(f"{prefix}:{metric}:q{index + 1}")
        feature_names = [*base_feature_names, *semantic_feature_names]
        (
            observation_ids, observation_item, observation_task, bases, humans,
            features, weights,
        ) = build_joint_observations(tasks, task_feature_rows)
        feature_weights: dict[str, float] = {
            name: 1.0 for name in base_feature_names
        }
        for name, question in zip(semantic_feature_names, filtered_bank):
            question_metric = (question.get("metric_ids") or metric_ids)[0]
            feature_weights[name] = onto.concept_importance(
                onto.concept_for_feature(name), question_metric,
            )

        tree_max_depth = max(2, min(6, int(p.get("tree_max_depth") or 3)))
        tree_min_leaf = max(1, int(p.get("tree_min_items_leaf") or 1))
        prompt_feature_names = [
            name for name in base_feature_names if name.startswith("prompt:")
        ]
        leaf_feature_names = [
            name for name in base_feature_names
            if name in {"base_score", "score_std", "score_range"}
        ]
        selected, selection_scores = select_semantic_tree_config(
            observation_ids=observation_ids, observation_item=observation_item,
            humans=humans, features=features, weights=weights,
            feature_names=feature_names, feature_weights=feature_weights,
            training_items=training_ids, max_depth=tree_max_depth,
            min_leaf_floor=tree_min_leaf,
            prompt_feature_names=prompt_feature_names,
            leaf_feature_names=leaf_feature_names,
        )
        semantic_factory = lambda: PromptRoutedSemanticTreeCalibrator(
            feature_weights=feature_weights,
            semantic_feature_names=selected["semantic_feature_names"],
            prompt_feature_names=prompt_feature_names,
            leaf_feature_names=leaf_feature_names,
            max_depth=selected["max_depth"],
            min_samples_leaf=selected["min_samples_leaf"],
        )
        report = fit_and_evaluate(
            item_ids=observation_ids, bases=bases, humans=humans,
            feats_full=features, feature_names=feature_names,
            loo_groups=observation_item, observation_weights=weights,
            train_groups=training_ids if evaluation_mode == "frozen_holdout" else None,
            validation_groups=validation_ids if evaluation_mode == "frozen_holdout" else None,
            extra_calibrators={"semantic": semantic_factory},
            strata={
                obs: tasks[observation_task[obs]]["metric_id"] for obs in observation_ids
            },
            reference_feature_names=base_feature_names,
        )
        train_observations = [
            obs for obs in observation_ids if observation_item[obs] in training_set
        ]
        semantic = semantic_factory().fit(
            [features[obs] for obs in train_observations],
            [humans[obs] for obs in train_observations],
            feature_names=feature_names,
            sample_weight=[weights[obs] for obs in train_observations],
        )
        semantic_meta = semantic.metadata()
        report["tree"] = semantic_meta.get("tree")
        report["tree_rule"] = semantic_meta.get("rule_text", "")
        report["feature_importances"] = semantic_meta.get("feature_importances", [])
        report["semantic_prompt_trees"] = semantic_meta.get("prompt_trees", {})
        report["semantic_split_features"] = semantic_meta.get("semantic_split_features", [])
        report["semantic_split_count"] = semantic_meta.get("semantic_split_count", 0)
        report["raw_score_split_count"] = semantic_meta.get("raw_score_split_count", 0)
        report["leaf_feature_names"] = semantic_meta.get("leaf_feature_names", [])
        report["tree_architecture"] = "fixed_prompt_router_semantic_splits_score_aware_leaves"
        report["semantic_model_method"] = {
            "split_candidates": "ontology-backed semantic questions only",
            "split_objective": "ontology-weighted MAE reduction",
            "context_router": "fixed prompt identity",
            "leaf_model": "ridge over raw judge score distribution",
        }
        report["metric"] = "joint:" + "+".join(metric_ids)
        report["metrics"] = metric_ids
        report["n_prompt_tasks"] = len(tasks)
        report["n_judge_variants"] = sum(task["variant_count"] for task in tasks.values())
        report["bank"] = filtered_bank
        report["candidate_bank"] = bank
        report["concept_tags"] = filtered_tags
        report["feature_prevalence"] = prevalence
        report["dropped_features"] = dropped
        report["feature_weights"] = feature_weights
        report["semantic_imputation"] = imputation
        report["semantic_tree_selection"] = {
            "selected": selected,
            "training_grouped_loo": selection_scores,
            "validation_labels_used": False,
        }
        report["feature_labels"] = {
            "base_score": "mean raw judge score across temperature variants",
            "score_std": "judge-score variation across temperatures",
            "score_range": "judge-score range across temperatures",
            **{f"prompt:{metric}": f"judge prompt is {metric}" for metric in metric_ids},
            **{
                name: filtered_bank[index]["question"]
                for index, name in enumerate(semantic_feature_names)
            },
        }
        report["per_item"] = {
            task_key: {
                "item_id": task["item_id"], "metric_id": task["metric_id"],
                "base": task["base"], "score_std": task["score_std"],
                "score_range": task["score_range"],
                "variant_count": task["variant_count"],
                "temperatures": task["temperatures"],
                "human": task["humans"],
                "booleans": filtered_booleans.get(task_key, []),
                "semantic_values": filtered_values.get(task_key, []),
                "missing": missing.get(task_key, []),
            }
            for task_key, task in tasks.items()
        }
        per_metric: dict[str, dict[str, Any]] = {}
        validation_predictions = report.get("validation_predictions_by_observation") or {}
        for metric in metric_ids:
            metric_observations = [
                obs for obs in validation_predictions
                if tasks[observation_task[obs]]["metric_id"] == metric
            ]
            per_metric[metric] = {
                comparator: (
                    sum(
                        weights[obs] * abs(
                            validation_predictions[obs][comparator] - humans[obs]
                        ) for obs in metric_observations
                    ) / sum(weights[obs] for obs in metric_observations)
                    if metric_observations else None
                )
                for comparator in report["loo_mae"]
            }
        report["validation_mae_by_metric"] = per_metric
        warnings: list[str] = []
        if len(training_ids) < 20:
            warnings.append(f"Only {len(training_ids)} independent training videos; results are exploratory.")
        if len(validation_ids) < 5:
            warnings.append(f"Only {len(validation_ids)} validation videos; improvement claims are unreliable.")
        if skipped:
            warnings.append(f"Skipped {len(skipped)} prompt task(s) without aligned human targets.")
        if dropped:
            warnings.append(f"Dropped {len(dropped)} constant question(s) within their applicable training prompt.")
        if not selected.get("meaningful_decision_tree"):
            warnings.append("No supported semantic split was found; score controls remain confined to an unsplit leaf model.")
        if selected.get("best_semantic_gain_over_base") is not None and not selected.get("semantic_gain_is_material"):
            warnings.append(
                "Semantic structure is shown for interpretation, but did not materially improve training-only grouped LOO over score-aware leaves."
            )
        report["warnings"] = warnings
        report["diagnostics"] = {
            "metric_ids": metric_ids,
            "n_independent_videos": len(all_item_ids),
            "n_prompt_tasks": len(tasks),
            "n_judge_variants": report["n_judge_variants"],
            "variant_counts": {key: task["variant_count"] for key, task in tasks.items()},
            "temperatures": sorted({temp for task in tasks.values() for temp in task["temperatures"]}),
            "skipped_tasks": skipped,
            "effective_train_items": len(training_ids),
            "effective_validation_items": len(validation_ids),
        }
        meta = {"n_items": len(all_item_ids), "n_prompt_tasks": len(tasks)}
        if warnings:
            meta["warning"] = " ".join(warnings)
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)
