"""Semantic Tree Calibration Node — an ontology-grounded sibling of the Rule/Tree node.

Same Model Calibration fitter contract (an upstream Adversarial Calibration node's
``calibration_results`` + labels + a critic engine → ``judge_rule``), but instead of a plain
CART over opaque ``qN`` booleans it fits an **ontology-weighted** semantic decision tree
whose features are concept-labeled:

  ``[base_score] + fm:<concept> counts + rule:<concept> critic booleans``

- ``fm:<concept>`` = per-item ``failure_mode_summary`` counts (how often the debate cited
  that taxonomy concept) — ontology-native, no extra calls.
- ``rule:<concept>`` = the independent critic's oriented answers to the mined bank,
  aggregated to the concept each question was tagged to (one extra tagging call).

Split selection is biased by ``ontology.concept_importance`` for the metric being
calibrated, and the report carries a ``semantic`` comparator alongside base/bias/linear/tree
so the Rule Comparison node shows the semantic tree head-to-head with the CART baseline on
the same features. Fit+report scope (in-sample + LOO), like the Rule/Tree node.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from ...core.calibration import SemanticDecisionTreeCalibrator
from ...core.calibration import ontology as onto
from ...core.calibration.debate.eval.concept_tagging import tag_questions_to_concepts
from ...core.calibration.debate.eval.critic_extraction import extract_critic_features
from ...core.calibration.debate.eval.question_bank import build_question_bank
from ...core.calibration.debate.eval.rule_extraction import extract_candidate_questions
from ...core.calibration.debate.eval.rule_fit import fit_and_evaluate
from ...core.calibration.debate.schema import DebateTranscript
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeRunContext, NodeRunResult, register
from ._templates import CalibrationFitterNode, unaggregated_labels_error
from .cl_adversarial_node import _DIMENSIONS_FOR_METRIC, _resolve_human_context
from .cl_rule_tree_node import _DEFAULT_ENGINE_KIND, _judge_rationale


def _failure_mode_counts(cr: dict[str, Any]) -> dict[str, int]:
    """Per-item taxonomy-keyed citation counts. Prefer the stored ``failure_mode_summary``;
    fall back to recomputing from the transcript turns (older checkpoints), mirroring
    ``cross_validate_calibration._ensure_failure_mode_summary``."""
    fms = cr.get("failure_mode_summary")
    if isinstance(fms, dict) and fms:
        return {k: int(v) for k, v in fms.items()}
    counts: dict[str, int] = {}
    for turn in (cr.get("transcript") or {}).get("turns", []):
        for mode in turn.get("failure_modes") or []:
            counts[mode] = counts.get(mode, 0) + 1
    return counts


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
        if (err := unaggregated_labels_error(labels)) is not None:
            return NodeRunResult(status="error", error=err)

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
            return NodeRunResult(
                outputs={"judge_rule": {}},
                meta={"dry_run": True, "n_items": len(usable_cr),
                      "estimated_calls": {"critic_calls": len(usable_cr), "tagging_calls": 1}},
            )

        try:
            require_live(ctx.allow_live, context=f"Semantic Tree Calibration over {len(usable_cr)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        override = p.get("human_dimension_override") or None
        dims = [override] if override else _DIMENSIONS_FOR_METRIC.get(metric_id, [])
        anchored: dict[str, dict[str, Any]] = {}
        for it, cr in usable_cr.items():
            agg = labels.get(it) if labels else None
            anchor = _resolve_human_context(agg, dims).get("anchor_score")
            if anchor is not None:
                anchored[it] = {"cr": cr, "human": float(anchor),
                                "base": float(cr["original_score"])}
        if not anchored:
            return NodeRunResult(
                status="error",
                error=f"No items with a usable human anchor for metric {metric_id} "
                "(check 'labels' cover the metric's mapped dimensions).",
            )

        temp_kw = {} if critic_config.get("temperature") is None else {"temperature": critic_config["temperature"]}
        critic_engine = get_engine(
            critic_config.get("engine_kind") or _DEFAULT_ENGINE_KIND.get(
                JUDGE_METRICS[metric_id].modality, "gpt"),
            history=ctx.run.history, model=critic_config.get("model"), creds=load_creds(),
            max_tokens=int(critic_config.get("max_tokens") or 4096), **temp_kw,
        )

        # --- mine + canonicalize the shared rule bank (checkpointed) ---
        bank_key = f"{ctx.node_id}::rule_bank"
        if ctx.checkpoint.has(bank_key):
            bank = ctx.checkpoint.get(bank_key)
        else:
            candidates: list[dict[str, Any]] = []
            for it, d in anchored.items():
                transcript_text = DebateTranscript.from_dict(d["cr"]["transcript"]).as_text()
                candidates.extend(extract_candidate_questions(
                    transcript_text=transcript_text, metric_id=metric_id, engine=critic_engine))
            bank = build_question_bank(candidates=candidates, engine=critic_engine,
                                       max_questions=max(1, int(p.get("max_questions") or 5)))
            ctx.checkpoint.put(bank_key, bank)

        # --- tag each mined rule to a taxonomy concept (checkpointed) ---
        tags_key = f"{ctx.node_id}::concept_tags"
        if ctx.checkpoint.has(tags_key):
            tags = ctx.checkpoint.get(tags_key)
        else:
            tags = tag_questions_to_concepts(bank=bank, engine=critic_engine)
            ctx.checkpoint.put(tags_key, tags)

        # --- independent critic answers the bank per item (concurrent, checkpointed) ---
        concurrency = max(1, int(critic_config.get("concurrency") or 1))
        item_ids = list(anchored)
        booleans: dict[str, list[int]] = {}
        missing: dict[str, list[str]] = {}
        tasks: list[str] = []
        for it in item_ids:
            fkey = f"{ctx.node_id}::{it}::rule_features"
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
                ctx.checkpoint.put(f"{ctx.node_id}::{it}::rule_features", feats)
                if ctx.progress_cb:
                    ctx.progress_cb("calibration_item_done", {"item_id": it})
                if ctx.should_stop and ctx.should_stop():
                    for f in futs:
                        if not f.done():
                            f.cancel()

        # --- assemble concept-labeled features ---
        fm_counts = {it: _failure_mode_counts(anchored[it]["cr"]) for it in item_ids}
        # fm:<concept> features only for concepts actually cited somewhere (lean feature space).
        fm_concepts = [
            k for k in onto.CONCEPTS
            if any(fm_counts[it].get(k, 0) > 0 for it in item_ids)
        ]
        # rule:<concept> features: aggregate (max = "any") the critic booleans of every mined
        # question tagged to that concept.
        concept_of_q = {i: t for i, t in enumerate(tags) if t}
        rule_concepts = sorted(set(concept_of_q.values()))

        def _rule_val(it: str, concept: str) -> int:
            vals = [booleans[it][i] for i, c in concept_of_q.items()
                    if c == concept and i < len(booleans.get(it, []))]
            return max(vals) if vals else 0

        feature_names = (
            ["base_score"]
            + [f"fm:{k}" for k in fm_concepts]
            + [f"rule:{k}" for k in rule_concepts]
        )
        bases = {it: anchored[it]["base"] for it in item_ids}
        humans = {it: anchored[it]["human"] for it in item_ids}
        feats_full = {
            it: (
                [bases[it]]
                + [float(fm_counts[it].get(k, 0)) for k in fm_concepts]
                + [float(_rule_val(it, k)) for k in rule_concepts]
            )
            for it in item_ids
        }
        feature_weights = {
            n: onto.concept_importance(onto.concept_for_feature(n), metric_id)
            for n in feature_names
        }

        # --- fit + evaluate (base/bias/linear/tree(CART) + semantic), in-sample + LOO ---
        report = fit_and_evaluate(
            item_ids=item_ids, bases=bases, humans=humans,
            feats_full=feats_full, feature_names=feature_names,
            extra_calibrators={
                "semantic": lambda: SemanticDecisionTreeCalibrator(feature_weights=feature_weights)
            },
        )

        # The exported tree + rule text should be the SEMANTIC tree (what this node is about),
        # not the CART one fit_and_evaluate exports by default. Refit on all items for display.
        if len(item_ids) >= 2:
            semantic = SemanticDecisionTreeCalibrator(feature_weights=feature_weights).fit(
                [feats_full[i] for i in item_ids], [humans[i] for i in item_ids],
                feature_names=feature_names,
            )
            sem_meta = semantic.metadata()
            report["tree"] = sem_meta.get("tree")
            report["tree_rule"] = sem_meta.get("rule_text", "")
            report["feature_importances"] = sem_meta.get("feature_importances", [])

        report["metric"] = metric_id
        report["bank"] = bank
        report["concept_tags"] = tags
        report["feature_weights"] = feature_weights
        # Self-contained labels for the UI tree tooltip: concept features -> concept label,
        # base_score -> a plain gloss.
        labels_map = {f"fm:{k}": f"cited: {c.label}" for k, c in onto.CONCEPTS.items()}
        labels_map.update({f"rule:{k}": f"critic: {c.label}" for k, c in onto.CONCEPTS.items()})
        labels_map["base_score"] = "the judge's own 1–5 score"
        report["feature_labels"] = {n: labels_map.get(n, n) for n in feature_names}
        report["per_item"] = {
            it: {"base": bases[it], "human": round(humans[it], 2),
                 "booleans": booleans.get(it, []), "missing": missing.get(it, [])}
            for it in item_ids
        }
        meta = {"n_items": len(item_ids)}
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)
