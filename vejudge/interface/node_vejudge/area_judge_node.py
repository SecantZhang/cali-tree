"""Unit-scoped, checkpointed area judge executor."""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ...core.area import judge_area_unit, select_units
from ...evidence import EvidenceBundle
from ...lm_engine import LiveCallNotAllowed, get_engine, load_creds, require_live
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class AreaJudgeNodeExecutor(NodeExecutor):
    node_type = "area_judge"
    category = "node_vejudge"
    input_sockets = {
        "samples": "samples",
        "evidence_bundle": "evidence_bundle",
        "engine_config": "engine_config",
        "area_rubric_spec": "area_rubric_spec",
    }
    output_sockets = {"area_judge_result": "area_judge_result"}
    param_schema = {
        "boundary_cap": {"type": "number", "default": 32, "min": 0},
        "shot_cap": {"type": "number", "default": 24, "min": 0},
        "sequence_cap": {"type": "number", "default": 12, "min": 0},
        "audio_event_cap": {"type": "number", "default": 24, "min": 0},
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        evidence_raw = ctx.inputs.get("evidence_bundle")
        engine_config = ctx.inputs.get("engine_config")
        spec = ctx.inputs.get("area_rubric_spec")
        missing = [
            name for name, value in (
                ("samples", samples), ("evidence_bundle", evidence_raw),
                ("engine_config", engine_config), ("area_rubric_spec", spec),
            ) if value is None
        ]
        if missing:
            return NodeRunResult(
                status="error", error=f"Area Judge requires: {', '.join(missing)}"
            )
        try:
            evidence = EvidenceBundle.from_dict(evidence_raw)
        except (KeyError, TypeError, ValueError) as error:
            return NodeRunResult(status="error", error=f"Invalid evidence bundle: {error}")

        caps = {
            "edit_boundary": int(ctx.params.get("boundary_cap", 32)),
            "shot": int(ctx.params.get("shot_cap", 24)),
            "sequence": int(ctx.params.get("sequence_cap", 12)),
            "audio_event": int(ctx.params.get("audio_event_cap", 24)),
        }
        selections: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
        estimated_calls = 0
        for item_id, manifest in evidence.manifests.items():
            selected, coverage = select_units(
                [unit.to_dict() for unit in manifest.units],
                rubric_id=spec["rubric_id"],
                unit_types=spec["unit_types"],
                caps=caps,
            )
            selections[item_id] = (selected, coverage)
            estimated_calls += len(selected)

        empty_output = {
            item_id: {
                "rubric_id": spec["rubric_id"],
                "rubric_version": spec["version"],
                "evidence_hash": evidence.manifests[item_id].evidence_hash,
                "selection": coverage,
                "units": [],
            }
            for item_id, (_selected, coverage) in selections.items()
        }
        if ctx.dry_run:
            return NodeRunResult(
                outputs={"area_judge_result": empty_output},
                meta={
                    "dry_run": True, "n_items": len(selections),
                    "estimated_calls": {"area_judge_calls": estimated_calls},
                },
            )
        try:
            require_live(
                ctx.allow_live,
                context=f"Area Judge '{spec['label']}' over {estimated_calls} unit(s)",
            )
        except LiveCallNotAllowed as error:
            return NodeRunResult(status="error", error=str(error))

        temp_kw = {} if engine_config.get("temperature") is None else {
            "temperature": engine_config["temperature"]
        }
        engine = get_engine(
            engine_config.get("engine_kind") or "gemini",
            history=ctx.run.history, model=engine_config.get("model"), creds=load_creds(),
            max_tokens=int(engine_config.get("max_tokens") or 4096), **temp_kw,
        )
        provenance = {
            "engine_kind": engine_config.get("engine_kind"),
            "model": engine_config.get("model"),
            "temperature": engine_config.get("temperature"),
            "rubric_id": spec["rubric_id"],
            "rubric_version": spec["version"],
        }
        variant = hashlib.sha256(
            json.dumps({"spec": spec, "engine": provenance}, sort_keys=True).encode()
        ).hexdigest()[:16]
        outputs = empty_output
        tasks: list[tuple[str, dict[str, Any]]] = []
        for item_id, (selected, _coverage) in selections.items():
            manifest = evidence.manifests[item_id]
            for unit in selected:
                key = (
                    f"{ctx.node_id}::{variant}::{manifest.evidence_hash}::"
                    f"{item_id}::{spec['rubric_id']}::{unit['unit_id']}"
                )
                cached = ctx.checkpoint.get(key) if ctx.checkpoint.has(key) else None
                if cached is not None:
                    outputs[item_id]["units"].append(cached)
                else:
                    tasks.append((item_id, unit))
        if ctx.progress_cb:
            ctx.progress_cb("area_judge_progress_init", {"total": len(tasks)})

        def run_one(item_id: str, unit: dict[str, Any]) -> tuple[str, str, dict[str, Any], float]:
            manifest = evidence.manifests[item_id]
            started = time.perf_counter()
            result = judge_area_unit(
                spec, engine, samples[item_id], manifest.to_dict(), unit
            )
            result["judge_provenance"] = provenance
            key = (
                f"{ctx.node_id}::{variant}::{manifest.evidence_hash}::"
                f"{item_id}::{spec['rubric_id']}::{unit['unit_id']}"
            )
            return item_id, key, result, (time.perf_counter() - started) * 1000

        timings: list[dict[str, Any]] = []
        with ThreadPoolExecutor(
            max_workers=max(1, int(engine_config.get("concurrency") or 1))
        ) as pool:
            futures = [pool.submit(run_one, item_id, unit) for item_id, unit in tasks]
            for future in as_completed(futures):
                item_id, key, result, elapsed = future.result()
                outputs[item_id]["units"].append(result)
                timings.append({
                    "item_id": item_id, "unit_id": result["unit_id"], "ms": round(elapsed, 1)
                })
                if result.get("valid"):
                    ctx.checkpoint.put(key, result)
                if ctx.progress_cb:
                    ctx.progress_cb(
                        "area_judge_unit",
                        {"item_id": item_id, "unit_id": result["unit_id"]},
                    )
        for result in outputs.values():
            result["units"].sort(key=lambda unit: (
                float(unit.get("start_seconds") or 0), str(unit.get("unit_id"))
            ))
        return NodeRunResult(
            outputs={"area_judge_result": outputs},
            meta={
                "n_items": len(outputs), "n_calls": len(tasks),
                "n_cached": estimated_calls - len(tasks), "unit_timings": timings,
            },
        )
