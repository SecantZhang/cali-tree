"""Offline tests for the independent-critic rule-boolean answering (no LM calls)."""

import json

from vejudge.core.calibration.debate.eval.critic_extraction import (
    build_critic_prompt,
    extract_critic_features,
)


class _ScriptedEngine:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        self.media_inputs = media_inputs
        return {"content": json.dumps(self.payload)}


_SAMPLE = {"item_id": "prj-x::0::peanut", "input": {"user_prompt": "assemble the montage"},
           "output": {"assembly_json": {"clips": ["a", "b"]}}}
_QUESTIONS = [
    {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"},
    {"question": "Does the judge penalize an unstated constraint?", "raises_score_when": "no"},
]


def test_prompt_frames_auditing_not_rescoring_and_lists_questions():
    prompt = build_critic_prompt(_SAMPLE, "the judge said the audio was repetitive", _QUESTIONS)
    assert "auditing" in prompt.lower() or "audit" in prompt.lower()
    assert "decision_answers" in prompt
    assert "q1" in prompt and "q2" in prompt
    assert "assemble the montage" in prompt  # item context present
    assert "the judge said the audio was repetitive" in prompt  # rationale present


def test_independent_critic_can_flag_the_judge_unlike_a_cold_self_answer():
    # The critic answers q1=false -> matches raises_when 'no' -> oriented 1 (the
    # score-raising condition is present). q2 omitted -> missing/0.
    eng = _ScriptedEngine({"decision_answers": {"q1": False}})
    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="...", questions=_QUESTIONS, critic_engine=eng,
    )
    assert feats["booleans"] == [1, 0]
    assert feats["missing"] == ["q2"]
    assert feats["media_grounded"] is False


def test_video_capable_critic_is_grounded_in_rendered_edit():
    sample = {
        **_SAMPLE,
        "output": {**_SAMPLE["output"], "output_video_path": "/tmp/rendered.mp4"},
    }
    eng = _ScriptedEngine({"decision_answers": {"q1": False, "q2": True}})
    eng.supports_video = True
    feats = extract_critic_features(
        sample=sample, judge_rationale="...", questions=_QUESTIONS, critic_engine=eng,
    )
    assert eng.media_inputs == [{"type": "video", "path": "/tmp/rendered.mp4"}]
    assert feats["media_grounded"] is True
    assert feats["critic_version"] == "rule-critic-v4-retry-complete"


def test_graded_answers_become_signed_semantic_evidence():
    eng = _ScriptedEngine({"decision_answers": {
        "q1": {"answer": False, "strength": 2, "evidence": "requested repetition"},
        "q2": {"answer": True, "strength": 3, "evidence": "unstated constraint"},
    }})
    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="...", questions=_QUESTIONS, critic_engine=eng,
    )
    assert feats["booleans"] == [1, 0]
    assert feats["semantic_values"] == [0.6667, -1.0]


def test_critic_call_failure_yields_all_zero_not_a_crash():
    class Boom:
        def generate(self, *a, **k):
            raise RuntimeError("gateway down")

    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="...", questions=_QUESTIONS, critic_engine=Boom(),
    )
    assert feats["booleans"] == [0, 0]
    assert feats["missing"] == ["q1", "q2"]
    assert feats["critic_attempts"] == 3
    assert len(feats["critic_errors"]) == 3


def test_incomplete_critic_response_is_retried_until_complete():
    class EventuallyComplete:
        def __init__(self):
            self.calls = 0

        def generate(self, *a, **k):
            self.calls += 1
            answers = {"q1": {"answer": False, "strength": 2}}
            if self.calls >= 2:
                answers["q2"] = {"answer": True, "strength": 3}
            return {"content": json.dumps({"decision_answers": answers})}

    eng = EventuallyComplete()
    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="...", questions=_QUESTIONS, critic_engine=eng,
    )
    assert eng.calls == 2
    assert feats["missing"] == []
    assert feats["booleans"] == [1, 0]
    assert feats["critic_attempts"] == 2


def test_no_questions_is_empty():
    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="...", questions=[], critic_engine=_ScriptedEngine({}),
    )
    assert feats == {"booleans": [], "raw_answers": {}, "missing": []}
