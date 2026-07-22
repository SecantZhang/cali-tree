"""Semantic Tree Calibration Node — an ontology-grounded sibling of the Rule/Tree node.

Same Model Calibration fitter contract (an upstream Adversarial Calibration node's
``calibration_results`` + labels + a critic engine → ``judge_rule``), but instead of a plain
CART over opaque ``qN`` booleans it fits an **ontology-weighted** semantic decision tree
whose deployment-safe features are concept-labeled independent-critic answers:

  ``[base_score] + rule:<concept>:qN``

Grounded debate failure-mode counts are deliberately excluded from fitted features because
they depend on human-label access that is unavailable for a fresh deployment item.

Split selection is biased by ``ontology.concept_importance`` for the metric being
calibrated, and the report carries a ``semantic`` comparator alongside base/bias/linear/tree
so the Rule Comparison node shows the semantic tree head-to-head with the CART baseline on
the same frozen training/validation split.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ...core.calibration import SemanticDecisionTreeCalibrator
from ...core.calibration import ontology as onto
from ...core.calibration.debate.eval.concept_tagging import tag_questions_to_concepts
from ...core.calibration.debate.eval.critic_extraction import extract_critic_features
from ...core.calibration.debate.eval.question_bank import build_question_bank
from ...core.calibration.debate.eval.rule_extraction import extract_candidate_questions
from ...core.calibration.debate.eval.rule_fit import fit_and_evaluate
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
    preflight_diagnostics,
    semantic_summary_text,
    stable_holdout_split,
)

@register
class ClSemanticTreeNodeExecutor(CalibrationFitterNode):
    # Model Calibration role — inherits the fitter I/O contract (samples +
    # calibration_results + labels + critic_engine -> judge_rule) from CalibrationFitterNode.
    node_type = "cl_semantic_tree"
    param_schema = {
        "max_questions": {"type": "number", "default": 5, "min": 1},
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
        calibration_results = ctx.inputs.get("calibration_results")
        labels = ctx.inputs.get("labels")
        critic_config = ctx.inputs.get("critic_engine")
        for name, val in (("samples", samples), ("calibration_results", calibration_results),
                          ("labels", labels), ("critic_engine", critic_config)):
            if val is None:
                return NodeRunResult(
                    status="error",
                    error=f"Semantic Tree Calibration Node requires a '{name}' input.",
                )
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
        max_questions = max(1, int(p.get("max_questions") or 5))
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
            bank = build_question_bank(candidates=candidates, engine=critic_engine,
                                       max_questions=max_questions)
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
        missing: dict[str, list[str]] = {}
        tasks: list[str] = []
        for it in item_ids:
            fkey = f"{ctx.node_id}::{it}::rule_features::{cache_suffix}"
            if ctx.checkpoint.has(fkey):
                cached = ctx.checkpoint.get(fkey)
                booleans[it] = cached["booleans"]
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
        filtered_bank, filtered_booleans, prevalence, dropped = filter_constant_questions(
            bank, booleans, training_ids,
        )
        dropped_indices = {entry["question_index"] for entry in dropped}
        kept_indices = [entry["question_index"] for entry in prevalence
                        if entry["question_index"] not in dropped_indices]
        filtered_tags = [tags[index] if index < len(tags) else None for index in kept_indices]
        feature_names = ["base_score"] + [
            f"rule:{(filtered_tags[index] or 'untagged')}:q{index + 1}"
            for index in range(len(filtered_bank))
        ]
        observation_ids, observation_item, bases, humans, feats_full, weights = build_observations(
            anchored, filtered_booleans,
        )
        feature_weights = {
            n: onto.concept_importance(onto.concept_for_feature(n), metric_id)
            for n in feature_names
        }

        # --- fit + evaluate (base/bias/linear/tree(CART) + semantic), in-sample + LOO ---
        report = fit_and_evaluate(
            item_ids=observation_ids, bases=bases, humans=humans,
            feats_full=feats_full, feature_names=feature_names,
            loo_groups=observation_item,
            observation_weights=weights,
            train_groups=training_ids if evaluation_mode == "frozen_holdout" else None,
            validation_groups=validation_ids if evaluation_mode == "frozen_holdout" else None,
            extra_calibrators={
                "semantic": lambda: SemanticDecisionTreeCalibrator(feature_weights=feature_weights)
            },
        )

        # The exported tree + rule text should be the SEMANTIC tree (what this node is about),
        # not the CART one fit_and_evaluate exports by default. Refit on all items for display.
        display_ids = [obs for obs in observation_ids
                       if observation_item[obs] in set(training_ids)]
        if len(set(observation_item[obs] for obs in display_ids)) >= 2:
            semantic = SemanticDecisionTreeCalibrator(feature_weights=feature_weights).fit(
                [feats_full[i] for i in display_ids],
                [humans[i] for i in display_ids],
                feature_names=feature_names,
                sample_weight=[weights[i] for i in display_ids],
            )
            sem_meta = semantic.metadata()
            report["tree"] = sem_meta.get("tree")
            report["tree_rule"] = sem_meta.get("rule_text", "")
            report["feature_importances"] = sem_meta.get("feature_importances", [])

        report["metric"] = metric_id
        report["bank"] = filtered_bank
        report["candidate_bank"] = bank
        report["concept_tags"] = filtered_tags
        report["feature_prevalence"] = prevalence
        report["dropped_features"] = dropped
        report["feature_weights"] = feature_weights
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
                 "booleans": filtered_booleans.get(it, []), "missing": missing.get(it, [])}
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
        report["diagnostics"] = diagnostics
        report["warnings"] = warnings
        meta = {"n_items": len(item_ids), "warning": " ".join(warnings) if warnings else None}
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)
