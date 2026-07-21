import json

import pytest

from vejudge.core.calibration.debate.runner import DebateConfig, DebateRunner


class _ScriptedEngine:
    """Duck-typed LMEngine test double: returns canned ``generate()`` outputs in order.

    Simpler and more deterministic for a two-role debate than monkeypatching the
    shared ``openai_compat.chat_completion`` transport for two engines at once.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        self.calls += 1
        if not self._responses:
            raise RuntimeError("scripted engine ran out of responses")
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _content(payload):
    return json.dumps(payload)


def _out(payload, model="m"):
    return {"content": _content(payload), "model": model, "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def _sample():
    return {"item_id": "prj-x::0::peanut", "project": "prj-x", "prompt_idx": 0, "model": "peanut",
            "input": {"user_prompt": "do a thing"}}


def _original_output(score=3):
    return {"parsed": {"score_1_to_5": score, "reasoning_lines": ["seems fine"]}, "valid": True}


def _runner(judge_responses, proxy_responses, **config_kwargs):
    judge_engine = _ScriptedEngine(judge_responses)
    proxy_engine = _ScriptedEngine(proxy_responses)
    config = DebateConfig(retrieval_enabled=False, **config_kwargs)
    return DebateRunner(
        metric_id="M4", judge_engine=judge_engine, proxy_engine=proxy_engine, config=config,
    )


def test_converges_within_epsilon_on_round_one():
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.1, "revised": True, "reasoning_lines": ["ok"], "evidence": ["e"]})],
        proxy_responses=[_out({"score_1_to_5": 2, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})],
        epsilon=0.25, max_rounds=4,
    )
    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.converged is True
    assert verdict.rounds_run == 1
    assert verdict.final_score == 3.1
    assert verdict.initial_score == 3.0
    assert "epsilon" in verdict.flags
    assert len(verdict.transcript.turns) == 2
    assert verdict.transcript.turns[0].role == "human_proxy"
    assert verdict.transcript.turns[1].role == "judge"
    # A well-formed human-proxy turn must validate successfully against the shared
    # validate_judge_output rationale check -- regression test for a bug caught by
    # manual testing where "critique_lines" (not "reasoning_lines") silently failed
    # the shared validator's rationale check on every single human-proxy turn.
    assert verdict.transcript.turns[0].valid is True
    assert verdict.transcript.turns[0].validation_flags == []


def test_hits_max_rounds_without_converging():
    # Each round the judge moves the score by 0.5 -- always above epsilon=0.25.
    judge_scores = [3.5, 4.0, 4.5, 5.0]
    judge_responses = [
        _out({"score_1_to_5": s, "revised": True, "reasoning_lines": ["ok"], "evidence": []})
        for s in judge_scores
    ]
    proxy_responses = [
        _out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})
        for _ in judge_scores
    ]
    runner = _runner(judge_responses, proxy_responses, epsilon=0.25, max_rounds=4)

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.converged is False
    assert verdict.rounds_run == 4
    assert verdict.final_score == 5.0
    assert "max_rounds" in verdict.flags
    assert len(verdict.transcript.turns) == 8


def test_invalid_judge_turn_stops_without_faking_convergence():
    runner = _runner(
        judge_responses=[
            _out({"score_1_to_5": 3.5, "revised": True, "reasoning_lines": ["ok"], "evidence": []}),
            {"content": "not json at all", "model": "m", "promptTokens": 1,
             "completionTokens": 1, "totalTokens": 2},  # round 2: genuinely unparseable
        ],
        proxy_responses=[
            _out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []}),
            _out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap again"], "cited_failure_modes": []}),
        ],
        epsilon=0.05, max_rounds=4,  # tiny epsilon so round 1 does NOT converge
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.converged is False
    assert verdict.rounds_run == 2
    assert "invalid_turn" in verdict.flags
    # Falls back to round 1's valid judge score, not None and not a fabricated delta.
    assert verdict.final_score == 3.5


def test_all_turns_failing_never_raises_and_flags_total_failure():
    runner = _runner(
        judge_responses=[RuntimeError("gateway down")],
        proxy_responses=[RuntimeError("gateway down")],
        epsilon=0.25, max_rounds=4,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.final_score is None
    assert verdict.converged is False
    assert verdict.flags == ["all_turns_failed"]
    assert all(t.error for t in verdict.transcript.turns)


def test_grounded_mode_requires_closing_the_human_gap_not_just_self_stability():
    # The judge is self-consistent from round 1 (always 3.5) -- in blind mode this
    # would converge immediately via "epsilon". But it's 1.5 points off the real human
    # anchor (5.0), well above epsilon (0.25) -- grounded mode must NOT treat
    # self-stability as convergence; it should keep running (and hit max_rounds without
    # ever converging), exactly the reported failure mode this feature targets.
    judge_responses = [
        _out({"score_1_to_5": 3.5, "revised": True, "reasoning_lines": ["ok"], "evidence": []})
        for _ in range(4)
    ]
    proxy_responses = [
        _out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})
        for _ in range(4)
    ]
    runner = _runner(
        judge_responses, proxy_responses,
        epsilon=0.25, max_rounds=4, ground_in_human_labels=True, human_anchor_score=5.0,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.grounded is True
    assert verdict.converged is False
    assert verdict.rounds_run == 4
    assert "max_rounds" in verdict.flags
    assert "epsilon" not in verdict.flags


def test_grounded_mode_converges_when_judge_closes_on_the_human_anchor():
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.05, "revised": True, "reasoning_lines": ["ok"], "evidence": []})],
        proxy_responses=[_out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})],
        epsilon=0.25, max_rounds=4, ground_in_human_labels=True, human_anchor_score=3.1,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.grounded is True
    assert verdict.converged is True
    assert verdict.rounds_run == 1
    assert "epsilon_human" in verdict.flags


def test_grounded_mode_falls_back_to_blind_when_no_human_anchor():
    # ground_in_human_labels=True but no anchor score for this item (human_anchor_score
    # left at its default None) -- automatic per-item fallback, no special-cased branch:
    # behaves exactly like today's blind debate.
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.1, "revised": True, "reasoning_lines": ["ok"], "evidence": ["e"]})],
        proxy_responses=[_out({"score_1_to_5": 2, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})],
        epsilon=0.25, max_rounds=4, ground_in_human_labels=True,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.grounded is False
    assert verdict.converged is True
    assert "epsilon" in verdict.flags
    assert "epsilon_human" not in verdict.flags


def test_grounded_mode_real_score_reaches_only_the_human_proxy_prompt():
    # The human-proxy's own prompt cites the real score explicitly when grounded; the
    # judge's turn never receives it directly (structural -- d1_judge_debate.build has
    # no such parameter at all) and must keep reacting only to the proxy's argued text.
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.05, "revised": True, "reasoning_lines": ["ok"], "evidence": []})],
        proxy_responses=[_out({"score_1_to_5": 1, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []})],
        epsilon=0.25, max_rounds=4, ground_in_human_labels=True, human_anchor_score=3.1,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    proxy_turn, judge_turn = verdict.transcript.turns
    assert proxy_turn.role == "human_proxy"
    assert "3.1" in proxy_turn.prompt_user
    assert "ground truth" in proxy_turn.prompt_user
    assert judge_turn.role == "judge"
    assert "3.1" not in judge_turn.prompt_user


def test_raw_grounded_mode_preserves_ratings_and_uses_stability_convergence():
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.0, "revised": False,
                               "reasoning_lines": ["stable"], "evidence": []})],
        proxy_responses=[_out({"score_1_to_5": 2, "agrees_with_judge": False,
                               "reasoning_lines": ["raters disagree"],
                               "cited_failure_modes": []})],
        epsilon=0.25, max_rounds=4, ground_in_human_labels=True,
        human_raw_scores=[2.0, 4.0],
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.grounded is True
    assert verdict.converged is True
    assert "epsilon_raw_grounded" in verdict.flags
    assert '"histogram": {"2": 1, "4": 1}' in verdict.transcript.turns[0].prompt_user
    assert verdict.human_disagreement_profile["polarized"] is True
    assert "Never select one annotator" in verdict.transcript.turns[0].prompt_user


def test_failure_mode_tags_are_normalized_and_counted():
    runner = _runner(
        judge_responses=[_out({"score_1_to_5": 3.1, "revised": True, "reasoning_lines": ["ok"], "evidence": []})],
        proxy_responses=[_out({
            "score_1_to_5": 2, "agrees_with_judge": False,
            "reasoning_lines": ["ignores the audio"],
            "cited_failure_modes": ["Audio-Neglect", "made_up_mode"],
        })],
        epsilon=0.25, max_rounds=4,
    )

    verdict = runner.run(_sample(), _original_output(score=3.0))

    assert verdict.failure_mode_summary == {"audio_neglect": 1}
    proxy_turn = verdict.transcript.turns[0]
    assert proxy_turn.failure_modes == ["audio_neglect"]
    assert "unknown_failure_mode:made_up_mode" in proxy_turn.validation_flags


def test_alternating_scores_stop_as_oscillation_and_keep_original_score():
    judge = [
        _out({
            "score_1_to_5": score, "revised": True,
            "reasoning_lines": [f"view {score}"], "evidence": ["e"],
            "semantic_summary": {
                "principle": f"principle {score}", "applies_when": "condition",
                "evidence_to_check": [f"evidence {score}"], "scoring_guidance": "weigh it",
            },
        })
        for score in (3, 5, 3, 5)
    ]
    proxy = [_out({
        "score_1_to_5": 2, "agrees_with_judge": False,
        "reasoning_lines": ["stable disagreement"], "cited_failure_modes": [],
    }) for _ in range(4)]
    verdict = _runner(
        judge, proxy, epsilon=0.25, max_rounds=6,
        ground_in_human_labels=True, human_raw_scores=[2.0, 5.0],
    ).run(_sample(), _original_output(score=2.0))
    assert verdict.converged is False
    assert verdict.rounds_run == 4
    assert verdict.final_score == 2.0
    assert verdict.score_delta == 0.0
    assert "oscillation_detected" in verdict.flags


def test_repeated_semantics_stop_after_two_stale_rounds():
    semantic = {
        "principle": "Use observable evidence.", "applies_when": "The edit is ambiguous.",
        "evidence_to_check": ["Check the same fact."], "scoring_guidance": "Weigh it consistently.",
    }
    judge = [_out({
        "score_1_to_5": score, "revised": True, "reasoning_lines": ["same finding"],
        "evidence": ["e"], "semantic_summary": semantic,
    }) for score in (2, 3, 4)]
    proxy = [_out({
        "score_1_to_5": 1, "agrees_with_judge": False,
        "reasoning_lines": ["same critique"], "cited_failure_modes": [],
    }) for _ in range(3)]
    verdict = _runner(judge, proxy, epsilon=0.1, max_rounds=6).run(
        _sample(), _original_output(score=1.0),
    )
    assert verdict.converged is True
    assert verdict.rounds_run == 3
    assert "semantic_stable" in verdict.flags


def test_debate_config_hard_caps_rounds_at_six():
    assert DebateConfig(max_rounds=20).max_rounds == 6
