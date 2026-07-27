"""Workflow node for cached edit-aware video decomposition."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ... import config
from ...evidence import EvidenceBundle, LocalEvidenceStore
from ...preprocessing import (
    PREPROCESSOR_VERSION,
    EditDecompositionConfig,
    EditDecompositionPreprocessor,
    VideoDependencyError,
)
from ...preprocessing.edit_decomposition import video_dependency_status
from ..server.registry import NodeExecutor, NodeRunContext, NodeRunResult, register


@register
class EditDecompositionNodeExecutor(NodeExecutor):
    node_type = "edit_decomposition"
    category = "node_preprocessing"
    input_sockets = {"samples": "samples"}
    output_sockets = {"evidence_bundle": "evidence_bundle"}
    param_schema = {
        "boundary_context_seconds": {"type": "number", "default": 2.0, "min": 0.1},
        "reconcile_tolerance_seconds": {"type": "number", "default": 0.1, "min": 0.0},
        "max_sequence_seconds": {"type": "number", "default": 30.0, "min": 3.0},
        "scene_threshold": {"type": "number", "default": 27.0, "min": 1.0},
        "silence_threshold_db": {"type": "number", "default": -40.0},
        "minimum_silence_seconds": {"type": "number", "default": 0.5, "min": 0.1},
        "extract_artifacts": {"type": "bool", "default": True},
        "cache_policy": {
            "type": "enum", "options": ["reuse_if_present", "force_recompute"],
            "default": "reuse_if_present",
        },
    }

    def run(self, ctx: NodeRunContext) -> NodeRunResult:
        samples = ctx.inputs.get("samples")
        if samples is None:
            return NodeRunResult(
                status="error",
                error="Edit Decomposition requires a Dataset node's 'samples' output.",
            )
        p = ctx.params
        decomposition_config = EditDecompositionConfig(
            boundary_context_seconds=float(p.get("boundary_context_seconds", 2.0)),
            reconcile_tolerance_seconds=float(p.get("reconcile_tolerance_seconds", 0.1)),
            max_sequence_seconds=float(p.get("max_sequence_seconds", 30.0)),
            scene_threshold=float(p.get("scene_threshold", 27.0)),
            silence_threshold_db=float(p.get("silence_threshold_db", -40.0)),
            minimum_silence_seconds=float(p.get("minimum_silence_seconds", 0.5)),
            extract_artifacts=bool(p.get("extract_artifacts", True)),
        )
        bundle = EvidenceBundle(
            schema_version="evidence-bundle-v1",
            preprocessing_config=asdict(decomposition_config),
            preprocessing_config_hash=decomposition_config.hash(),
            preprocessor_version=PREPROCESSOR_VERSION,
        )
        store = LocalEvidenceStore(config.EVIDENCE_ROOT)
        processor = EditDecompositionPreprocessor(store, decomposition_config)
        force = p.get("cache_policy") == "force_recompute"
        cache_hits = 0
        failures: dict[str, str] = {}

        if ctx.dry_run:
            for item_id, sample in samples.items():
                try:
                    cache_key, _video_hash = processor.cache_key(sample)
                    cached = None if force else store.get_manifest(cache_key)
                    if cached:
                        bundle.manifests[item_id] = cached
                        cache_hits += 1
                except (FileNotFoundError, OSError) as error:
                    failures[item_id] = str(error)
            return NodeRunResult(
                outputs={"evidence_bundle": bundle.to_dict()},
                meta={
                    "dry_run": True,
                    "n_items": len(samples),
                    "cached_manifests": cache_hits,
                    "would_decompose": len(samples) - cache_hits - len(failures),
                    "dependency_status": video_dependency_status(),
                    "failures": failures,
                },
            )

        for index, (item_id, sample) in enumerate(samples.items(), start=1):
            if ctx.should_stop and ctx.should_stop():
                break
            try:
                cache_key, _video_hash = processor.cache_key(sample)
                was_cached = not force and store.get_manifest(cache_key) is not None
                manifest = processor.run(sample, force=force)
                bundle.manifests[item_id] = manifest
                cache_hits += int(was_cached)
            except (VideoDependencyError, FileNotFoundError, RuntimeError, OSError) as error:
                failures[item_id] = str(error)
            if ctx.progress_cb:
                ctx.progress_cb(
                    "decomposition_item",
                    {"item_id": item_id, "current": index, "total": len(samples)},
                )
        if not bundle.manifests and failures:
            return NodeRunResult(
                status="error",
                error=next(iter(failures.values())),
                outputs={"evidence_bundle": bundle.to_dict()},
                meta={"failures": failures},
            )
        return NodeRunResult(
            outputs={"evidence_bundle": bundle.to_dict()},
            meta={
                "n_items": len(samples),
                "n_manifests": len(bundle.manifests),
                "cache_hits": cache_hits,
                "failures": failures,
                "evidence_root": str(config.EVIDENCE_ROOT),
            },
        )
