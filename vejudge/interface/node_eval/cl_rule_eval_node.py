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

        if best_rule_loo is None or not isinstance(bias_loo, (int, float)):
            verdict = "Not enough data to compare held-out (LOO) MAE."
            beats_bias = False
        elif best_rule_loo < bias_loo:
            verdict = (
                f"Rules help: {best_rule_key} beats a plain bias correction held-out "
                f"({best_rule_loo:.2f} vs {bias_loo:.2f} LOO MAE, "
                f"Δ {bias_loo - best_rule_loo:.2f})."
            )
            beats_bias = True
        else:
            verdict = (
                f"Rules do NOT beat a plain bias correction held-out ({best_rule_key} "
                f"{best_rule_loo:.2f} vs bias {float(bias_loo):.2f} LOO MAE) — the bias "
                "term alone captures the correction at this n."
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
        }

        ctx.run.write_json(f"rule_eval_{ctx.node_id}.json", report)
        ctx.run.logger.info("%s[%s]: %s", self.label, ctx.node_id, verdict)
        return NodeRunResult(
            outputs={"comparison": report},
            meta={"n_items": judge_rule.get("n_items"), "beats_bias": beats_bias},
        )
