import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vejudge.preprocessing.edit_decomposition import (
    EditDecompositionConfig,
    EditDecompositionPreprocessor,
    _sequence_ranges,
    parse_otio_timeline,
    reconcile_boundaries,
)
from vejudge.evidence import LocalEvidenceStore


def _rt(value, rate=10):
    return {"value": value, "rate": rate}


def test_otio_parser_reconstructs_output_time_rates_gaps_and_transitions(tmp_path):
    timeline = {
        "tracks": {"children": [{
            "kind": "Video",
            "children": [
                {"OTIO_SCHEMA": "Clip.2", "name": "A",
                 "source_range": {"start_time": _rt(20), "duration": _rt(30)}},
                {"OTIO_SCHEMA": "Gap.1", "name": "gap",
                 "source_range": {"duration": _rt(5)}},
                {"OTIO_SCHEMA": "Transition.1", "name": "dissolve",
                 "in_offset": _rt(2), "out_offset": _rt(3)},
                {"OTIO_SCHEMA": "Clip.2", "name": "A again",
                 "source_range": {"start_time": _rt(20), "duration": _rt(10)}},
            ],
        }]},
    }
    path = tmp_path / "timeline.otio"
    path.write_text(json.dumps(timeline))
    parsed = parse_otio_timeline(str(path))
    assert [clip["name"] for clip in parsed["clips"]] == ["A", "A again"]
    assert parsed["clips"][0]["source_start"] == 2.0
    assert parsed["clips"][1]["output_start"] == 3.5
    assert parsed["gaps"][0]["output_start"] == 3.0
    assert parsed["transitions"][0]["in_offset"] == 0.2
    assert parsed["boundaries"] == [3.5]


def test_reconcile_retains_matched_and_unmatched_boundaries():
    result = reconcile_boundaries([1.0, 4.0], [1.05, 8.0], tolerance=0.1)
    assert result[0]["provenance"] == ["timeline", "rendered"]
    assert result[1]["provenance"] == ["timeline"]
    assert result[2]["provenance"] == ["rendered"]


def test_sequence_fallback_splits_at_nearest_shot_boundary():
    ranges = _sequence_ranges(
        70.0, [10.0, 27.0, 55.0], [], max_seconds=30.0
    )
    assert ranges == [(0.0, 27.0), (27.0, 55.0), (55.0, 70.0)]


def test_cache_identity_changes_with_video_content_and_config(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"one")
    sample = {"item_id": "i", "output": {"output_video_path": str(video)}}
    store = LocalEvidenceStore(tmp_path / "evidence")
    first = EditDecompositionPreprocessor(
        store, EditDecompositionConfig(extract_artifacts=False)
    ).cache_key(sample)[0]
    changed_config = EditDecompositionPreprocessor(
        store, EditDecompositionConfig(extract_artifacts=False, scene_threshold=99)
    ).cache_key(sample)[0]
    video.write_bytes(b"two")
    changed_video = EditDecompositionPreprocessor(
        store, EditDecompositionConfig(extract_artifacts=False)
    ).cache_key(sample)[0]
    assert len({first, changed_config, changed_video}) == 3


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg binaries are required for the real-media decomposition check",
)
def test_real_media_decomposition_extracts_cached_artifacts(tmp_path):
    video = tmp_path / "cut-with-audio.mp4"
    command = [
        shutil.which("ffmpeg"),
        "-y",
        "-f", "lavfi", "-i", "color=c=red:s=160x90:d=2:r=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2:r=10",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
        "-filter_complex",
        "[0:v][1:a][2:v][3:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(video),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    sample = {"item_id": "real", "output": {"output_video_path": str(video)}}
    store = LocalEvidenceStore(tmp_path / "evidence")
    preprocessor = EditDecompositionPreprocessor(
        store,
        scene_detector=lambda _path, _threshold: ([2.0], []),
    )
    manifest = preprocessor.run(sample)

    assert manifest.video_metadata["has_audio"] is True
    assert {"shot", "edit_boundary", "sequence", "audio_event"} <= {
        unit.unit_type for unit in manifest.units
    }
    artifact_kinds = {
        artifact.kind for unit in manifest.units for artifact in unit.artifacts
    }
    assert {"short_clip", "keyframe", "waveform"} <= artifact_kinds
    for unit in manifest.units:
        for artifact in unit.artifacts:
            assert artifact.path.startswith(str(store.objects_root))
            assert Path(artifact.path).is_file()

    cached = preprocessor.run(sample)
    assert cached.evidence_hash == manifest.evidence_hash
    assert len(cached.units) == len(manifest.units)
