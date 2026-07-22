from vejudge.core.calibration.debate.eval.rubric_bank import (
    combine_with_debate_bank,
    rubric_questions,
)


def test_m5_rubric_bank_covers_structure_and_flow_without_targets():
    bank = rubric_questions("M5")
    assert len(bank) == 8
    assert {entry["semantic_key"] for entry in bank} >= {
        "rubric:story_flow_voiceover",
        "rubric:story_flow_visuals",
        "rubric:section_placement_opening",
        "rubric:section_placement_middle",
        "rubric:section_placement_closing",
    }
    rendered = " ".join(entry["question"] for entry in bank).lower()
    assert "human" not in rendered and "target score" not in rendered


def test_debate_rules_fill_capacity_after_rubric_anchors():
    debate = [
        {"question": f"Debate rule {index}?", "raises_score_when": "yes"}
        for index in range(10)
    ]
    bank = combine_with_debate_bank(metric_id="M5", debate_bank=debate, max_questions=12)
    assert len(bank) == 12
    assert sum(entry["scope"] == "item_quality" for entry in bank) == 8
    assert sum(entry["scope"] == "judge_reasoning" for entry in bank) == 4
