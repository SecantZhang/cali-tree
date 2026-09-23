"""The ``judge_spec`` artifact — a judge's identity as data, produced by the Judge Prompt
node and consumed by the generic Judge node.

A metric used to be a `metrics` dropdown on the modality-split Judge nodes, but a metric is
really the judge's whole identity: a prompt + expected output schema + validation + a
human-dimension alignment binding. Making it a wired artifact lets each metric be its own
graph path and lets a future optimizer *produce* judges. Two kinds:

- **builtin** — `{kind, metric_id, modality, label}`: delegates entirely to the existing
  M1-M6 code (`core.judge.make_judge`, `core.prompts.build_prompt`, `postprocessing.align`'s
  `ALIGNMENT`). Zero rewrite of the six existing prompts.
- **custom** — a free-text prompt template + declared output/alignment, for new/experimental
  judges (and the future prompt optimizer). Runs through `run_custom_judge` below and carries
  its own `align: {dimension, score_path}` so the Eval node can align it generically.
"""

from __future__ import annotations

from typing import Any, Optional

from ...core.judge.parse import parse_json_object
from ...core.judge.validate import validate_judge_output
from ...core.rubric.definitions import JUDGE_METRICS
from ...database.dl_human_annotations import HUMAN_DIMENSIONS
from ...lm_engine.lm_template import LMEngine
from ...postprocessing.align import score_at_path

# M1..M6, in rubric order — the built-in preset options on the Judge Prompt node.
PRESET_METRIC_IDS: list[str] = list(JUDGE_METRICS.keys())
# The human dimensions a custom judge may target (its alignment binding for Eval).
TARGET_DIMENSIONS: list[str] = list(HUMAN_DIMENSIONS)
CUSTOM_TARGET_DIMENSIONS: list[str] = [*TARGET_DIMENSIONS, "satisfaction"]


def builtin_spec(metric_id: str) -> dict[str, Any]:
    m = JUDGE_METRICS[metric_id]
    return {"kind": "builtin", "metric_id": metric_id, "modality": m.modality, "label": metric_id}


def spec_key(spec: dict[str, Any]) -> str:
    """The key a judge result is filed under: the metric id (builtin) or spec id (custom)."""
    return spec["metric_id"] if spec.get("kind") == "builtin" else spec.get("spec_id", "custom")


def spec_modality(spec: dict[str, Any]) -> str:
    return spec.get("modality", "text")


def _template_fields(sample: dict[str, Any]) -> dict[str, Any]:
    """Flat, string-friendly view of a sample for `{placeholder}` filling in custom prompts."""
    fields: dict[str, Any] = {
        "item_id": sample.get("item_id", ""),
        "project": sample.get("project", ""),
        "model": sample.get("model", ""),
        "use_case": sample.get("use_case", ""),
    }
    for k, v in (sample.get("input") or {}).items():
        fields[k] = v
    for k, v in (sample.get("output") or {}).items():
        fields[k] = v
    return fields


def fill_template(template: str, sample: dict[str, Any]) -> str:
    """Substitute only the known ``{placeholder}`` tokens; leave every other brace literal.

    Deliberately NOT ``str.format`` — a custom judge's template almost always contains a
    literal JSON output example (``{"score": ...}``), which ``str.format`` misparses as a
    format field/spec ("Invalid format specifier"). A targeted replace passes any such JSON
    (and any unknown ``{token}``) through verbatim, and can't crash the run.
    """
    out = template
    for key, value in _template_fields(sample).items():
        out = out.replace("{" + key + "}", "" if value is None else str(value))
    return out


def run_custom_judge(
    spec: dict[str, Any], engine: LMEngine, sample: dict[str, Any], *, model: Optional[str] = None
) -> dict[str, Any]:
    """Run one custom judge spec over a sample — mirrors ``core.judge.Judge.run``'s output
    dict shape (so downstream code is uniform) and additionally carries the ``align`` binding.
    """
    system = fill_template(spec.get("system") or "", sample) or None
    user = fill_template(spec.get("user_template") or "", sample)
    media: Optional[list[dict[str, Any]]] = None
    modality = spec.get("modality")
    if modality in {"video", "image"}:
        parts: list[dict[str, Any]] = []
        # A source/original video, when the sample carries one (e.g. VE-Bench edits), is
        # attached FIRST so a judge can compare edited-vs-source (instruction following,
        # preservation). Peanut assembly samples have no source_video_path, so this is a
        # no-op there and the edited video stays the only attachment.
        if modality == "video":
            src = (sample.get("input") or {}).get("source_video_path", "")
            out = (sample.get("output") or {}).get("output_video_path", "")
        else:
            src = (sample.get("input") or {}).get("source_image_path", "")
            out = (sample.get("output") or {}).get("edited_image_path", "")
        if src:
            parts.append({"type": modality, "path": src})
        if out:
            parts.append({"type": modality, "path": out})
        media = parts or None

    result: dict[str, Any] = {
        "judge": spec.get("label") or spec_key(spec),
        "metric_id": spec_key(spec),
        "spec_kind": "custom",
        "prompt_version": spec.get("version", "custom-v1"),
        "prompt_system": system,
        "prompt_user": user,
        "parsed": None,
        "raw_content": "",
        # Carried so the Eval node can align a custom judge without an ALIGNMENT entry.
        "align": {"dimension": spec.get("target_dimension"), "score_path": spec.get("score_path")},
    }

    try:
        out = engine.generate(user, media_inputs=media, system=system, model=model)
    except Exception as e:  # noqa: BLE001 - recorded so the run continues
        result["error"] = str(e)
        result["validation_flags"] = ["engine_error"]
        return result

    content = out.get("content") or ""
    result["raw_content"] = content
    result["promptTokens"] = out.get("promptTokens")
    result["completionTokens"] = out.get("completionTokens")
    result["totalTokens"] = out.get("totalTokens")
    result["model"] = out.get("model")

    try:
        parsed = parse_json_object(content)
    except (ValueError, TypeError):
        parsed = None
    result["parsed"] = parsed

    validation = validate_judge_output(parsed, required_fields=spec.get("expected_fields") or [])
    result["validation_flags"] = validation.flags
    result["valid"] = validation.ok
    if isinstance(parsed, dict) and spec.get("score_path"):
        result["score"] = score_at_path(parsed, spec["score_path"])
    return result
