import json

from vejudge.database.dl_peanut_eval.extract_otio import extract_assembly_from_otio

_OTIO = {
    "OTIO_SCHEMA": "Timeline.1",
    "tracks": {
        "OTIO_SCHEMA": "Stack.1",
        "children": [
            {"OTIO_SCHEMA": "Track.1", "kind": "Video", "children": [
                {"OTIO_SCHEMA": "Clip.2", "name": "intro",
                 "source_range": {"start_time": {"value": 0.0}, "duration": {"value": 30.0}}},
                {"OTIO_SCHEMA": "Clip.2", "name": "b-roll",
                 "source_range": {"start_time": {"value": 30.0}, "duration": {"value": 12.5}}},
                {"OTIO_SCHEMA": "Gap.1", "name": "gap"},  # non-clip, must be skipped
            ]},
            {"OTIO_SCHEMA": "Track.1", "kind": "Audio", "children": [
                {"OTIO_SCHEMA": "Clip.2", "name": "voiceover",
                 "source_range": {"start_time": {"value": 0.0}, "duration": {"value": 42.0}}},
            ]},
        ],
    },
}


def test_extracts_clips_with_track_and_timing(tmp_path):
    p = tmp_path / "t.otio"
    p.write_text(json.dumps(_OTIO))
    asm = extract_assembly_from_otio(str(p))
    assert asm["source"] == "otio"
    assert asm["n_clips"] == 3  # 2 video + 1 audio; the Gap is skipped
    assert sorted(asm["tracks"]) == ["Audio", "Video"]
    intro = next(c for c in asm["clips"] if c["name"] == "intro")
    assert intro["track"] == "Video" and intro["duration"] == 30.0 and intro["start"] == 0.0


def test_missing_or_bad_file_returns_empty(tmp_path):
    assert extract_assembly_from_otio("") == {}
    assert extract_assembly_from_otio(str(tmp_path / "nope.otio")) == {}
    bad = tmp_path / "bad.otio"
    bad.write_text("not json {")
    assert extract_assembly_from_otio(str(bad)) == {}


def test_no_clips_returns_empty(tmp_path):
    p = tmp_path / "empty.otio"
    p.write_text(json.dumps({"OTIO_SCHEMA": "Timeline.1", "tracks": {"children": []}}))
    assert extract_assembly_from_otio(str(p)) == {}
