from copy import deepcopy
import json
import pytest

from .assumption3_probe import BudgetedEngine, BudgetExhausted, run_case
from .test_casewise_fitting import plan, check


class Engine:
    model = "offline"
    temperature = 0
    max_tokens = 100

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, **kwargs):
        self.calls += 1
        return {"completionTokens": 40, "promptTokens": 20}


def test_budget_reserves_before_call_and_survives_restart(tmp_path):
    path = tmp_path / "budget.json"
    raw = Engine()
    engine = BudgetedEngine(raw, path, 2, 140)
    engine.generate("first")
    restored = BudgetedEngine(raw, path, 2, 140)
    restored.generate("second")
    with pytest.raises(BudgetExhausted, match="allowance"):
        restored.generate("third")
    assert raw.calls == 2
    assert restored.usage["completion_tokens_or_reserved"] == 80


def test_insufficient_completion_allowance_stops_before_provider(tmp_path):
    raw = Engine()
    engine = BudgetedEngine(raw, tmp_path / "budget.json", 3, 100)
    engine.generate("first")
    with pytest.raises(BudgetExhausted, match="reserve"):
        engine.generate("second")
    assert raw.calls == 1


def test_failure_keeps_conservative_reservation(tmp_path):
    class Broken(Engine):
        def generate(self, *args, **kwargs):
            raise RuntimeError("provider failed")
    path = tmp_path / "budget.json"
    engine = BudgetedEngine(Broken(), path, 2, 100)
    with pytest.raises(RuntimeError, match="provider"):
        engine.generate("first")
    assert json.loads(path.read_text())[0]["charged_completion"] == 100
    restored = BudgetedEngine(Engine(), path, 2, 100)
    with pytest.raises(BudgetExhausted):
        restored.generate("second")


def test_frozen_plan_checker_does_not_receive_fit_labels_or_conflicts():
    inputs = []
    class Experiment:
        def request(self, stage, payload, *args):
            inputs.append(deepcopy(payload))
            return check("partial"), "key"
    row = {"instruction": "Close curtains", "plan": plan(),
           "human_label": "partial", "final_decomposed": "no", "feedback_used": True,
           "checks": [{"condition_id": "c1", **check("absent")}], "media": [],
           "neutral_observations": {"source": "open", "edited": "gap"}}
    row["plan"]["rubric_conflicts"] = ["Human feedback selected a no result"]
    result = run_case(Experiment(), row, "neutral")
    assert result["label"] == "partial" and result["matches_human"]
    assert result["statuses_changed_from_selected_fit"] == ["c1"]
    assert set(inputs[0]) == {"instruction", "condition", "independent_neutral_observations"}
    assert "Human feedback" not in json.dumps(inputs[0])


def test_bound_fresh_neutral_runner_and_restart(tmp_path):
    from .assumption3_probe import run_bound_case
    from .test_casewise_fitting import Engine as Responses
    from .test_decision_sets import images, neutral, answer
    evidence, hashes = images(tmp_path)
    row = {"instruction": "Close curtains", "optimized_prompt": "rubric", "plan": plan(),
           "human_label": "partial", "feedback_used": True, "criteria_origin": "saved-fit",
           "checks": [{"condition_id": "c1", **check("absent")}],
           "images": [{"path": evidence[k], "sha256": h} for k, h in
                      zip(("source_image", "edited_image"), hashes)], "bound_neutral": neutral(hashes)}
    raw = Responses([answer(), answer(), check("partial")])
    result = run_bound_case(raw, tmp_path, row, "fresh-neutral")
    assert result["valid"] and result["matches_human"]
    assert len(raw.calls) == 3
    assert result["observations"]["neutral_evidence"]["origin"].startswith("observer-checkpoints:")
    replay = Responses([])
    assert run_bound_case(replay, tmp_path, row, "fresh-neutral") == result
    assert not replay.calls
