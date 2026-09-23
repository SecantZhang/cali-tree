from vejudge.database.dl_human_annotations.aggregate import AggregatedHumanRecord
from vejudge.postprocessing.align import (
    ALIGNMENT,
    build_aligned_rows,
    derive_overall,
    diagnose_missing_rows,
    judge_signal_for_dimension,
)


def _judge_results():
    return {
        "M3": {"parsed": {"score_1_to_5": 4}},
        "M4": {"parsed": {"score_1_to_5": 3}},
        "M5": {"parsed": {"score_1_to_5": 5}},
        "M6": {
            "parsed": {
                "voiceover_visual_match": {"score_1_to_5": 2},
                "voiceover_continuity": {"score_1_to_5": 3},
                "visual_continuity": {"score_1_to_5": 4},
                "overall_av_sync_score": 3,
            }
        },
    }


def test_alignment_covers_all_human_dims():
    # Every dimension in the crosswalk has a label + extractor.
    assert "video_addresses_prompt" in ALIGNMENT
    assert "voiceover_matches_visuals" in ALIGNMENT


def test_signal_extraction():
    jr = _judge_results()
    assert judge_signal_for_dimension(jr, "video_addresses_prompt") == 4.0
    assert judge_signal_for_dimension(jr, "story_flow_visuals") == 5.0
    assert judge_signal_for_dimension(jr, "voiceover_matches_visuals") == 2.0
    assert judge_signal_for_dimension(jr, "abrupt_cutoffs_video") == 4.0


def test_signal_missing_returns_none():
    assert judge_signal_for_dimension({"M3": {"parsed": None}}, "video_addresses_prompt") is None


def test_derive_overall_mean():
    # mean of M3=4, M4=3, M5=5, M6 overall=3 -> 3.75
    assert derive_overall(_judge_results()) == 3.75


def test_build_aligned_rows():
    item_id = "prj-x::0::peanut"
    agg = AggregatedHumanRecord(
        item_id=item_id,
        project="prj-x",
        prompt_idx=0,
        model="peanut",
        use_case="visual montage",
        scores={"video_addresses_prompt": 4.0, "story_flow_visuals": 5.0},
    )
    rows = build_aligned_rows(
        [item_id], {item_id: agg}, {item_id: _judge_results()}
    )
    by_dim = {r["dimension"]: r for r in rows}
    assert by_dim["video_addresses_prompt"]["human"] == 4.0
    assert by_dim["video_addresses_prompt"]["judge_raw"] == 4.0
    assert by_dim["story_flow_visuals"]["human"] == 5.0
    assert by_dim["story_flow_visuals"]["judge_raw"] == 5.0
    assert by_dim["video_addresses_prompt"]["use_case"] == "visual montage"


def test_build_aligned_rows_skips_missing_scores():
    item_id = "prj-x::0::peanut"
    agg = AggregatedHumanRecord(
        item_id=item_id, project="prj-x", prompt_idx=0, model="peanut",
    )
    rows = build_aligned_rows([item_id], {item_id: agg}, {item_id: _judge_results()})
    assert rows == []


def _full_agg(item_id="prj-x::0::peanut"):
    # A human score for every ALIGNMENT-covered dimension, so only the judge side varies
    # across the diagnostic tests below.
    return AggregatedHumanRecord(
        item_id=item_id, project="prj-x", prompt_idx=0, model="peanut",
        scores={dim: 4.0 for dim in ALIGNMENT},
    )


def test_diagnose_missing_rows_reports_missing_human_score():
    item_id = "prj-x::0::peanut"
    agg = AggregatedHumanRecord(item_id=item_id, project="prj-x", prompt_idx=0, model="peanut")
    diag = diagnose_missing_rows([item_id], {item_id: agg}, {item_id: _judge_results()})
    reasons = {(d["dimension"], d["reason"]) for d in diag}
    assert any("no human score" in r for _, r in reasons)


def test_diagnose_missing_rows_reports_metric_never_produced():
    item_id = "prj-x::0::peanut"
    agg = _full_agg(item_id)
    # No M3 key at all in the judge results -> video_addresses_prompt can't align.
    diag = diagnose_missing_rows([item_id], {item_id: agg}, {item_id: {}})
    entry = next(d for d in diag if d["dimension"] == "video_addresses_prompt")
    assert "never produced" in entry["reason"]
    assert entry["count"] == 1
    assert entry["example_item_ids"] == [item_id]


def test_diagnose_missing_rows_reports_invalid_parsed_output():
    item_id = "prj-x::0::peanut"
    agg = _full_agg(item_id)
    diag = diagnose_missing_rows(
        [item_id], {item_id: agg}, {item_id: {"M3": {"parsed": None, "error": "boom"}}}
    )
    entry = next(d for d in diag if d["dimension"] == "video_addresses_prompt")
    assert "no valid parsed output" in entry["reason"]
    assert "boom" in entry["reason"]


def test_diagnose_missing_rows_reports_non_numeric_score_field():
    item_id = "prj-x::0::peanut"
    agg = _full_agg(item_id)
    diag = diagnose_missing_rows(
        [item_id], {item_id: agg},
        {item_id: {"M3": {"parsed": {"score_1_to_5": "4"}}}},  # string, not numeric
    )
    entry = next(d for d in diag if d["dimension"] == "video_addresses_prompt")
    assert "no numeric score" in entry["reason"]


def test_diagnose_missing_rows_groups_same_reason_across_items_not_per_item():
    ids = ["prj-x::0::peanut", "prj-x::1::peanut", "prj-x::2::peanut"]
    human = {iid: _full_agg(iid) for iid in ids}
    judges = {iid: {} for iid in ids}  # every metric missing for every item
    diag = diagnose_missing_rows(ids, human, judges)
    entry = next(d for d in diag if d["dimension"] == "video_addresses_prompt")
    assert entry["count"] == 3
    assert len(entry["example_item_ids"]) == 3  # capped sample, not the full list


def test_diagnose_missing_rows_returns_empty_when_nothing_is_wrong():
    item_id = "prj-x::0::peanut"
    agg = AggregatedHumanRecord(
        item_id=item_id, project="prj-x", prompt_idx=0, model="peanut",
        scores={"video_addresses_prompt": 4.0},
    )
    diag = diagnose_missing_rows([item_id], {item_id: agg}, {item_id: _judge_results()})
    assert not any(d["dimension"] == "video_addresses_prompt" for d in diag)
