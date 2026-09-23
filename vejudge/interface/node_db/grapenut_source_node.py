"""Grapenut Source Node — loads every rendered grapenut item (indexed videos/ layout)."""

from __future__ import annotations

from ..server.registry import register
from .eval_source_base import EvalSourceNodeExecutor


@register
class GrapenutSourceNodeExecutor(EvalSourceNodeExecutor):
    node_type = "grapenut_source"
    MODEL = "grapenut"
