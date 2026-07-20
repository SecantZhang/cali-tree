"""GET /api/nodes — palette metadata for the registered node types."""

from __future__ import annotations

from fastapi import APIRouter

from ... import node_types  # noqa: F401 - import side effect: registers dataset/judge/eval
from ..registry import NODE_EXECUTORS
from ..schemas import NodeTypeOut

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeTypeOut])
def list_node_types() -> list[NodeTypeOut]:
    return [
        NodeTypeOut(
            type=cls.node_type,
            category=cls.category,
            subcategory=cls.subcategory,
            multi_input_sockets=sorted(cls.multi_input_sockets),
            input_sockets=dict(cls.input_sockets),
            output_sockets=dict(cls.output_sockets),
            param_schema=dict(cls.param_schema),
        )
        for cls in sorted(NODE_EXECUTORS.values(), key=lambda c: c.node_type)
    ]
