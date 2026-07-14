"""The calibration prompts feed straight into a downstream Judge's real prompt, so
they must (a) never crash on a partial/invalid verdict and (b) stay concise — a
distilled lesson, not the full transcript dump the old version embedded."""

from vejudge.core.calibration.debate.calibrated_result import (
    _GUIDANCE_MAX_WORDS,
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


# --- per-item: never crashes, correct wording per branch ---------------------

def test_final_score_none_falls_back_without_crashing():
    verdict = _verdict(final_score=None, score_delta=None, converged=False, flags=["all_turns_failed"])
    text = render_optimized_prompt_addendum(verdict)
    assert "could not settle on a revised score" in text


def test_initial_score_none_with_a_real_final_score_falls_back_without_crashing():
    # A malformed anchor can leave initial_score None while final_score is set — the
    # revision branch formats both, so both are guarded together.
    verdict = _verdict(initial_score=None, final_score=3.0, score_delta=None, converged=False)
    text = render_optimized_prompt_addendum(verdict)
    assert "could not settle on a revised score" in text


def test_revision_renders_both_scores_concisely():
    verdict = _verdict(initial_score=3.0, final_score=4.0, score_delta=1.0, converged=True)
    text = render_optimized_prompt_addendum(verdict)
    assert "adjusted the score 3→4" in text


def test_confirmed_renders_single_score():
    verdict = _verdict(initial_score=3.0, final_score=3.0, score_delta=0.0, converged=True)
    text = render_optimized_prompt_addendum(verdict)
    assert "confirmed the score of 3" in text


# --- per-item: distillation (the point of the redesign) ----------------------

def test_flagged_failure_modes_become_a_tendency_clause():
    verdict = _verdict(
        initial_score=2.0, final_score=4.0, score_delta=2.0,
        failure_mode_summary={"scale_drift": 3, "overconfident_rationale": 5, "audio_neglect": 1},
    )
    text = render_optimized_prompt_addendum(verdict)
    # Top-2 by count appear as tendency phrases; the third (audio_neglect, count 1) does not.
    assert _TENDENCY["overconfident_rationale"] in text
    assert _TENDENCY["scale_drift"] in text
    assert _TENDENCY["audio_neglect"] not in text
    assert "tendency to" in text


def test_no_failure_modes_means_no_tendency_clause():
    verdict = _verdict(failure_mode_summary={})
    assert "tendency to" not in render_optimized_prompt_addendum(verdict)


def test_optimized_prompt_does_not_embed_the_full_reasoning_trace():
    # The old version appended verdict.reasoning_trace verbatim; the distilled form must
    # not — that's what made it balloon to hundreds/thousands of words.
    verdict = _verdict(reasoning_trace="SENTINEL_FULL_TRANSCRIPT_TEXT " * 50)
    assert "SENTINEL_FULL_TRANSCRIPT_TEXT" not in render_optimized_prompt_addendum(verdict)


def test_guidance_clause_is_capped_regardless_of_critique_length():
    long_line = " ".join(f"word{i}" for i in range(200))
    verdict = _verdict(proxy_lines=[long_line])
    text = render_optimized_prompt_addendum(verdict)
    assert "Key point:" in text
    # Whole addendum stays bounded even when the underlying critique is enormous.
    assert len(text.split()) < 40
    assert text.rstrip().endswith("…")


def test_per_item_prompt_is_bounded_even_with_many_rounds():
    # Many rounds => many failure-mode citations + a long trace, but the distilled
    # prompt is capped by construction (top-2 tendencies + one capped clause).
    transcript = DebateTranscript(item_id="prj-x::0::peanut", metric_id="M5")
    for r in range(1, 11):
        transcript.turns.append(_proxy_turn(["a concrete critique sentence here"], round_no=r))
    verdict = _verdict(
        proxy_lines=None, transcript=transcript, rounds_run=10, converged=False,
        initial_score=1.0, final_score=4.0, score_delta=3.0,
        failure_mode_summary={"scale_drift": 9, "overconfident_rationale": 6},
    )
    assert len(render_optimized_prompt_addendum(verdict).split()) <= 60


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
