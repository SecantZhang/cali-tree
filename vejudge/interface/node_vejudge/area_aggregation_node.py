"""Pure aggregation node for fan-in area judge results."""

from __future__ import annotations

from ...core.area import aggregate_area_results
from ...core.calibration.unit_affine import calibrate_area_result_units, fit_unit_calibrators
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class AreaAggregationNodeExecutor(NodeExecutor):
    node_type = "area_aggregation"
    category = "node_vejudge"
    input_sockets = {
        "area_judge_result": "area_judge_result",
        "unit_labels": "unit_labels",
    }
    multi_input_sockets = frozenset({"area_judge_result"})
    output_sockets = {
        "judge_result": "judge_result",
        "decomposition_features": "decomposition_features",
    }
    param_schema: dict = {}

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        incoming = ctx.inputs.get("area_judge_result")
        if incoming is None:
            return NodeRunResult(
                status="error",
                error="Area Aggregation requires at least one area_judge_result.",
            )
        bundles = incoming if isinstance(incoming, list) else [incoming]
        unit_models = fit_unit_calibrators(bundles, ctx.inputs.get("unit_labels") or [])
        calibrated = calibrate_area_result_units(bundles, unit_models)
        judge_result, features = aggregate_area_results(calibrated)
        return NodeRunResult(
            outputs={
                "judge_result": judge_result,
                "decomposition_features": features,
            },
            meta={
                "n_items": len(judge_result),
                "n_area_inputs": len(bundles),
                "unit_calibration": {
                    rubric: model["metadata"] for rubric, model in unit_models.items()
                },
            },
        )
