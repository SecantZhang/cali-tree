"""Per-case fitting contracts; real model calls stay in the opt-in runner."""
from copy import deepcopy
import json

import pytest

from .casewise_fitting import CasewiseExperiment, aggregate, query_media, validate_plan


def plan(criterion="visible condition"):
    return {"conditions": [{"id": "c1", "requirement": "Close curtains", "source_selector": "source curtains",
                            "complete_when": criterion, "partial_when": "Some closure", "absent_when": "Remain open",
                            "unknown_when": "Curtains hidden"}], "rubric_conflicts": []}


def check(status):
    return {"source_observation": "Open curtains", "edited_observation": "Gap remains", "status": status, "rationale": "Visible gap"}


class Engine:
    model = "offline"
    temperature = 0
    max_tokens = 4096

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        value = deepcopy(next(self.outputs))
        return {"parsed": value, "content": json.dumps(value)}


def test_feedback_revises_plan_but_does_not_reach_checker(tmp_path):
    engine = Engine([plan(), check("complete"), plan("Curtains cover the window"), check("absent")])
    experiment = CasewiseExperiment(engine, tmp_path)
    result = experiment.fit("Close curtains", "Cached optimized rubric", [], "no", max_rounds=3)
    assert [r["label"] for r in result["rounds"]] == ["yes", "no"]
    assert result["matched"]
    first = json.loads(engine.calls[0][0].split("INPUT_JSON: ")[1])
    revised = json.loads(engine.calls[2][0].split("INPUT_JSON: ")[1])
    assert "human_training_feedback" not in first
    assert revised["human_training_feedback"] == {"label": "no"}
    for i in (1, 3):
        payload = json.loads(engine.calls[i][0].split("INPUT_JSON: ")[1])
        assert set(payload) == {"instruction", "condition"}
        assert "human_training_feedback" not in payload
        assert "previous_attempt" not in payload
    assert all(c[1]["strict_schema"] for c in engine.calls)
    # Identical replay uses cached verified stages, preserving the full fit trace.
    assert experiment.fit("Close curtains", "Cached optimized rubric", [], "no", max_rounds=3) == result
    assert len(engine.calls) == 4


def test_already_matching_case_gets_no_feedback(tmp_path):
    engine = Engine([plan(), check("partial")])
    result = CasewiseExperiment(engine, tmp_path).fit("Close curtains", "rubric", [], "partial", max_rounds=3)
    assert result["matched"] and len(result["rounds"]) == 1
    assert not result["rounds"][0]["feedback_used"]


def test_failed_fit_retains_failure_at_budget_limit(tmp_path):
    engine = Engine([plan(), check("complete")])
    result = CasewiseExperiment(engine, tmp_path).fit("Close curtains", "rubric", [], "no", max_rounds=1)
    assert not result["matched"]
    assert result["final_label"] == "yes"


def test_recorded_provenance_is_converted_to_image_media():
    arm = {"input": {"query": {"source_image_position": 3, "edited_image_position": 4}},
           "media": [{"path": "reference1"}, {"path": "reference2"},
                     {"position": 3, "path": "source.png", "sha256": "a"},
                     {"position": 4, "path": "edited.png", "sha256": "b"}]}
    assert query_media(arm) == [{"type": "image", "path": "source.png"}, {"type": "image", "path": "edited.png"}]


def test_pipeline_failure_does_not_trigger_label_feedback(tmp_path):
    class FailingEngine(Engine):
        def generate(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            raise RuntimeError("provider failure")
    engine = FailingEngine([])
    result = CasewiseExperiment(engine, tmp_path).fit("Close curtains", "rubric", [], "no", max_rounds=3)
    assert len(result["rounds"]) == 1 and not result["matched"]
    assert result["rounds"][0]["error"] == "provider failure"
    assert len(engine.calls) == 1


@pytest.mark.parametrize("statuses,label", [(["complete"], "yes"), (["complete", "partial"], "partial"),
                                            (["partial", "absent"], "no"), (["unknown"], "no")])
def test_aggregation_uses_actual_condition_results(statuses, label):
    assert aggregate([check(s) for s in statuses]) == label


def test_invalid_or_missing_checks_cannot_count_as_success():
    with pytest.raises(ValueError):
        aggregate([])
    with pytest.raises(ValueError):
        aggregate([check("desired-label")])
    p = plan()
    p["conditions"].append(deepcopy(p["conditions"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_plan(p)
