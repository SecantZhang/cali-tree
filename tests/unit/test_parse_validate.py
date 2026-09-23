from vejudge.core.judge.parse import parse_json_object
from vejudge.core.judge.validate import validate_judge_output


def test_parse_strips_fences():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('{"b": 2}') == {"b": 2}


def test_validate_ok():
    parsed = {"score_1_to_5": 4, "reasoning_lines": ["a", "b", "c"]}
    res = validate_judge_output(parsed, required_fields=["score_1_to_5"])
    assert res.ok and not res.flags


def test_validate_flags_out_of_range():
    parsed = {"score_1_to_5": 9, "reasoning_lines": ["x"]}
    res = validate_judge_output(parsed, required_fields=["score_1_to_5"])
    assert not res.ok
    assert any("out_of_range" in f for f in res.flags)


def test_validate_flags_missing_and_empty():
    res = validate_judge_output({"reasoning_lines": []}, required_fields=["score_1_to_5"])
    assert "missing_field:score_1_to_5" in res.flags
    assert "empty_rationale" in res.flags


def test_validate_invalid_json():
    res = validate_judge_output(None)
    assert res.flags == ["invalid_json"]


def test_validate_nested_m6_scores():
    parsed = {
        "voiceover_visual_match": {"score_1_to_5": 5, "reasoning": "ok"},
        "voiceover_continuity": {"score_1_to_5": 4, "reasoning": "ok"},
        "visual_continuity": {"score_1_to_5": 3, "reasoning": "ok"},
        "overall_av_sync_score": 4,
        "reasoning_lines": ["a", "b"],
    }
    res = validate_judge_output(parsed)
    assert res.ok, res.flags
