"""Workflow wiring and portable policy inference with offline engines."""

from copy import deepcopy
import json

import pytest

from critical.interface.node_calibration.calitree_nodes import (
    CaliTreeTrainNodeExecutor, CaliTreeJudgeNodeExecutor, _CaliTreeRuntime,
)
from critical.core.optimization.prompt.calitree.decomposition import load_templates
from run.calitree_modular_demo import RUBRIC, DemoRubricCompiler, DemoInstructionCompiler


def dataset():
    samples = {f"task{key}::editor": {"item_id": f"task{key}::editor",
        "split": "test" if key == 12 else "train", "editor": "editor",
        "input": {"instruction": "Make it red", "source_image_path": "/unused/source.jpg"},
        "output": {"edited_image_path": "/unused/edited.jpg"}, "evidence": {"color": "red"}}
        for key in range(13)}
    return samples, {key: {"target_label": "yes", "split": row["split"]} for key, row in samples.items()}


def inputs():
    samples, labels = dataset()
    return {"samples": samples, "labels": labels, "judge_engine": {"model": "offline"},
            "optimizer_engine": {"model": "offline", "max_tokens": 1000}}


class OfflineEngine:
    name = "offline"
    model = "offline"
    temperature = 0
    max_tokens = 1000
    def __init__(self):
        self.calls = []
    def generate(self, prompt, *, system=None, **kwargs):
        self.calls.append((prompt, system))
        templates = load_templates()
        if system == templates.compile_policy:
            rubric = "\n".join(row["text"] for row in json.loads(prompt)["rubric_lines"])
            value = DemoRubricCompiler().compile(rubric).specification
        elif system == templates.decompose_instruction:
            value = DemoInstructionCompiler().decompose(prompt).to_dict()
        elif system == templates.check_condition:
            value = {"status": "satisfied", "rationale": "observed red"}
        elif "Synthesize one reusable" in prompt:
            value = {"prompt": RUBRIC, "conflict": False, "conflict_reason": ""}
        else:
            value = {"criteria": ["judge requested change"], "priorities": [], "constraints": []}
        return {"content": json.dumps(value), "promptTokens": 1, "completionTokens": 2, "totalTokens": 3}


def test_modular_dry_run_counts_new_stages_without_engine_creation(make_ctx, monkeypatch):
    monkeypatch.setattr("critical.interface.node_calibration.calitree_nodes._engine_from",
                        lambda *_: pytest.fail("Dry run created an engine"))
    result = CaliTreeTrainNodeExecutor().run(make_ctx(params={"modular_mode": True,
        "optimizer_plan": "best_of_both", "max_merge_children": 4}, inputs=inputs()))
    assert result.status == "done"
    assert result.meta["modular_strategies"]["max_merge_children"] == 4
    assert result.meta["estimated_calls"]["gepa_reflection_max"] > 0
    assert result.outputs == {"prompt_tree": {}, "calitree_report": {}}


@pytest.mark.parametrize("options", [
    {"architecture": "rubric_lite"}, {"specialization_mode": "additive"},
    {"max_merge_children": 1}, {"max_merge_children": 2.5},
    {"optimizer_plan": "unknown"}, {"decomposition_strategy": "unknown"},
    {"merge_strategy": "unknown"}, {"optimizer_plan": "best_of_both", "max_steps": 1},
])
def test_invalid_modular_settings_fail_before_calls(make_ctx, options):
    result = CaliTreeTrainNodeExecutor().run(make_ctx(inputs=inputs(), params={"modular_mode": True, **options}))
    assert result.status == "error" and result.error


def test_workflow_train_reload_and_judge_executes_saved_policy(make_ctx, monkeypatch):
    engine = OfflineEngine()
    monkeypatch.setattr("critical.interface.node_calibration.calitree_nodes._engine_from", lambda *_: engine)
    monkeypatch.setattr(_CaliTreeRuntime, "embed", lambda _, texts: [[1, 0] for _ in texts])
    monkeypatch.setattr("critical.interface.node_calibration.calitree_nodes._prompt", lambda *_: RUBRIC)
    result = CaliTreeTrainNodeExecutor().run(make_ctx(inputs=inputs(), dry_run=False, allow_live=True,
        params={"modular_mode": True, "max_merge_children": 3, "warm_start": False,
                "optimizer_plan": "evaluate_only", "embedding_model": "offline",
                "run_baselines": False, "run_conflict_resolver": False}))
    assert result.status == "done"
    tree = json.loads(json.dumps(result.outputs["prompt_tree"]))
    assert tree["version"] == "calitree-modular-v1"
    assert any(len(n["children"]) == 3 and n["status"] == "accepted" for n in tree["nodes"].values())
    assert result.outputs["calitree_report"]["usage"]["decomposition_calls"] > 0
    samples = {"new": {**next(iter(dataset()[0].values())), "item_id": "new"}}
    before = len(engine.calls)
    judged = CaliTreeJudgeNodeExecutor().run(make_ctx(node_id="judge", dry_run=False, allow_live=True,
        inputs={"samples": samples, "prompt_tree": tree, "judge_engine": {"model": "offline"}}))
    assert judged.status == "done"
    row = judged.outputs["judge_result"]["new"]["calitree"]
    assert row["label"] == "yes" and row["trace"]["label"] == "yes"
    assert all(system != load_templates().compile_policy for _, system in engine.calls[before:])
    broken = deepcopy(tree)
    broken["nodes"][broken["roots"][0]]["prompt"] = "tampered"
    invalid = CaliTreeJudgeNodeExecutor().run(make_ctx(node_id="bad", dry_run=False, allow_live=True,
        inputs={"samples": samples, "prompt_tree": broken, "judge_engine": {"model": "offline"}}))
    assert invalid.status == "error" and "binding" in invalid.error


def test_optimizer_engine_clamps_budget_and_records_once(make_ctx):
    engine = OfflineEngine()
    runtime = _CaliTreeRuntime(make_ctx(), judge_engine=engine, optimizer_engine=engine,
                              embedding_model="unused", optimizer_budget=2)
    result = runtime._bounded_generate("extract criteria")
    assert result["completionTokens"] == 2
    assert engine.max_tokens == 1000  # clamping applies to a copy
    assert runtime.usage["optimizer_calls"] == 1 and runtime.optimizer_completion_tokens == 2
    from critical.core.optimization.prompt.calitree.optimization.gepa import BudgetExhausted
    with pytest.raises(BudgetExhausted):
        runtime.reflect("no remaining budget")


def test_decomposition_checkpoint_recompiles_when_model_settings_change(make_ctx):
    engine = OfflineEngine()
    ctx = make_ctx()
    runtime = _CaliTreeRuntime(ctx, judge_engine=engine, optimizer_engine=engine,
                              embedding_model="unused", optimizer_budget=100)
    runtime.configure_modular("two_way")
    sample = next(iter(dataset()[0].values()))
    runtime.modular_executor.judge(RUBRIC, sample)
    before = len(engine.calls)
    runtime.configure_modular("two_way")
    runtime.modular_executor.judge(RUBRIC, sample)
    assert len(engine.calls) == before
    engine.temperature = 0.5
    runtime.configure_modular("two_way")
    runtime.modular_executor.judge(RUBRIC, sample)
    assert any(system == load_templates().compile_policy for _, system in engine.calls[before:])


def test_train_excludes_quarantined_annotations_and_population_priors(make_ctx):
    from tests.unit.calitree.test_annotation_quality import REVIEW
    data = inputs()
    data['labels']['task0::editor']['annotation_review'] = REVIEW
    data['population_labels'] = {'outside': {'target_label': 'yes', 'split': 'train', 'annotation_review': REVIEW}}
    result = CaliTreeTrainNodeExecutor().run(make_ctx(inputs=data, params={'modular_mode': True}))
    assert result.status == 'done', result.error
    assert result.meta['n_train'] == 11
    assert set(result.meta['annotation_quarantine']) == {'task0::editor'}
    assert set(result.meta['population_annotation_quarantine']) == {'outside'}
    assert 'annotation_quarantine' in result.outputs['calitree_report']


def test_eval_reports_quarantine_outside_primary_agreement_denominator(make_ctx):
    from critical.interface.node_calibration.calitree_nodes import CaliTreeEvalNodeExecutor
    from tests.unit.calitree.test_annotation_quality import REVIEW
    samples, labels = dataset()
    labels['task0::editor']['annotation_review'] = REVIEW
    result = CaliTreeEvalNodeExecutor().run(make_ctx(inputs={'samples': samples, 'labels': labels,
        'judge_result': {k: {'calitree': {'label': 'yes'}} for k in samples}}))
    assert result.status == 'done', result.error
    assert result.meta['n_items'] == 12
    assert set(result.outputs['metrics_report']['annotation_quarantine']) == {'task0::editor'}
