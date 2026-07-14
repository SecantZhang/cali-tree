"""Offline tests for the prompt-calibration A/B pipeline units (no LM/video calls)."""

import json

from vejudge.core.calibration.debate.eval import feature_extraction as fe
from vejudge.core.calibration.debate.eval.ab_debate import (
    build_judge_ab,
    build_proxy_ab,
    direction_word,
    run_ab_debate,
)
from vejudge.core.calibration.debate.eval.feature_extraction import (
    build_decision_extra_context,
    extract_features,
)
from vejudge.core.calibration.debate.eval.question_bank import build_question_bank
from vejudge.core.calibration.debate.eval.rule_extraction import extract_candidate_questions


class _ScriptedEngine:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        return {"content": json.dumps(self.payload), "model": "m",
                "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


_SAMPLE = {"item_id": "prj-x::0::peanut", "project": "prj-x", "prompt_idx": 0,
           "model": "peanut", "input": {"user_prompt": "assemble the montage"}}
_ORIGINAL = {"parsed": {"score_1_to_5": 2, "reasoning_lines": ["too repetitive"]}}


# --- mechanism B: the proxy never sees the human number ---

def test_direction_word_thresholds():
    assert "HIGHER" in direction_word(2.0, 3.8)
    assert "LOWER" in direction_word(4.0, 2.0)
    assert "about the same" in direction_word(3.0, 3.0)
    assert "unknown" in direction_word(None, 3.0)


def test_proxy_prompt_gets_direction_and_notes_but_not_the_number():
    spec = build_proxy_ab(
        sample=_SAMPLE, metric_id="M5", original_output=_ORIGINAL, transcript_text="",
        round_no=1, direction=direction_word(2.0, 3.84), notes=["the script repeats the line on purpose"],
    )
    assert "HIGHER" in spec.user
    assert "the script repeats the line on purpose" in spec.user
    # The exact human aggregate must never leak into the prompt (mechanism B).
    assert "3.84" not in spec.user and "3.8" not in spec.user


# --- mechanism A: framed as general-rule extraction ---

def test_proxy_and_judge_prompts_are_rule_focused():
    proxy = build_proxy_ab(sample=_SAMPLE, metric_id="M5", original_output=_ORIGINAL,
                           transcript_text="", round_no=1, direction="HIGHER", notes=[])
    assert "proposed_rule" in proxy.user and "general" in proxy.system.lower()
    judge = build_judge_ab(sample=_SAMPLE, metric_id="M5", original_output=_ORIGINAL,
                           transcript_text="x", round_no=1)
    assert "concede_rule" in judge.user and "refined_rule" in judge.user


def test_run_ab_debate_early_stops_when_judge_concedes():
    proxy = _ScriptedEngine({"proposed_rule": "If repetition is user-requested, don't penalize",
                             "reasoning_lines": ["a", "b"], "agrees_with_judge": False})
    judge = _ScriptedEngine({"reasoning_lines": ["fair"], "concede_rule": True,
                             "refined_rule": "Don't penalize user-requested repetition"})
    tr = run_ab_debate(sample=_SAMPLE, metric_id="M5", original_output=_ORIGINAL,
                       judge_engine=judge, proxy_engine=proxy, direction="HIGHER",
                       notes=[], max_rounds=3)
    assert tr["rounds_run"] == 1  # conceded round 1 -> stops
    assert [t["role"] for t in tr["turns"]] == ["human_proxy", "judge"]
    assert "user-requested repetition" in tr["transcript_text"]


# --- rule extraction ---

def test_extract_candidate_questions_parses_and_filters():
    eng = _ScriptedEngine({"questions": [
        {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"},
        {"question": "malformed", "raises_score_when": "maybe"},
    ]})
    qs = extract_candidate_questions(transcript_text="...", metric_id="M5", engine=eng)
    assert qs == [{"question": "Does the judge penalize user-requested repetition?",
                   "raises_score_when": "no"}]


def test_extract_candidate_questions_error_yields_empty():
    class Boom:
        def generate(self, *a, **k):
            raise RuntimeError("x")
    assert extract_candidate_questions(transcript_text="x", metric_id="M5", engine=Boom()) == []


# --- question bank aggregation ---

def test_build_question_bank_canonicalizes():
    cands = [{"question": "q1", "raises_score_when": "no"}]
    eng = _ScriptedEngine({"questions": [
        {"question": "Does the judge penalize user-requested repetition?", "raises_score_when": "no"}]})
    bank = build_question_bank(candidates=cands, engine=eng, max_questions=5)
    assert bank == [{"question": "Does the judge penalize user-requested repetition?",
                     "raises_score_when": "no"}]


def test_build_question_bank_empty_input_is_empty():
    assert build_question_bank(candidates=[], engine=_ScriptedEngine({})) == []


# --- cold feature extraction (orientation + missing handling) ---

def test_feature_extraction_orients_and_flags_missing(monkeypatch):
    questions = [
        {"question": "penalize user-requested repetition?", "raises_score_when": "no"},
        {"question": "penalize unstated constraint?", "raises_score_when": "no"},
    ]

    class FakeJudge:
        def run(self, sample, *, model=None, extra_context=None):
            # q1 = False -> matches raises_when 'no' -> oriented 1; q2 omitted -> missing/0.
            return {"parsed": {"score_1_to_5": 2, "reasoning_lines": ["x"],
                               "decision_answers": {"q1": False}}, "raw_content": "{}"}

    monkeypatch.setattr(fe, "make_judge", lambda metric_id, engine: FakeJudge())
    out = extract_features(sample={"item_id": "p::0::peanut"}, metric_id="M5",
                           questions=questions, engine=None)
    assert out["base_score"] == 2.0
    assert out["booleans"] == [1, 0]
    assert out["features"] == [2.0, 1.0, 0.0]
    assert out["missing"] == ["q2"]


def test_decision_extra_context_lists_questions():
    ctx = build_decision_extra_context([{"question": "Q about repetition?", "raises_score_when": "no"}])
    assert "decision_answers" in ctx and "q1" in ctx and "Q about repetition?" in ctx
