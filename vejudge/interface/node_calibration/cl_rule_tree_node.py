"""Rule/Tree Calibration Node — mines reusable decision rules from an upstream
Adversarial Calibration node's debates, has an **independent critic** answer them per
item, and fits an interpretable decision tree ``[base_score + rule booleans] -> human
score``. New nodes mine a frozen rule bank on a deterministic training partition and
report item-macro held-out MAE; legacy graphs retain explicitly exploratory grouped LOO.
The independent critic
(a separate LM, not the judge being calibrated) is the fix for the finding that a judge
won't self-report its own errors.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

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
from .evaluation_support import (
    build_observations,
    evaluation_cache_suffix,
    filter_constant_questions,
    preflight_diagnostics,
    semantic_summary_text,
    stable_holdout_split,
)

_DEFAULT_ENGINE_KIND = {"text": "gpt", "video": "gemini"}


def _judge_rationale(cr: dict[str, Any]) -> str:
    """The upstream judge's ORIGINAL rationale (what the critic audits) — deliberately
    not the debate's own conclusions, so the critic forms an independent view."""
    parsed = ((cr.get("transcript") or {}).get("initial_judge_result") or {}).get("parsed") or {}
    lines = parsed.get("reasoning_lines")
    if isinstance(lines, list) and lines:
        return " ".join(str(x) for x in lines)
    return str(cr.get("reasoning") or "")


@register
class ClRuleTreeNodeExecutor(CalibrationFitterNode):
    # Model Calibration role — inherits the fitter I/O contract (samples +
    # calibration_results + labels + critic_engine -> judge_rule) from CalibrationFitterNode;
    # see node_calibration._templates.
    node_type = "cl_rule_tree"
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
                    error=f"Rule/Tree Calibration Node requires a '{name}' input.",
                )
        overlap = sorted(set(samples) & set(calibration_results))
        # A usable item has a debate transcript + a numeric original (base) score.
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
                      }},
            )

        try:
            require_live(ctx.allow_live, context=f"Rule/Tree Calibration over {len(usable_cr)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        # Human targets + base score per item. Aggregated Dataset modes provide one
        # target; `none` provides every raw rating and is expanded into repeated fit
        # observations below.
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

        # Mine only from de-leaked structured summaries in the training partition.
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

        def _run(it: str) -> tuple[str, dict[str, Any], float]:
            if ctx.progress_cb:
                ctx.progress_cb("calibration_item_start", {"item_id": it})
            t0 = time.perf_counter()
            feats = extract_critic_features(
                sample=samples[it], judge_rationale=_judge_rationale(anchored[it]["cr"]),
                questions=bank, critic_engine=critic_engine,
            )
            return it, feats, round((time.perf_counter() - t0) * 1000, 1)

        item_timings: list[dict[str, Any]] = []
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

        filtered_bank, filtered_booleans, prevalence, dropped = filter_constant_questions(
            bank, booleans, training_ids,
        )
        observation_ids, observation_item, bases, humans, feats_full, weights = build_observations(
            anchored, filtered_booleans,
        )
        feature_names = ["base_score"] + [f"q{i + 1}" for i in range(len(filtered_bank))]
        report = fit_and_evaluate(
            item_ids=observation_ids, bases=bases, humans=humans,
            feats_full=feats_full, feature_names=feature_names,
            loo_groups=observation_item,
            observation_weights=weights,
            train_groups=training_ids if evaluation_mode == "frozen_holdout" else None,
            validation_groups=validation_ids if evaluation_mode == "frozen_holdout" else None,
        )
        report["metric"] = metric_id
        report["bank"] = filtered_bank
        report["candidate_bank"] = bank
        report["feature_prevalence"] = prevalence
        report["dropped_features"] = dropped
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
        report["per_item"] = {
            it: {"base": anchored[it]["base"],
                 "human": [round(v, 2) for v in anchored[it]["humans"]]
                 if len(anchored[it]["humans"]) > 1 else round(anchored[it]["humans"][0], 2),
                 "booleans": filtered_booleans.get(it, []), "missing": missing.get(it, [])}
            for it in item_ids
        }
        meta = {"n_items": len(item_ids), "warning": " ".join(warnings) if warnings else None}
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)
