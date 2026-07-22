"""Rule Comparison Node — renders the calibration comparison from an upstream Rule/Tree
Calibration node's ``judge_rule`` report as a standalone eval node: the MAE table
(base / base+bias / score-only linear / rule models, training and held-out), the
mined rule bank, the fitted decision tree, and a one-line verdict on whether the mined
rules actually beat a plain bias correction *held-out*.

Pure display: it re-surfaces an already-computed report (the upstream node did all the
critic calls + the fit), so it makes no gateway calls and is never gated by dry-run/--live.
This mirrors the Eval node's "read a report, present the numbers" role, but for the
rule/tree calibration comparison instead of the human-vs-judge agreement gap.
"""

from __future__ import annotations

import random
from typing import Any

from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register

# Label + presentation order for known comparators. The report renders whichever keys are
# actually present in the upstream judge_rule (so a Semantic Tree node's extra `semantic`
# row appears automatically, while a Rule/Tree node stays four rows). Mirrors
# ClRuleTreeSecondaryTab's COMPARATOR_LABELS.
_COMPARATOR_LABELS: dict[str, str] = {
    "base": "(a) base only",
    "bias": "(b) base + global bias",
    "score_linear": "(c) linear[base score only]",
    "linear": "(d) linear[base+rules]",
    "tree": "(e) tree[base+rules]",
    "semantic": "(f) semantic tree[ontology]",
}
_COMPARATOR_ORDER = ["base", "bias", "score_linear", "linear", "tree", "semantic"]
# The rule-based models (vs. the plain base / bias-shift baselines) — a report "helps" only
# if one of these beats the bias correction held-out.
_RULE_MODELS = ("semantic", "tree", "linear")


def _bootstrap_interval(values: list[float], *, draws: int = 2000) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(0)
    means = sorted(
        sum(rng.choice(values) for _ in values) / len(values)
        for _ in range(draws)
    )
    return means[int(0.025 * (draws - 1))], means[int(0.975 * (draws - 1))]


@register
class ClRuleEvalNodeExecutor(NodeExecutor):
    node_type = "cl_rule_eval"
    category = "node_eval"
    input_sockets = {"judge_rule": "judge_rule"}
    output_sockets = {"comparison": "metrics_report"}
    param_schema: dict = {}
    label = "Rule Comparison"

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        judge_rule = ctx.inputs.get("judge_rule")
        if judge_rule is None:
            return NodeRunResult(
                status="error",
                error="Rule Comparison Node requires a 'judge_rule' input (wire a Rule/Tree "
                "Calibration node's `judge_rule` output).",
            )

        insample = judge_rule.get("insample_mae") or {}
        loo = judge_rule.get("loo_mae") or {}
        present = set(insample) | set(loo)
        keys = [k for k in _COMPARATOR_ORDER if k in present]
        keys += sorted(k for k in present if k not in _COMPARATOR_ORDER)
        rows = [
            {"key": k, "label": _COMPARATOR_LABELS.get(k, k),
             "insample": insample.get(k), "loo": loo.get(k)}
            for k in keys
        ]

        # First test the predeclared score-only linear calibration against a global bias.
        # Then test whether semantic rules add anything beyond that score-only model. This
        # prevents a learned raw-score slope from being misattributed to the rule features.
        bias_loo = loo.get("bias")
        score_linear_loo = loo.get("score_linear")
        best_rule_key: str | None = None
        best_rule_loo: float | None = None
        for k in _RULE_MODELS:
            v = loo.get(k)
            if isinstance(v, (int, float)) and (best_rule_loo is None or v < best_rule_loo):
                best_rule_key, best_rule_loo = k, float(v)

        evaluation_mode = judge_rule.get("evaluation_mode", "grouped_loo_exploratory")
        n_validation = int(judge_rule.get("n_validation_items") or 0)
        per_item_errors = judge_rule.get("per_item_errors") or {}
        score_improvements = [
            float(errors["bias"]) - float(errors["score_linear"])
            for errors in per_item_errors.values()
            if isinstance(errors, dict)
            and isinstance(errors.get("bias"), (int, float))
            and isinstance(errors.get("score_linear"), (int, float))
        ]
        score_ci_low, score_ci_high = _bootstrap_interval(score_improvements)
        score_improvement = (
            float(bias_loo) - float(score_linear_loo)
            if isinstance(bias_loo, (int, float))
            and isinstance(score_linear_loo, (int, float)) else None
        )
        paired_improvements = [
            float(errors["bias"]) - float(errors[best_rule_key])
            for errors in per_item_errors.values()
            if best_rule_key is not None
            and isinstance(errors, dict)
            and isinstance(errors.get("bias"), (int, float))
            and isinstance(errors.get(best_rule_key), (int, float))
        ]
        ci_low, ci_high = _bootstrap_interval(paired_improvements)
        improvement = (
            float(bias_loo) - best_rule_loo
            if best_rule_loo is not None and isinstance(bias_loo, (int, float)) else None
        )
        rule_vs_score_improvements = [
            float(errors["score_linear"]) - float(errors[best_rule_key])
            for errors in per_item_errors.values()
            if best_rule_key is not None
            and isinstance(errors, dict)
            and isinstance(errors.get("score_linear"), (int, float))
            and isinstance(errors.get(best_rule_key), (int, float))
        ]
        rule_ci_low, rule_ci_high = _bootstrap_interval(rule_vs_score_improvements)
        rule_increment = (
            float(score_linear_loo) - best_rule_loo
            if best_rule_loo is not None and isinstance(score_linear_loo, (int, float))
            else None
        )

        score_calibration_passes = bool(
            evaluation_mode == "frozen_holdout"
            and n_validation >= 5
            and score_improvement is not None
            and score_improvement >= 0.05
            and score_ci_low > 0
        )
        rules_incrementally_help = bool(
            evaluation_mode == "frozen_holdout"
            and n_validation >= 5
            and rule_increment is not None
            and rule_increment >= 0.05
            and rule_ci_low > 0
        )
        best_calibration_passes = bool(
            evaluation_mode == "frozen_holdout"
            and n_validation >= 5
            and improvement is not None
            and improvement >= 0.05
            and ci_low > 0
        )

        if best_rule_loo is None or not isinstance(bias_loo, (int, float)):
            verdict = "Not enough data to compare held-out MAE."
            beats_bias = False
        elif evaluation_mode != "frozen_holdout":
            verdict = (
                "Exploratory grouped LOO only: the rule bank was not isolated from held-out "
                "items, so no generalization claim is made."
            )
            beats_bias = False
        elif n_validation < 5:
            verdict = (
                f"Insufficient validation data: {n_validation} independent video(s); at least "
                "5 are required before claiming improvement over global bias."
            )
            beats_bias = False
        elif best_calibration_passes:
            verdict = (
                f"Calibration helps: {best_rule_key} beats a plain bias correction "
                f"held-out ({float(best_rule_loo):.2f} vs {float(bias_loo):.2f} MAE, "
                f"Δ {float(improvement):.2f}, 95% bootstrap CI "
                f"[{ci_low:.2f}, {ci_high:.2f}]). "
                + (
                    f"Rules add further signal: {best_rule_key} improves another "
                    f"{float(rule_increment):.2f} MAE (95% CI "
                    f"[{rule_ci_low:.2f}, {rule_ci_high:.2f}])."
                    if rules_incrementally_help else
                    f"Its incremental gain over score-only calibration is not conclusive "
                    f"(best incremental Δ {float(rule_increment or 0):.2f}, 95% CI "
                    f"[{rule_ci_low:.2f}, {rule_ci_high:.2f}])."
                )
            )
            beats_bias = True
        else:
            verdict = (
                f"Indistinguishable from global bias: {best_rule_key} {best_rule_loo:.2f} "
                f"vs bias {float(bias_loo):.2f} held-out MAE (Δ {float(improvement or 0):.2f}, "
                f"95% bootstrap CI [{ci_low:.2f}, {ci_high:.2f}])."
            )
            beats_bias = False

        report = {
            "n_items": judge_rule.get("n_items"),
            "metric": judge_rule.get("metric"),
            "rows": rows,
            "insample_mae": insample,
            "loo_mae": loo,
            "tree_rule": judge_rule.get("tree_rule"),
            "tree": judge_rule.get("tree"),
            "bank": judge_rule.get("bank"),
            "verdict": verdict,
            "beats_bias": beats_bias,
            "evaluation_mode": evaluation_mode,
            "n_validation_items": n_validation,
            "improvement_over_bias": improvement,
            "improvement_ci_95": [ci_low, ci_high],
            "best_calibration_beats_bias": best_calibration_passes,
            "score_calibration_beats_bias": score_calibration_passes,
            "score_calibration_improvement": score_improvement,
            "score_calibration_ci_95": [score_ci_low, score_ci_high],
            "rules_beat_score_linear": rules_incrementally_help,
            "rule_increment_over_score_linear": rule_increment,
            "rule_increment_ci_95": [rule_ci_low, rule_ci_high],
            "diagnostics": judge_rule.get("diagnostics"),
            "warnings": judge_rule.get("warnings") or [],
        }

        ctx.run.write_json(f"rule_eval_{ctx.node_id}.json", report)
        ctx.run.logger.info("%s[%s]: %s", self.label, ctx.node_id, verdict)
        return NodeRunResult(
            outputs={"comparison": report},
            meta={"n_items": judge_rule.get("n_items"), "beats_bias": beats_bias},
        )
