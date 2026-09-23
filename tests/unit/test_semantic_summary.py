import json

import pytest

from vejudge.core.calibration.debate.calibrated_result import _TENDENCY
from vejudge.core.calibration.debate.schema import DebateTranscript, DebateTurn
from vejudge.core.calibration.debate.semantic_summary import (
    SemanticSummary,
    llm_summary,
    render_summary,
    rule_based_summary,
    validate_summary,
)


def _turn(role, semantic=None, *, evidence=None, reasoning=None, round_no=1):
    parsed = {
        "score_1_to_5": 3,
        "reasoning_lines": reasoning or ["The abrupt cuts repeatedly break visual continuity."],
        "evidence": evidence or ["Abrupt cuts return to the same static shot after each insert."],
    }
    if semantic is not None:
        parsed["semantic_summary"] = semantic
    return DebateTurn(
        round=round_no, role=role, prompt_version="v", prompt_system="s",
        prompt_user="u", raw_content="{}", parsed=parsed, validation_flags=[],
        valid=True, model="m",
    )


def test_rule_summary_prefers_final_structured_judge_semantics():
    semantic = {
        "principle": "Judge pacing from the cumulative rhythm, not isolated clean frames.",
        "applies_when": "A short edit alternates rapidly between repeated A-roll and B-roll.",
        "evidence_to_check": ["Repeated returns to one static shot create a stuttering rhythm."],
        "scoring_guidance": "Weigh sustained watchability alongside topical B-roll relevance.",
    }
    transcript = DebateTranscript(
        item_id="x", metric_id="M5", turns=[_turn("judge", semantic)], converged=True,
    )
    summary = rule_based_summary(transcript, {"frame_only_blindness": 1}, _TENDENCY)
    assert summary.principle == semantic["principle"]
    assert summary.evidence_to_check[0] == semantic["evidence_to_check"][0]
    assert "Principle:" in render_summary(summary)


def test_legacy_rule_summary_filters_human_targets_but_keeps_editing_evidence():
    transcript = DebateTranscript(
        item_id="x", metric_id="M5", converged=False,
        turns=[
            _turn("human_proxy", reasoning=["Human raters scored it 2/5."], evidence=[]),
            _turn("judge", evidence=[
                "The edit returns to the same static shot after every B-roll insert.",
                "A majority of human annotators rated the video 2/5.",
            ]),
        ],
    )
    summary = rule_based_summary(transcript, {"scale_drift": 2}, _TENDENCY)
    text = render_summary(summary)
    assert "static shot" in text
    assert "annotator" not in text.lower() and "2/5" not in text


@pytest.mark.parametrize("leak", [
    "The human score array is [2, 3, 4].",
    "There were 12 annotators.",
    "Seventy-five percent agreed, recorded as 75%.",
    "Use the median rating.",
    "Use the mode from the rater distribution.",
    "Increase the score by 1.5 points.",
])
def test_validator_rejects_label_leakage(leak):
    summary, error = validate_summary({
        "principle": leak,
        "applies_when": "always", "evidence_to_check": [],
        "scoring_guidance": "copy it", "counter_consideration": "",
    })
    assert summary is None
    assert error == "summary_contains_human_label_or_target_score"


def test_validator_rejects_malformed_evidence_list():
    summary, error = validate_summary({
        "principle": "Evaluate the edit as a complete temporal sequence.",
        "applies_when": "The result contains multiple temporal edits.",
        "evidence_to_check": "not a JSON list",
        "scoring_guidance": "Weigh the observable sequence-level effects.",
    })
    assert summary is None
    assert error == "summary_evidence_not_a_list"


def test_validator_rejects_missing_required_semantic_fields():
    summary, error = validate_summary({
        "principle": "Evaluate the edit as a complete temporal sequence.",
        "evidence_to_check": [],
    })
    assert summary is None
    assert error == "summary_missing_required_fields:applies_when,scoring_guidance"


def test_renderer_is_hard_bounded():
    summary = SemanticSummary(
        principle="principle " * 80,
        applies_when="condition " * 80,
        evidence_to_check=["evidence " * 80],
        scoring_guidance="guidance " * 80,
    )
    assert len(render_summary(summary).split()) <= 250


def test_renderer_preserves_a_rich_summary_within_target_budget():
    summary = SemanticSummary(
        principle=(
            "Judge the edit's cumulative temporal rhythm and instruction fulfillment, "
            "not the polish of isolated frames or the presence of individually relevant inserts."
        ),
        applies_when=(
            "A short edit repeatedly alternates between an unchanged anchor shot and topical "
            "B-roll, or when local transitions appear acceptable but the complete sequence feels repetitive."
        ),
        evidence_to_check=[
            "Track how often the same composition returns and whether those returns advance the requested narrative.",
            "Inspect cut timing, shot duration, transition continuity, and whether visual changes align with spoken ideas.",
            "Separate source-inherited limitations from artifacts introduced by the edit itself.",
        ],
        scoring_guidance=(
            "Weigh successful instruction coverage against sustained pacing or continuity defects, cite the observable "
            "facts that drive the judgment, and avoid letting one clean frame conceal repeated disruption across time."
        ),
        counter_consideration=(
            "Relevant B-roll can still improve clarity, so repetition should matter only when it weakens watchability "
            "or fails to support the requested communication goal."
        ),
    )
    words = len(render_summary(summary).split())
    assert 120 <= words <= 250


class _Engine:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return {"content": json.dumps(self.payload)}


def test_llm_summary_uses_one_call_and_shared_schema():
    engine = _Engine({
        "principle": "Evaluate temporal rhythm across the complete edit.",
        "applies_when": "Cuts repeatedly return to an unchanged anchor shot.",
        "evidence_to_check": ["The same composition recurs after each B-roll insert."],
        "scoring_guidance": "Weigh cumulative disruption, not frame-level polish.",
        "counter_consideration": "",
    })
    summary, error = llm_summary(DebateTranscript(item_id="x", metric_id="M5"), engine)
    assert error is None and summary is not None
    assert engine.calls == 1
