"""Config-only node producing one fixed area-rubric specification."""

from __future__ import annotations

from ...core.area import AREA_RUBRICS, area_rubric_spec
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class AreaRubricNodeExecutor(NodeExecutor):
    node_type = "area_rubric"
    category = "node_vejudge"
    input_sockets: dict = {}
    output_sockets = {"area_rubric_spec": "area_rubric_spec"}
    param_schema = {
        "rubric": {
            "type": "enum", "options": list(AREA_RUBRICS),
            "default": "transition_smoothness",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        rubric_id = str(ctx.params.get("rubric") or "transition_smoothness")
        try:
            spec = area_rubric_spec(rubric_id)
        except KeyError as error:
            return NodeRunResult(status="error", error=str(error))
        return NodeRunResult(
            outputs={"area_rubric_spec": spec},
            meta={"rubric_id": rubric_id, "version": spec["version"]},
        )
