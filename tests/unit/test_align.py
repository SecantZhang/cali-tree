from vejudge.postprocessing.align import (
    ALIGNMENT,
    derive_overall,
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
