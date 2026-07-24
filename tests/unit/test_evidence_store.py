import json

from vejudge.evidence import ArtifactRef, EvaluationUnit, EvidenceManifest, LocalEvidenceStore


def _manifest(artifact):
    unit = EvaluationUnit(
        unit_id="shot-0000-abc",
        unit_type="shot",
        start_seconds=0.0,
        end_seconds=4.0,
        applicable_rubrics=["visual_quality_temporal_stability"],
        artifacts=[artifact],
        measurements={"blur_score": 0.2},
    )
    return EvidenceManifest(
        item_id="item",
        cache_key="cache",
        evidence_hash="evidence",
        source_video_path="/video.mp4",
        source_video_sha256="source",
        preprocessing_config_hash="config",
        preprocessor_version="v1",
        units=[unit],
        timeline_provenance={"source": "otio"},
    )


def test_local_store_import_publish_roundtrip_and_query(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video bytes")
    store = LocalEvidenceStore(tmp_path / "evidence")
    artifact = store.import_artifact(source, kind="short_clip", media_type="video/mp4")
    manifest = _manifest(artifact)
    store.publish_manifest(manifest)

    loaded = store.get_manifest("cache")
    assert loaded is not None
    assert loaded.to_dict() == manifest.to_dict()
    assert loaded.units[0].artifacts[0].path != str(source)
    assert store.query_units(item_id="item", unit_type="shot")[0]["unit_id"] == "shot-0000-abc"


def test_corrupt_cached_manifest_is_not_reused(tmp_path):
    store = LocalEvidenceStore(tmp_path / "evidence")
    with store._connect() as db:
        db.execute(
            "INSERT INTO manifests VALUES (?, ?, ?, ?, ?, ?)",
            ("bad", "item", "hash", "ready", "{broken", "now"),
        )
    assert store.get_manifest("bad") is None


def test_manifest_with_missing_artifact_is_not_reused(tmp_path):
    store = LocalEvidenceStore(tmp_path / "evidence")
    artifact = ArtifactRef(
        artifact_id="missing", kind="short_clip",
        path=str(tmp_path / "gone.mp4"), sha256="x",
    )
    store.publish_manifest(_manifest(artifact))
    assert store.get_manifest("cache") is None
