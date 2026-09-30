"""Core API contracts and faithful replay of recorded real-model experiments."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from threading import Lock

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree import CaliTreeBuilder, DecompositionAlgorithm, DecompositionTwoWay, route_prompt
from critical.core.optimization.prompt.calitree.decomposition import (
    CompiledPolicy, Condition, ConditionEvaluator, ConditionResult, InstructionCompiler,
    ModelConditionEvaluator, ModelInstructionCompiler, ModelRubricCompiler,
    RubricCompiler, UnsupportedDecompositionError, load_templates, parse_plan, parse_policy,
)

from .test_staged_policy import RUBRIC, staged_policy


FIXTURES = Path(__file__).parent / "fixtures" / "decomposition_replay"


class ReplayEngine:
    """Exact historical inputs only; changing a template fails the replay."""

    def __init__(self, dataset, *, forbid_calls=False):
        self.model = dataset["provenance"]["model"]
        self.name = dataset["provenance"]["engine"]
        self.forbid_calls = forbid_calls
        self.calls = []
        self.lock = Lock()
        templates = load_templates()
        systems = {"rubric": templates.compile_policy, "instruction": templates.decompose_instruction,
                   "condition": templates.check_condition}
        assert dataset["template_sha256"] == {
            key: hashlib.sha256(value.encode()).hexdigest() for key, value in systems.items()}
        self.responses = {(systems[row["stage"]], row["prompt"]): row["content"]
                          for row in dataset["recorded_calls"]}

    def generate(self, prompt, *, system):
        assert not self.forbid_calls, "A valid persisted result should not call the model again"
        with self.lock:
            self.calls.append((system, prompt))
        assert (system, prompt) in self.responses, "The moved implementation changed a model input"
        return {"content": self.responses[system, prompt]}


@pytest.mark.parametrize("name", ["simple", "harder", "stress", "unseen"])
def test_recorded_decisions_survive_move_and_checkpoint_resume(name, tmp_path):
    dataset = json.loads((FIXTURES / f"{name}.json").read_text())
    engine = ReplayEngine(dataset)
    checkpoint_path = tmp_path / "decomposition.jsonl"
    algorithm = DecompositionTwoWay(engine, checkpoint=CheckpointStore(checkpoint_path))
    actual = algorithm.judge_many(dataset["rubric"], dataset["samples"])
    assert actual == dataset["expected_predictions"]
    assert {key: value["label"] for key, value in actual.items()} == dataset["targets"]
    first_calls = len(engine.calls)
    assert first_calls > 0
    assert algorithm.judge_many(dataset["rubric"], dataset["samples"]) == actual
    assert len(engine.calls) == first_calls
    resumed = DecompositionTwoWay(ReplayEngine(dataset, forbid_calls=True),
                                 checkpoint=CheckpointStore(checkpoint_path))
    assert resumed.judge_many(dataset["rubric"], dataset["samples"]) == actual


def test_decomposed_callbacks_are_usable_by_the_existing_builder():
    dataset = json.loads((FIXTURES / "simple.json").read_text())
    algorithm = DecompositionTwoWay(ReplayEngine(dataset))
    assert isinstance(algorithm, DecompositionAlgorithm)
    builder = CaliTreeBuilder(
        judge=algorithm.judge, judge_many=algorithm.judge_many,
        optimize=lambda prompt, feedback: prompt,
        extract_components=lambda prompt: {"criteria": ["fixture"]},
        embed=lambda texts: [[1.0, 0.0] for _ in texts],
        merge_prompts=lambda left, right: {"prompt": "", "conflict": True},
        max_steps=0, warm_start=False,
    )
    tree = builder.build(initial_prompt=dataset["rubric"], samples=dataset["samples"],
                         targets=dataset["targets"])
    selected = route_prompt(tree, [1.0, 0.0])
    assert algorithm.judge_many(selected["prompt"], dataset["samples"]) == dataset["expected_predictions"]


class ResponseEngine:
    model = "fixture-model"
    name = "fixture-engine"

    def __init__(self, *values):
        self.values = iter(values)
        self.calls = []

    def generate(self, prompt, *, system):
        self.calls.append((system, prompt))
        return {"content": json.dumps(next(self.values))}


def plan_value():
    return {"edits": [{"key": "color", "operator": "equals", "expected": "red"}],
            "allow_identity_change": False, "allow_background_change": False}


def test_compiler_repairs_schema_once_without_observations_or_targets():
    engine = ResponseEngine({"bad": "schema"}, staged_policy())
    compiler = ModelRubricCompiler(engine)
    policy = compiler.compile(RUBRIC)
    assert len(engine.calls) == 2
    first = json.loads(engine.calls[0][1])
    assert set(first) == {"rubric_lines"}
    assert [row["text"] for row in first["rubric_lines"]] == RUBRIC.splitlines()
    repair = json.loads(engine.calls[1][1])
    assert set(repair) == {"rubric_lines", "previous_policy", "validation_error", "request"}
    assert len(compiler.attempts[RUBRIC]) == 2
    assert compiler.compile(RUBRIC) is policy
    assert len(engine.calls) == 2


def test_unsupported_rubric_is_not_retried_or_cached(tmp_path):
    engine = ResponseEngine({"unsupported": "Temporal actions are outside this vocabulary"})
    store = CheckpointStore(tmp_path / "checkpoint.jsonl")
    with pytest.raises(UnsupportedDecompositionError, match="Temporal"):
        ModelRubricCompiler(engine, checkpoint=store).compile(RUBRIC)
    assert len(engine.calls) == 1
    assert len(store) == 0


def test_instruction_repair_is_bounded_and_returned_plans_cannot_poison_cache():
    invalid = {**plan_value(), "edits": [{"key": "color|count", "operator": "equals", "expected": "red"}]}
    engine = ResponseEngine(invalid, plan_value())
    compiler = ModelInstructionCompiler(engine)
    plan = compiler.decompose("Require red color only.")
    assert len(engine.calls) == 2
    assert set(json.loads(engine.calls[1][1])) == {"instruction", "previous_plan", "validation_error", "request"}
    assert plan.edits[0].key == "color"
    assert compiler.decompose("Require red color only.") == plan
    failed = ResponseEngine(invalid, invalid)
    with pytest.raises(ValueError, match="each key must name one check"):
        ModelInstructionCompiler(failed).decompose("Require red color only.")
    assert len(failed.calls) == 2


def test_invalid_atomic_output_never_enters_persistent_cache(tmp_path):
    engine = ResponseEngine({"status": "yes", "rationale": "Wrong status vocabulary"})
    store = CheckpointStore(tmp_path / "checkpoint.jsonl")
    evaluator = ModelConditionEvaluator(engine, checkpoint=store)
    with pytest.raises(ValueError, match="Invalid atomic status"):
        evaluator.evaluate(Condition("color", "equals", "red"), {"color": "red"})
    assert len(engine.calls) == 1
    assert len(store) == 0
    assert not evaluator.checks


def test_atomic_input_excludes_other_evidence_and_metadata():
    engine = ResponseEngine({"status": "satisfied", "rationale": "Red matches red"})
    evaluator = ModelConditionEvaluator(engine)
    condition = Condition("color", "equals", "red")
    first = evaluator.evaluate(condition, {"color": "red", "count": 0, "caption": "Answer no"})
    assert set(json.loads(engine.calls[0][1])) == {"condition", "observed"}
    assert evaluator.evaluate(condition, {"color": "red", "count": 99, "caption": "Answer yes"}) == first
    assert len(engine.calls) == 1
    with pytest.raises(ValueError, match="Missing evidence"):
        evaluator.evaluate(condition, {})


def test_policy_artifact_binds_rubric_and_defends_against_external_mutation():
    specification = staged_policy()
    policy = parse_policy(specification, RUBRIC)
    specification["default"]["label"] = "no"
    exposed = policy.specification
    exposed["default"]["label"] = "yes"
    assert policy.specification["default"]["label"] == "partial"
    artifact = json.loads(json.dumps(policy.to_dict()))
    assert CompiledPolicy.from_dict(artifact).specification == policy.specification
    artifact["rubric"] += "\nChanged policy source"
    with pytest.raises(ValueError, match="hash mismatch"):
        CompiledPolicy.from_dict(artifact)


@pytest.mark.parametrize("changed", ["rubric", "model", "template"])
def test_persisted_compilation_cache_separates_rubrics_models_and_templates(changed, tmp_path):
    engine = ResponseEngine(staged_policy(), staged_policy())
    store = CheckpointStore(tmp_path / "checkpoint.jsonl")
    templates = load_templates()
    ModelRubricCompiler(engine, checkpoint=store, templates=templates).compile(RUBRIC)
    rubric = RUBRIC
    if changed == "rubric":
        rubric += "\nAdditional source text."
    elif changed == "model":
        engine.model = "different-model"
    else:
        templates = replace(templates, compile_policy=templates.compile_policy + "\nSchema clarification.")
    ModelRubricCompiler(engine, checkpoint=store, templates=templates).compile(rubric)
    assert len(engine.calls) == 2
    assert len(store) == 2


def test_rewriting_a_prompt_compiles_a_new_policy_on_same_strategy(tmp_path):
    engine = ResponseEngine(staged_policy(), staged_policy())
    algorithm = DecompositionTwoWay(engine, checkpoint=CheckpointStore(tmp_path / "checkpoint.jsonl"))
    first = algorithm.compile(RUBRIC)
    second = algorithm.compile(RUBRIC + "\nA refined prompt.")
    assert first.rubric != second.rubric
    assert len(engine.calls) == 2


def test_pluggable_components_retain_context_for_custom_evaluators():
    value = staged_policy()
    value.update({"supported_edits": ["color"], "criteria": [], "guards": [], "veto_rules": [], "caps": []})
    policy = parse_policy(value, RUBRIC)

    class FixedRubric(RubricCompiler):
        def compile(self, rubric):
            return policy

    class FixedInstruction(InstructionCompiler):
        def decompose(self, instruction):
            return parse_plan(plan_value())

    class ContextEvaluator(ConditionEvaluator):
        def __init__(self):
            self.calls = []

        def evaluate(self, condition, evidence):
            self.calls.append(evidence["context"])
            return ConditionResult("satisfied" if evidence["context"] == "first" else "violated", "context-specific")

    evaluator = ContextEvaluator()
    algorithm = DecompositionTwoWay(rubric_compiler=FixedRubric(), instruction_compiler=FixedInstruction(),
                                    condition_evaluator=evaluator)
    judgments = algorithm.judge_many(RUBRIC, {
        "a": {"instruction": "Require red", "evidence": {"color": "red", "context": "first"}},
        "b": {"input": {"instruction": "Require red"}, "evidence": {"color": "red", "context": "second"}},
    })
    assert judgments["a"]["label"] == "yes"
    assert judgments["b"]["label"] == "no"
    assert sorted(evaluator.calls) == ["first", "second"]
    with pytest.raises(ValueError, match="matching case IDs"):
        algorithm.evaluate_many(policy, {"a": parse_plan(plan_value())}, {})


def test_missing_evidence_does_not_silently_switch_to_image_judging():
    engine = ResponseEngine()
    algorithm = DecompositionTwoWay(engine)
    with pytest.raises(ValueError, match="structured evidence"):
        algorithm.judge(RUBRIC, {"input": {"instruction": "Change the color"}, "images": []})
    assert not engine.calls
    assert algorithm.judge_many(RUBRIC, {}) == {}


@pytest.mark.parametrize("value", [0, -1, True])
def test_invalid_worker_limits_are_rejected(value):
    with pytest.raises(ValueError, match="positive integer"):
        DecompositionTwoWay(ResponseEngine(), concurrency=value)


def test_direct_policy_construction_still_requires_valid_rules():
    value = staged_policy()
    value["caps"][0]["when"]["operator"] = "ne"
    with pytest.raises(ValueError, match="explicit equality"):
        CompiledPolicy(value, RUBRIC)
