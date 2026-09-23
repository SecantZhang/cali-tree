"""Coconut Source Node — loads every rendered coconut item (ordinal-run-subdir layout)."""

from __future__ import annotations

from ..server.registry import register
from .eval_source_base import EvalSourceNodeExecutor


@register
class CoconutSourceNodeExecutor(EvalSourceNodeExecutor):
    node_type = "coconut_source"
    MODEL = "coconut"
