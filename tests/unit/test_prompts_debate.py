from vejudge.core.prompts import d1_judge_debate, d2_human_proxy_debate


def _sample():
    return {"input": {"user_prompt": "do a thing"}, "project": "prj-x", "prompt_idx": 0, "model": "peanut"}


def _original_output():
    return {"parsed": {"score_1_to_5": 4, "reasoning_lines": ["looked complete"]}}


def test_d1_build_includes_original_score_and_transcript():
    spec = d1_judge_debate.build(
        sample=_sample(),
        metric_id="M4",
        original_output=_original_output(),
        transcript_text="Round 1 -- Human-proxy critique (score=2):\n  - missing b-roll",
        round_no=2,
    )
    assert spec.version == d1_judge_debate.VERSION
    assert "do a thing" in spec.user
    assert "missing b-roll" in spec.user
    assert "'score_1_to_5': 4" in spec.user or "score_1_to_5" in spec.user
    assert set(spec.schema.keys()) == {"score_1_to_5", "revised", "reasoning_lines", "evidence"}


def test_d1_build_handles_empty_transcript_on_round_one():
    spec = d1_judge_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1,
    )
    assert "no prior debate turns yet" in spec.user


def test_d2_build_includes_failure_mode_taxonomy_always():
    spec = d2_human_proxy_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1, retrieved_note=None,
    )
    for key in d2_human_proxy_debate.FAILURE_MODE_TAXONOMY:
        assert key in spec.system
    assert set(spec.schema.keys()) == {
        "score_1_to_5", "agrees_with_judge", "critique_lines", "cited_failure_modes",
    }


def test_d2_build_states_no_grounding_when_note_is_none():
    spec = d2_human_proxy_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1, retrieved_note=None,
    )
    assert "No similar historical human annotation was found" in spec.user


def test_d2_build_includes_retrieved_note_text_when_present():
    spec = d2_human_proxy_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1, retrieved_note="voiceover cut off abruptly",
    )
    assert "voiceover cut off abruptly" in spec.user
    assert "supporting evidence, not a hard override" in spec.user
