"""Rule Comparison Node — renders the calibration comparison from an upstream Rule/Tree
Calibration node's ``judge_rule`` report as a standalone eval node: the four-way MAE table
(base / base+bias / linear[base+rules] / tree[base+rules], in-sample AND held-out LOO), the
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
    "linear": "(c) linear[base+rules]",
    "tree": "(d) tree[base+rules]",
    "semantic": "(e) semantic tree[ontology]",
}
_COMPARATOR_ORDER = ["base", "bias", "linear", "tree", "semantic"]
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

        # The mined rules earn their keep only if a rule model (semantic / tree / linear)
        # beats a plain bias shift HELD-OUT (LOO). In-sample MAE always improves with more
        # features, so it is never the test — the verdict reads the LOO column only.
        bias_loo = loo.get("bias")
        best_rule_key: str | None = None
        best_rule_loo: float | None = None
        for k in _RULE_MODELS:
            v = loo.get(k)
            if isinstance(v, (int, float)) and (best_rule_loo is None or v < best_rule_loo):
                best_rule_key, best_rule_loo = k, float(v)

        evaluation_mode = judge_rule.get("evaluation_mode", "grouped_loo_exploratory")
        n_validation = int(judge_rule.get("n_validation_items") or 0)
        per_item_errors = judge_rule.get("per_item_errors") or {}
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
        elif improvement is not None and improvement >= 0.05 and ci_low > 0:
            verdict = (
                f"Rules help: {best_rule_key} beats a plain bias correction held-out "
                f"({best_rule_loo:.2f} vs {bias_loo:.2f} MAE, "
                f"Δ {improvement:.2f}, 95% bootstrap CI [{ci_low:.2f}, {ci_high:.2f}])."
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
            "diagnostics": judge_rule.get("diagnostics"),
            "warnings": judge_rule.get("warnings") or [],
        }

        ctx.run.write_json(f"rule_eval_{ctx.node_id}.json", report)
        ctx.run.logger.info("%s[%s]: %s", self.label, ctx.node_id, verdict)
        return NodeRunResult(
            outputs={"comparison": report},
            meta={"n_items": judge_rule.get("n_items"), "beats_bias": beats_bias},
        )
