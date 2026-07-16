"""Malformed LLM JSON must degrade gracefully, not crash the calibration node.

Regression for a live `cl_semantic_tree` failure (JSONDecodeError bubbling out of a critic
call): several helpers called `parse_json_object` outside their try/except, so a
nondeterministic malformed response killed the whole run instead of yielding an empty
result. Each helper is exercised here with an engine that returns invalid JSON."""

from vejudge.core.calibration.debate.eval.concept_tagging import tag_questions_to_concepts
from vejudge.core.calibration.debate.eval.critic_extraction import extract_critic_features
from vejudge.core.calibration.debate.eval.question_bank import build_question_bank
from vejudge.core.calibration.debate.eval.rule_extraction import extract_candidate_questions


class _MalformedEngine:
    """Returns truncated / non-JSON content (what a flaky LLM response looks like)."""

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        return {"content": '{"questions": [ {"question": "x", '}  # invalid JSON


_SAMPLE = {"item_id": "prj-x::0::peanut", "input": {"user_prompt": "go"},
           "output": {"assembly_json": {"clips": ["a"]}}}
_QS = [{"question": "q1?", "raises_score_when": "no"},
       {"question": "q2?", "raises_score_when": "yes"}]


def test_rule_extraction_survives_malformed_json():
    assert extract_candidate_questions(
        transcript_text="t", metric_id="M5", engine=_MalformedEngine()) == []


def test_question_bank_falls_back_on_malformed_json():
    cands = [{"question": "keep me?", "raises_score_when": "no"}]
    bank = build_question_bank(candidates=cands, engine=_MalformedEngine(), max_questions=5)
    assert bank == [{"question": "keep me?", "raises_score_when": "no"}]  # dedup fallback


def test_critic_extraction_survives_malformed_json():
    feats = extract_critic_features(
        sample=_SAMPLE, judge_rationale="r", questions=_QS, critic_engine=_MalformedEngine())
    assert feats["booleans"] == [0, 0]
    assert feats["missing"] == ["q1", "q2"]


def test_concept_tagging_survives_malformed_json():
    assert tag_questions_to_concepts(bank=_QS, engine=_MalformedEngine()) == [None, None]
