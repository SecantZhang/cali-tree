"""run_custom_judge video attachment: a source video (when the sample has one, e.g.
VE-Bench edits) is attached before the edited video; peanut-style samples (edited only)
stay single-video."""

import json

from vejudge.interface.node_vejudge.judge_spec import fill_template, run_custom_judge


def test_fill_template_leaves_literal_json_braces_intact():
    # Regression: a custom judge template almost always shows a JSON output example. str.format
    # would misparse `{"score": <1-10>}` ("Invalid format specifier"); fill_template must
    # substitute {user_prompt} and pass the JSON through verbatim.
    tmpl = (
        'Rate: "{user_prompt}"\n'
        'Respond JSON only: {"overall_editing_score": <integer 1-10>, "reasoning": "<one>"}'
    )
    out = fill_template(tmpl, {"input": {"user_prompt": "make it rain"}})
    assert 'Rate: "make it rain"' in out
    assert '{"overall_editing_score": <integer 1-10>, "reasoning": "<one>"}' in out


def test_fill_template_leaves_unknown_placeholder_literal():
    assert fill_template("hi {nope}", {"input": {}}) == "hi {nope}"

_SPEC = {
    "kind": "custom", "spec_id": "eq", "label": "eq", "modality": "video",
    "system": "s", "user_template": "rate {user_prompt}",
    "expected_fields": ["overall_editing_score"], "score_path": "overall_editing_score",
    "target_dimension": "edit_quality", "version": "v1",
}


class _CaptureEngine:
    def __init__(self):
        self.media = None

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        self.media = media_inputs
        return {"content": json.dumps({"overall_editing_score": 7}), "model": "m",
                "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def test_source_then_edited_when_both_present():
    eng = _CaptureEngine()
    sample = {"input": {"user_prompt": "x", "source_video_path": "/s.mp4"},
              "output": {"output_video_path": "/e.mp4"}}
    res = run_custom_judge(_SPEC, eng, sample)
    assert [m["path"] for m in eng.media] == ["/s.mp4", "/e.mp4"]  # source first, edited second
    assert res["score"] == 7.0
    assert res["align"] == {"dimension": "edit_quality", "score_path": "overall_editing_score"}


def test_edited_only_when_no_source():
    eng = _CaptureEngine()
    sample = {"input": {"user_prompt": "x"}, "output": {"output_video_path": "/e.mp4"}}
    run_custom_judge(_SPEC, eng, sample)
    assert [m["path"] for m in eng.media] == ["/e.mp4"]


def test_no_media_when_no_videos():
    eng = _CaptureEngine()
    run_custom_judge(_SPEC, eng, {"input": {"user_prompt": "x"}, "output": {}})
    assert eng.media is None
