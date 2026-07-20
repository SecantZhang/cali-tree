"""Peanut Source Node — loads every rendered peanut item.

One of three per-model source nodes (see ``eval_source_base``); all share the loading logic
and differ only in ``MODEL``. Sampling/filtering is the downstream Dataset node's job, and
several sources can fan into one Dataset (which merges their pools).
"""

from __future__ import annotations

from ..server.registry import register
from .eval_source_base import EvalSourceNodeExecutor


@register
class PeanutSourceNodeExecutor(EvalSourceNodeExecutor):
    node_type = "peanut_source"
    MODEL = "peanut"
