"""Rule/Tree Calibration Node — mines reusable decision rules from an upstream
Adversarial Calibration node's debates, has an **independent critic** answer them per
item, and fits an interpretable decision tree ``[base_score + rule booleans] -> human
score``. Reports in-sample AND leave-one-out MAE against four comparators so you can see
whether the mined semantic rules actually beat a plain bias correction.

Fit+report scope (v1): this evaluates whether the rule tree helps on the labeled batch;
it is not an unseen-item scorer (a DAG can't express a train/test split in one run, so
leave-one-out inside the node is the honest generalization read). The independent critic
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
from ...core.calibration.debate.schema import DebateTranscript
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeRunContext, NodeRunResult, register
from ._templates import CalibrationFitterNode, unaggregated_labels_error
from .cl_adversarial_node import _DIMENSIONS_FOR_METRIC, _resolve_human_context

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
        if (err := unaggregated_labels_error(labels)) is not None:
            return NodeRunResult(status="error", error=err)

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
            return NodeRunResult(
                outputs={"judge_rule": {}},
                meta={"dry_run": True, "n_items": len(usable_cr),
                      "estimated_calls": {"critic_calls": len(usable_cr)}},
            )

        try:
            require_live(ctx.allow_live, context=f"Rule/Tree Calibration over {len(usable_cr)} item(s)")
        except LiveCallNotAllowed as e:
            return NodeRunResult(status="error", error=str(e))

        # Human anchor (rater-count-weighted) + base score per item; drop items lacking a
        # usable human anchor (nothing to fit against).
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

        # --- mine + canonicalize the shared rule bank (checkpointed for re-run stability) ---
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

        # --- independent critic answers the bank per item (concurrent, checkpointed) ---
        concurrency = max(1, int(critic_config.get("concurrency") or 1))
        batch_size = max(1, int(p.get("batch_size") or 1))
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

        def _run(it: str) -> tuple[str, dict[str, Any], float]:
            if ctx.progress_cb:
                ctx.progress_cb("calibration_item_start", {"item_id": it})
            t0 = time.perf_counter()
            feats = extract_critic_features(
                sample=samples[it], judge_rationale=_judge_rationale(anchored[it]["cr"]),
                questions=bank, critic_engine=critic_engine,
            )
            return it, feats, round((time.perf_counter() - t0) * 1000, 1)

        done = 0
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
                ctx.checkpoint.put(f"{ctx.node_id}::{it}::rule_features", feats)
                if ctx.progress_cb:
                    ctx.progress_cb("calibration_item_done", {"item_id": it})
                done += 1
                if ctx.should_stop and ctx.should_stop():
                    for f in futs:
                        if not f.done():
                            f.cancel()

        # --- fit + evaluate (in-sample + LOO) ---
        bases = {it: anchored[it]["base"] for it in item_ids}
        humans = {it: anchored[it]["human"] for it in item_ids}
        feats_full = {it: [bases[it]] + [float(x) for x in booleans.get(it, [])] for it in item_ids}
        feature_names = ["base_score"] + [f"q{i + 1}" for i in range(len(bank))]
        report = fit_and_evaluate(
            item_ids=item_ids, bases=bases, humans=humans,
            feats_full=feats_full, feature_names=feature_names,
        )
        report["metric"] = metric_id
        report["bank"] = bank
        report["per_item"] = {
            it: {"base": bases[it], "human": round(humans[it], 2),
                 "booleans": booleans.get(it, []), "missing": missing.get(it, [])}
            for it in item_ids
        }
        meta = {"n_items": len(item_ids)}
        if item_timings:
            meta["item_timings"] = item_timings
        return NodeRunResult(outputs={"judge_rule": report}, meta=meta)
