import json

import pytest

from vejudge.core.calibration.debate import runner as debate_runner_module
from vejudge.core.calibration.debate.registry import debate_prompt_versions, make_debate
from vejudge.core.calibration.debate.retrieval import RetrievedNote
from vejudge.core.calibration.debate.runner import DebateConfig


class _ScriptedEngine:
    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, prompt, media_inputs=None, schema=None, *, system=None, model=None):
        resp = self._responses.pop(0)
        self.last_prompt = prompt
        self.last_system = system
        return resp


def _out(payload):
    return {"content": json.dumps(payload), "model": "m", "promptTokens": 1, "completionTokens": 1, "totalTokens": 2}


def _sample():
    return {"item_id": "prj-x::0::peanut", "project": "prj-x", "prompt_idx": 0, "model": "peanut",
            "input": {"user_prompt": "add a title card"}}


def _original_output():
    return {"parsed": {"score_1_to_5": 3, "reasoning_lines": ["mostly matches"]}}


def test_full_two_round_debate_converges_and_produces_verdict():
    judge_engine = _ScriptedEngine([
        _out({"score_1_to_5": 3.6, "revised": True, "reasoning_lines": ["addressed one gap"], "evidence": ["title visible"]}),
        _out({"score_1_to_5": 3.7, "revised": True, "reasoning_lines": ["minor further tweak"], "evidence": ["timing ok"]}),
    ])
    proxy_engine = _ScriptedEngine([
        _out({"score_1_to_5": 2, "agrees_with_judge": False, "reasoning_lines": ["title card missing on B-roll"], "cited_failure_modes": ["surface_realism_bias"]}),
        _out({"score_1_to_5": 2, "agrees_with_judge": False, "reasoning_lines": ["still a bit early"], "cited_failure_modes": []}),
    ])

    debater = make_debate(
        "M4", judge_engine, proxy_engine,
        config=DebateConfig(epsilon=0.25, max_rounds=4, retrieval_enabled=False),
    )
    verdict = debater.run(_sample(), _original_output())

    assert verdict.rounds_run == 2
    assert verdict.converged is True
    assert verdict.final_score == pytest.approx(3.7)
    assert verdict.initial_score == 3.0
    assert verdict.score_delta == pytest.approx(0.7)

    turns = verdict.transcript.turns
    assert len(turns) == 4
    assert [t.role for t in turns] == ["human_proxy", "judge", "human_proxy", "judge"]
    assert [t.round for t in turns] == [1, 1, 2, 2]

    assert verdict.reasoning_trace
    assert "mostly matches" in verdict.reasoning_trace  # original judge rationale carried through
    assert "title card missing on B-roll" in verdict.reasoning_trace

    assert verdict.failure_mode_summary == {"surface_realism_bias": 1}
    assert debate_prompt_versions() == {"D1": "v1", "D2": "v1"}
    assert verdict.transcript.judge_agent_prompt_version == "v1"
    assert verdict.transcript.human_proxy_prompt_version == "v1"


def test_retrieval_note_reaches_the_human_proxy_prompt(monkeypatch):
    note = RetrievedNote(
        text="a prior annotator flagged the voiceover as out of sync",
        source_path="/fake/other.json", item_id="prj-x::9::peanut", matched_terms=["sync"],
    )
    monkeypatch.setattr(debate_runner_module, "find_similar_human_note", lambda **kwargs: note)

    judge_engine = _ScriptedEngine([
        _out({"score_1_to_5": 3.1, "revised": True, "reasoning_lines": ["ok"], "evidence": []}),
    ])
    proxy_engine = _ScriptedEngine([
        _out({"score_1_to_5": 2, "agrees_with_judge": False, "reasoning_lines": ["gap"], "cited_failure_modes": []}),
    ])

    debater = make_debate(
        "M4", judge_engine, proxy_engine,
        config=DebateConfig(epsilon=0.25, max_rounds=4, retrieval_enabled=True),
    )
    verdict = debater.run(_sample(), _original_output())

    proxy_turn = verdict.transcript.turns[0]
    assert proxy_turn.retrieval_used is True
    assert proxy_turn.retrieved_note == note
    assert "a prior annotator flagged the voiceover as out of sync" in proxy_turn.prompt_user
