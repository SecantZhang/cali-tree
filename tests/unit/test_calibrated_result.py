"""render_optimized_prompt_addendum must never crash on a partial/invalid verdict —
it feeds straight into a downstream Judge Node's real prompt."""

from vejudge.core.calibration.debate.calibrated_result import render_optimized_prompt_addendum
from vejudge.core.calibration.debate.schema import DebateTranscript, DebateVerdict


def _verdict(**overrides) -> DebateVerdict:
    defaults = dict(
        item_id="prj-x::0::peanut",
        metric_id="M1",
        initial_score=3.0,
        final_score=3.0,
        score_delta=0.0,
        converged=True,
        rounds_run=1,
        flags=[],
        reasoning_trace="because reasons",
        failure_mode_summary={},
        transcript=DebateTranscript(item_id="prj-x::0::peanut", metric_id="M1"),
    )
    defaults.update(overrides)
    return DebateVerdict(**defaults)


def test_final_score_none_falls_back_without_crashing():
    verdict = _verdict(final_score=None, score_delta=None, converged=False, flags=["all_turns_failed"])
    text = render_optimized_prompt_addendum(verdict)
    assert "could not reach a valid revised score" in text
    assert "all_turns_failed" in text


def test_initial_score_none_with_a_real_final_score_falls_back_without_crashing():
    # A malformed anchor (parsed dict present but missing the score key) can leave
    # initial_score None while final_score still ends up set — the "revised the score
    # from X to Y" branch used to format initial_score unconditionally and crash with
    # TypeError: unsupported format string passed to NoneType.__format__.
    verdict = _verdict(initial_score=None, final_score=3.0, score_delta=None, converged=False)
    text = render_optimized_prompt_addendum(verdict)
    assert "could not reach a valid revised score" in text


def test_normal_revision_renders_both_scores():
    verdict = _verdict(initial_score=3.0, final_score=4.0, score_delta=1.0, converged=True)
    text = render_optimized_prompt_addendum(verdict)
    assert "revised the score from 3 to 4" in text


def test_converged_with_no_change_renders_single_score():
    verdict = _verdict(initial_score=3.0, final_score=3.0, score_delta=0.0, converged=True)
    text = render_optimized_prompt_addendum(verdict)
    assert "confirmed the original score of 3 held up" in text
