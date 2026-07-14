from vejudge.core.judge.validate import validate_judge_output
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
        "score_1_to_5", "agrees_with_judge", "reasoning_lines", "cited_failure_modes",
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


def test_d2_build_omits_real_score_block_by_default():
    spec = d2_human_proxy_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1, retrieved_note=None,
    )
    assert "ground truth" not in spec.user


def test_d2_build_includes_real_score_block_when_grounded():
    spec = d2_human_proxy_debate.build(
        sample=_sample(), metric_id="M4", original_output=_original_output(),
        transcript_text="", round_no=1, retrieved_note=None, real_human_score=4.5,
    )
    assert "4.5" in spec.user
    assert "ground truth" in spec.user
    # Distinct from and never conflated with the different-item retrieved_note block.
    assert "supporting evidence, not a hard override" not in spec.user


def test_d2_schema_is_compatible_with_the_shared_judge_output_validator():
    # Regression test: an earlier draft named this field "critique_lines", which the
    # shared vejudge.core.judge.validate.validate_judge_output rationale check doesn't
    # recognize (it only special-cases "reasoning_lines", matching every M1-M6 judge) --
    # every well-formed human-proxy response was silently flagged "empty_rationale".
    # This asserts a schema-conformant response actually validates as OK.
    well_formed_response = {
        "score_1_to_5": 2,
        "agrees_with_judge": False,
        "reasoning_lines": ["concrete critique here", "another sentence"],
        "cited_failure_modes": ["audio_neglect"],
    }
    result = validate_judge_output(
        well_formed_response, required_fields=list(d2_human_proxy_debate.SCHEMA.keys())
    )
    assert result.ok is True
    assert result.flags == []
