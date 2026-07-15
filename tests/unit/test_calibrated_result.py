"""The calibration prompts feed straight into a downstream Judge's real prompt, so
they must (a) never crash on a partial/invalid verdict and (b) stay concise — a
distilled lesson, not the full transcript dump the old version embedded."""

from vejudge.core.calibration.debate.calibrated_result import (
    _TENDENCY,
    render_corpus_calibration_prompt,
    render_optimized_prompt_addendum,
)
from vejudge.core.prompts.d2_human_proxy_debate import FAILURE_MODE_TAXONOMY
from vejudge.core.calibration.debate.schema import DebateTranscript, DebateTurn, DebateVerdict


def _proxy_turn(reasoning_lines, round_no=1):
    return DebateTurn(
        round=round_no, role="human_proxy", prompt_version="v1", prompt_system="s",
        prompt_user="u", raw_content="{}",
        parsed={"score_1_to_5": 3, "reasoning_lines": reasoning_lines},
        validation_flags=[], valid=True, model="m",
    )


def _verdict(*, proxy_lines=None, **overrides) -> DebateVerdict:
    transcript = DebateTranscript(item_id="prj-x::0::peanut", metric_id="M5")
    if proxy_lines is not None:
        transcript.turns.append(_proxy_turn(proxy_lines))
    defaults = dict(
        item_id="prj-x::0::peanut",
        metric_id="M5",
        initial_score=3.0,
        final_score=3.0,
        score_delta=0.0,
        converged=True,
        rounds_run=1,
        flags=[],
        reasoning_trace="because reasons",
        failure_mode_summary={},
        transcript=transcript,
    )
    defaults.update(overrides)
    return DebateVerdict(**defaults)


# --- taxonomy sync -----------------------------------------------------------

def test_calibration_tendency_phrases_cover_the_taxonomy():
    # The concise tendency phrases must stay pinned to the same key set as the
    # human-proxy failure-mode taxonomy — a new taxonomy key with no tendency phrase
    # would silently drop out of every calibration prompt.
    assert set(_TENDENCY) == set(FAILURE_MODE_TAXONOMY)


# --- per-item: de-leaked (general tendencies only, no score / no narrative) ---

def test_no_failure_modes_yields_empty_prompt():
    # Nothing generalizable to inject -> "" (the judge re-scores uncalibrated), rather
    # than a score-bearing header that would leak the grounded target.
    verdict = _verdict(failure_mode_summary={})
    assert render_optimized_prompt_addendum(verdict) == ""


def test_prompt_carries_only_general_tendencies():
    verdict = _verdict(
        initial_score=2.0, final_score=4.0, score_delta=2.0,
        failure_mode_summary={"scale_drift": 3, "overconfident_rationale": 5, "audio_neglect": 1},
    )
    text = render_optimized_prompt_addendum(verdict)
    # Top-2 by count appear; the third (audio_neglect, count 1) does not.
    assert _TENDENCY["overconfident_rationale"] in text
    assert _TENDENCY["scale_drift"] in text
    assert _TENDENCY["audio_neglect"] not in text
    assert "tendency to" in text and "Weigh these when scoring" in text


def test_prompt_does_not_leak_the_score_or_item_narrative():
    # The whole point of the de-leak: no revised/initial/final score, no "→", no
    # item-specific "Key point", and never the full reasoning trace.
    verdict = _verdict(
        proxy_lines=["The score oscillated between 1, 3 and 4 for this exact video."],
        initial_score=1.0, final_score=3.0, score_delta=2.0,
        reasoning_trace="SENTINEL_FULL_TRANSCRIPT_TEXT " * 50,
        failure_mode_summary={"scale_drift": 3, "overconfident_rationale": 2},
    )
    text = render_optimized_prompt_addendum(verdict)
    assert "→" not in text
    assert "1" not in text and "3" not in text and "4" not in text  # no score digits
    assert "Key point" not in text
    assert "adjusted the score" not in text and "confirmed the score" not in text
    assert "SENTINEL_FULL_TRANSCRIPT_TEXT" not in text
    assert "oscillated" not in text  # the item-specific critique narrative is gone


def test_prompt_is_short_and_bounded_regardless_of_rounds():
    transcript = DebateTranscript(item_id="prj-x::0::peanut", metric_id="M5")
    for r in range(1, 11):
        transcript.turns.append(_proxy_turn(["a concrete critique sentence here"], round_no=r))
    verdict = _verdict(
        proxy_lines=None, transcript=transcript, rounds_run=10, converged=False,
        initial_score=1.0, final_score=4.0, score_delta=3.0,
        failure_mode_summary={"scale_drift": 9, "overconfident_rationale": 6},
    )
    text = render_optimized_prompt_addendum(verdict)
    assert len(text.split()) <= 30  # just the two tendencies + framing
    assert "→" not in text


# --- corpus-level generalization ---------------------------------------------

def test_corpus_prompt_aggregates_recurring_modes_and_direction():
    results = [
        {"failure_mode_summary": {"overconfident_rationale": 2, "scale_drift": 1}, "score_delta": 1.0},
        {"failure_mode_summary": {"overconfident_rationale": 3, "category_imbalance": 2}, "score_delta": 2.0},
        {"failure_mode_summary": {"category_imbalance": 1}, "score_delta": 0.0},
    ]
    text = render_corpus_calibration_prompt(results)
    # Top-3 recurring modes named; item-independent (no item ids / no per-item narrative).
    assert _TENDENCY["overconfident_rationale"] in text
    assert _TENDENCY["category_imbalance"] in text
    assert "3 adversarially-reviewed items" in text
    # Positive mean delta => judge under-scored.
    assert "under-score" in text
    assert "prj-" not in text  # nothing item-specific leaked in


def test_corpus_prompt_reports_over_scoring_direction():
    results = [{"failure_mode_summary": {"scale_drift": 1}, "score_delta": -1.5}]
    assert "over-score" in render_corpus_calibration_prompt(results)


def test_corpus_prompt_states_correction_magnitude_not_just_direction():
    # Directional-only correction overshot in leave-one-out CV; the prompt now states
    # the average correction size so the re-judge has a target, not just a sign.
    results = [
        {"failure_mode_summary": {"scale_drift": 1}, "score_delta": 2.0},
        {"failure_mode_summary": {"scale_drift": 1}, "score_delta": 2.0},
    ]
    text = render_corpus_calibration_prompt(results)
    assert "roughly 2.0 point" in text


def test_corpus_prompt_empty_when_nothing_to_generalize():
    assert render_corpus_calibration_prompt([]) == ""
    # No flagged modes and no directional bias => nothing generalizable.
    assert render_corpus_calibration_prompt([{"failure_mode_summary": {}, "score_delta": 0.0}]) == ""


def test_corpus_prompt_singular_grammar_for_one_item():
    results = [{"failure_mode_summary": {"scale_drift": 1}, "score_delta": 1.0}]
    text = render_corpus_calibration_prompt(results)
    assert "1 adversarially-reviewed item:" in text
    assert "1 adversarially-reviewed items" not in text
