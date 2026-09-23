import json

import pytest

from vejudge.experiments.structured_decision_test import (
    compare_behavior, compile_alternate_prose_prompt, compile_controlled_prose_prompt, compile_mechanical_json_prompt,
    compile_structured_prompt, parse_decision_spec,
    select_candidate_rounds, summarize,
)


SPEC = {
    "objective": "judge semantic satisfaction",
    "evidence_rules": ["use visible evidence"],
    "decision_steps": [{"order": 1, "decision": "check instruction", "outcomes": "route"}],
    "label_boundaries": {"no": ["absent"], "partial": ["incomplete"], "yes": ["complete"]},
    "tie_breaks": ["absence is no"],
    "output_contract": {"format": "json", "labels": ["no", "partial", "yes"]},
}


def test_parse_and_compile_structured_decisions():
    parsed = parse_decision_spec("```json\n" + json.dumps(SPEC) + "\n```")
    prompt = compile_structured_prompt(parsed)
    assert "<semantic_decision_policy>" in prompt
    assert '"partial"' in prompt
    assert "check instruction" in prompt
    prose = compile_controlled_prose_prompt(parsed)
    assert "Ordered decisions:" in prose and "1. check instruction" in prose
    mechanical = compile_mechanical_json_prompt("first\n\nfirst")
    assert '"order": 2' in mechanical
    assert mechanical.count('"text": "first"') == 2
    alternate = compile_alternate_prose_prompt(parsed)
    assert "Assign labels using these boundaries:" in alternate
    assert "Resolve close calls in this order:" in alternate


def test_selects_all_screen_correct_rounds_and_tags_primary():
    trace = {"item_id": "item", "method": "gepa", "target_label": "partial", "rounds": [
        {"round": 1, "accepted": False, "screen": {"valid": True, "label": "partial"},
         "candidate_prompt": "one", "repeats": [], "robustness": {}},
        {"round": 2, "accepted": True, "screen": {"valid": True, "label": "partial"},
         "candidate_prompt": "two", "repeats": [], "robustness": {}},
        {"round": 3, "accepted": False, "screen": {"valid": True, "label": "no"}},
    ]}
    rows = select_candidate_rounds([trace])
    assert [row["cohort"] for row in rows] == ["screen_correct_secondary", "accepted_primary"]


def test_behavior_comparison_reports_preservation_and_shift():
    candidate = {"target_label": "partial", "original_screen": {"label": "partial"},
                 "original_robustness": {"target_hits": 7, "n": 10,
                 "label_distribution": {"no": 3, "partial": 7, "yes": 0, "invalid": 0}}}
    repeats = [{"valid": True, "label": "partial"}] * 8 + [{"valid": True, "label": "no"}] * 2
    result = compare_behavior(candidate, {"valid": True, "label": "partial"}, repeats, 6)
    assert result["screen_label_preserved"] is True
    assert result["robustness_preserved"] is True
    assert result["target_hit_delta"] == 1
    assert result["total_variation_distance"] == pytest.approx(0.1)
    summary = summarize([{"cohort": "accepted_primary", "extraction": {"valid": True}, "comparison": result}])
    assert summary["accepted_primary"]["robustness_preserved"] == 1
