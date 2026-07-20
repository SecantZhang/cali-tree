"""Calibration node role templates — the shared I/O contracts for the two calibration
sub-categories, so every node in a sub-category has the SAME input/output sockets and any
new implementation conforms by construction (subclass, inherit the sockets, implement
``run``).

Two roles (see ``interface.md``):

- **Agent Calibration** (``subcategory="agent"``) — *producers*. Run LLM agents (a judge
  vs. a human-proxy debate) over a judged dataset to generate a calibration signal.
  Contract: ``samples + judge_result + labels + judge_engine + human_engine``
  → ``calibration_results + general_calibration``.
- **Model Calibration** (``subcategory="model"``) — *fitters*. Consume a producer's
  ``calibration_results`` and fit an interpretable calibration model — a rule/decision
  tree today, other ``Calibrator`` variants (isotonic, ordinal, Bradley-Terry, …) next.
  Contract: ``samples + calibration_results + labels + critic_engine`` → ``judge_rule``
  (the fitted calibration model/rule).

These bases are abstract (no ``node_type``, never ``@register``ed). A concrete node
subclasses exactly one, inherits its ``category``/``subcategory`` + sockets, and only
supplies ``node_type``, ``param_schema``, and ``run``. Do not redeclare the sockets in a
subclass — inheriting them is what keeps a sub-category unified. If a new node genuinely
needs a different I/O shape, that is the signal it is a *different role* (a new template),
not a member of this one.
"""

from __future__ import annotations

from typing import ClassVar

from ..server.registry import NodeExecutor

CALIBRATION_CATEGORY = "node_calibration"


class CalibrationProducerNode(NodeExecutor):
    """Agent Calibration role: judged dataset + human labels → calibration signal."""

    category: ClassVar[str] = CALIBRATION_CATEGORY
    subcategory: ClassVar[str] = "agent"
    input_sockets: ClassVar[dict[str, str]] = {
        "samples": "samples",
        "judge_result": "judge_result",
        "labels": "labels",
        "judge_engine": "engine_config",
        "human_engine": "engine_config",
    }
    output_sockets: ClassVar[dict[str, str]] = {
        "calibration_results": "calibration_results",
        # Item-independent corpus calibration note — wire into a Judge Node's
        # `general_calibration` input to apply it dataset-wide to unseen items.
        "general_calibration": "general_calibration",
    }


class CalibrationFitterNode(NodeExecutor):
    """Model Calibration role: a producer's calibration_results → a fitted model/rule."""

    category: ClassVar[str] = CALIBRATION_CATEGORY
    subcategory: ClassVar[str] = "model"
    input_sockets: ClassVar[dict[str, str]] = {
        "samples": "samples",
        "calibration_results": "calibration_results",
        "labels": "labels",
        "critic_engine": "engine_config",
    }
    output_sockets: ClassVar[dict[str, str]] = {
        "judge_rule": "judge_rule",
    }
