"""Run a fixed area rubric over one stable evidence unit."""

from __future__ import annotations

from typing import Any

from ...lm_engine.lm_template.base import LMEngine
from ..judge.parse import parse_json_object

SEVERITIES = {"none", "minor", "major", "critical"}


def _clip_path(unit: dict[str, Any]) -> str:
    for artifact in unit.get("artifacts") or []:
        if artifact.get("kind") == "short_clip" and artifact.get("path"):
            return str(artifact["path"])
    return ""


def judge_area_unit(
    spec: dict[str, Any], engine: LMEngine, sample: dict[str, Any],
    manifest: dict[str, Any], unit: dict[str, Any],
) -> dict[str, Any]:
    clip = _clip_path(unit)
    result: dict[str, Any] = {
        "item_id": sample.get("item_id"),
        "unit_id": unit.get("unit_id"),
        "unit_type": unit.get("unit_type"),
        "rubric_id": spec["rubric_id"],
        "rubric_version": spec["version"],
        "evidence_hash": manifest.get("evidence_hash"),
        "start_seconds": unit.get("start_seconds"),
        "end_seconds": unit.get("end_seconds"),
        "duration_seconds": max(
            0.0, float(unit.get("end_seconds") or 0) - float(unit.get("start_seconds") or 0)
        ),
        "valid": False,
        "validation_flags": [],
    }
    if not clip:
        result.update({
            "error": "No short_clip artifact for unit",
            "validation_flags": ["missing_media"],
        })
        return result

    user_prompt = str((sample.get("input") or {}).get("user_prompt") or "")
    prompt = f"""
Rubric: {spec['label']}
Unit type: {unit.get('unit_type')}
Unit timestamps in full video: {float(unit.get('start_seconds') or 0):.3f}s to {float(unit.get('end_seconds') or 0):.3f}s
User edit request: {user_prompt or '(not available)'}
Deterministic measurements: {unit.get('measurements') or {}}

{spec['instruction']}

Return exactly:
{{
  "score_1_to_5": <number 1..5>,
  "severity": "none" | "minor" | "major" | "critical",
  "confidence": <number 0..1>,
  "rationale": "<specific local evidence>",
  "cited_timestamps": [<seconds relative to the supplied clip>]
}}
""".strip()
    try:
        response = engine.generate(
            prompt,
            media_inputs=[{"type": "video", "path": clip}],
            system=spec.get("system"),
        )
    except Exception as error:  # noqa: BLE001 - one bad unit must not stop a video
        result.update({
            "error": str(error),
            "validation_flags": ["engine_error"],
        })
        return result
    content = response.get("content") or ""
    result.update({
        "raw_content": content,
        "model": response.get("model"),
        "promptTokens": response.get("promptTokens"),
        "completionTokens": response.get("completionTokens"),
        "totalTokens": response.get("totalTokens"),
    })
    try:
        parsed = parse_json_object(content)
    except (TypeError, ValueError):
        parsed = None
    result["parsed"] = parsed
    flags: list[str] = []
    if not isinstance(parsed, dict):
        flags.append("invalid_json")
    else:
        score = parsed.get("score_1_to_5")
        confidence = parsed.get("confidence")
        severity = parsed.get("severity")
        rationale = parsed.get("rationale")
        cited = parsed.get("cited_timestamps")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 1 <= score <= 5:
            flags.append("invalid_score")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            flags.append("invalid_confidence")
        if severity not in SEVERITIES:
            flags.append("invalid_severity")
        if not isinstance(rationale, str) or not rationale.strip():
            flags.append("empty_rationale")
        if not isinstance(cited, list) or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) for value in cited
        ):
            flags.append("invalid_cited_timestamps")
    result["validation_flags"] = flags
    result["valid"] = not flags
    if result["valid"]:
        result.update({
            "score": float(parsed["score_1_to_5"]),
            "severity": parsed["severity"],
            "confidence": float(parsed["confidence"]),
            "rationale": parsed["rationale"],
            "cited_timestamps": [float(value) for value in parsed["cited_timestamps"]],
        })
    return result
