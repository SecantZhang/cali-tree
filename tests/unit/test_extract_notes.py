import json

from vejudge.database.dl_peanut_eval.extract_notes import extract_peanut_assembly_from_notes


def _write(tmp_path, obj):
    p = tmp_path / "notes.json"
    p.write_text(json.dumps(obj))
    return str(p)


def test_v2_schema(tmp_path):
    notes = {
        "prompt": "make a reel",
        "stages": [{
            "name": "OrchestratorRefineV2",
            "output": {"finalClipIds": ["c1", "c2"], "trimmedWordIds": [3, 4]},
            "subStages": [{"input": {"currentTimeline": "0,Hello,0.5\n1,world,0.4"}}],
        }],
    }
    a = extract_peanut_assembly_from_notes(_write(tmp_path, notes))
    assert a["a_roll"]["final_clip_ids"] == ["c1", "c2"]
    assert "Hello world" in a["transcript"]


def test_v4_schema(tmp_path):
    notes = {
        "prompt": "outline video",
        "stages": [{
            "name": "OrchestratorRefineV4",
            "output": {
                "finalSegments": [{"video_id": "8", "start_ms": 0, "end_ms": 100}],
                "finalTracks": {
                    "v1": [{"video_id": "8", "start_ms": 0, "end_ms": 100}],
                    "v2": [{"video_id": "100", "start_ms": 0, "end_ms": 3000,
                            "caption": "a mural that says FREMONT"}],
                },
            },
        }],
    }
    a = extract_peanut_assembly_from_notes(_write(tmp_path, notes))
    assert a["a_roll"]["n_segments"] == 1
    assert a["a_roll"]["track_sizes"] == {"v1": 1, "v2": 1}
    assert len(a["b_roll"]) == 1 and "FREMONT" in a["b_roll"][0]["caption"]


def test_unknown_stage_falls_back_to_empty(tmp_path):
    notes = {"prompt": "x", "stages": [{"name": "SomethingElse", "output": {}}]}
    a = extract_peanut_assembly_from_notes(_write(tmp_path, notes))
    assert a["a_roll"] == {} and a["b_roll"] == [] and a["notes_prompt"] == "x"
