from vejudge.core.calibration.debate.retrieval import RetrievedNote
from vejudge.core.calibration.debate.schema import (
    DebateTranscript,
    DebateTurn,
    DebateVerdict,
    extract_original_score,
    normalize_failure_modes,
    render_reasoning_trace,
)


def _turn(round_no, role, parsed, **kwargs):
    return DebateTurn(
        round=round_no,
        role=role,
        prompt_version="v1",
        prompt_system="sys",
        prompt_user="user",
        raw_content="{}",
        parsed=parsed,
        validation_flags=kwargs.pop("validation_flags", []),
        valid=kwargs.pop("valid", True),
        model="m",
        **kwargs,
    )


def test_as_text_empty_transcript_is_empty_string():
    t = DebateTranscript(item_id="prj::0::peanut", metric_id="M4")
    assert t.as_text() == ""


def test_as_text_includes_role_round_score_and_lines_in_order():
    t = DebateTranscript(item_id="prj::0::peanut", metric_id="M4")
    t.turns.append(
        _turn(1, "human_proxy", {"score_1_to_5": 2, "reasoning_lines": ["misses the ask"]})
    )
    t.turns.append(
        _turn(1, "judge", {"score_1_to_5": 4, "reasoning_lines": ["still aligned"]})
    )
    text = t.as_text()
    assert "Round 1 -- Human-proxy critique (score=2)" in text
    assert "misses the ask" in text
    assert "Round 1 -- Judge response (score=4)" in text
    assert "still aligned" in text
    assert text.index("Human-proxy critique") < text.index("Judge response")


def test_last_returns_most_recent_turn_for_role():
    t = DebateTranscript(item_id="x", metric_id="M4")
    t.turns.append(_turn(1, "judge", {"score_1_to_5": 3}))
    t.turns.append(_turn(2, "judge", {"score_1_to_5": 4}))
    assert t.last("judge").round == 2
    assert t.last("human_proxy") is None


def test_extract_original_score_uses_metric_specific_key():
    assert extract_original_score({"parsed": {"score_1_to_5": 4}}, "M4") == 4.0
    assert extract_original_score({"parsed": {"overall_av_sync_score": 3}}, "M6") == 3.0
    assert extract_original_score({"parsed": {}}, "M4") is None
    assert extract_original_score({}, "M4") is None


def test_normalize_failure_modes_splits_known_and_unknown():
    known, unknown = normalize_failure_modes(["Self-Bias", "audio_neglect", "made_up_thing"])
    assert known == ["self_bias", "audio_neglect"]
    assert unknown == ["made_up_thing"]


def test_normalize_failure_modes_handles_none():
    known, unknown = normalize_failure_modes(None)
    assert known == [] and unknown == []


def test_render_reasoning_trace_converged():
    t = DebateTranscript(item_id="x", metric_id="M4", converged=True, rounds_run=2)
    t.turns.append(
        _turn(1, "human_proxy", {"score_1_to_5": 2, "reasoning_lines": ["gap here"]})
    )
    t.turns.append(_turn(1, "judge", {"score_1_to_5": 4, "reasoning_lines": ["holds up"]}))
    trace = render_reasoning_trace(t, {"parsed": {"reasoning_lines": ["orig rationale"]}})
    assert "orig rationale" in trace
    assert "gap here" in trace
    assert "holds up" in trace
    assert "Converged after 2 round(s)." in trace


def test_render_reasoning_trace_not_converged():
    t = DebateTranscript(
        item_id="x", metric_id="M4", converged=False, rounds_run=4,
        convergence_reason="max_rounds",
    )
    trace = render_reasoning_trace(t, {})
    assert "Did not converge after 4 round(s) (reason: max_rounds)." in trace


def test_debate_verdict_to_dict_from_dict_round_trip():
    note = RetrievedNote(text="note text", source_path="p", item_id="other::1::x", matched_terms=["audio"])
    transcript = DebateTranscript(item_id="prj::0::peanut", metric_id="M6", converged=True, rounds_run=1)
    transcript.turns.append(
        _turn(1, "human_proxy", {"score_1_to_5": 2}, retrieval_used=True, retrieved_note=note)
    )
    transcript.turns.append(_turn(1, "judge", {"score_1_to_5": 4}))
    verdict = DebateVerdict(
        item_id="prj::0::peanut",
        metric_id="M6",
        initial_score=3.0,
        final_score=4.0,
        score_delta=1.0,
        converged=True,
        rounds_run=1,
        flags=["epsilon"],
        reasoning_trace="trace text",
        failure_mode_summary={"self_bias": 1},
        transcript=transcript,
    )

    data = verdict.to_dict()
    restored = DebateVerdict.from_dict(data)

    assert restored.item_id == verdict.item_id
    assert restored.final_score == verdict.final_score
    assert restored.failure_mode_summary == {"self_bias": 1}
    assert restored.transcript.turns[0].retrieved_note == note
    assert restored.transcript.turns[0].retrieval_used is True
    assert len(restored.transcript.turns) == 2
    # Not passed above -> defaults False on both the fresh object and the round-trip.
    assert verdict.grounded is False
    assert restored.grounded is False


def test_grounded_field_round_trips_and_defaults_false_on_old_data():
    transcript = DebateTranscript(
        item_id="x", metric_id="M6", converged=True, rounds_run=1, grounded=True,
    )
    verdict = DebateVerdict(
        item_id="x", metric_id="M6", initial_score=3.0, final_score=3.05,
        score_delta=0.05, converged=True, rounds_run=1, flags=["epsilon_human"],
        reasoning_trace="t", failure_mode_summary={}, transcript=transcript, grounded=True,
    )

    restored = DebateVerdict.from_dict(verdict.to_dict())
    assert restored.grounded is True
    assert restored.transcript.grounded is True

    # Old checkpoint data predating this field entirely (no "grounded" key at all).
    legacy_data = verdict.to_dict()
    del legacy_data["grounded"]
    del legacy_data["transcript"]["grounded"]
    legacy_restored = DebateVerdict.from_dict(legacy_data)
    assert legacy_restored.grounded is False
    assert legacy_restored.transcript.grounded is False
