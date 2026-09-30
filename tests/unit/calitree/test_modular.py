"""Offline tests of modular artifacts, recursive merging, selection and GEPA RPC."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from critical.checkpoint import CheckpointStore
from critical.core.optimization.prompt.calitree import (
    ArtifactExecutor, CaliTreeLeafNode, CaliTreeMergeNode, CallbackMultiMergeAlgorithm,
    ConcatenateMergeAlgorithm, LeafController, MergeCoordinator, OptimizerPlan,
    SemanticCompleteLinkClustering, route_prompt, validate_tree,
)
from critical.core.optimization.prompt.calitree.context import BuildContext, CaliTreeServices
from critical.core.optimization.prompt.calitree.merge import GuardedMergeAcceptance
from critical.core.optimization.prompt.calitree.optimization.gepa import resolve_gepa_python
from critical.core.optimization.prompt.calitree.decomposition.artifacts import prompt_hash
from run.calitree_modular_demo import RUBRIC, demo_adapter, demo_builder, demo_sample

BAD = "Always no.\n" + RUBRIC


def context(*, samples=None, targets=None, max_steps=0, optimize=None, reflect=None,
            budget_available=None, merge=None, checkpoint=None):
    samples = samples or {key: demo_sample() for key in ("a", "b", "c", "d", "e")}
    targets = targets or {key: "yes" for key in samples}
    executor = ArtifactExecutor(demo_adapter(), checkpoint)
    builder = demo_builder(max_steps=max_steps)
    services = CaliTreeServices(executor.judge, optimize or (lambda text, _: text),
        lambda prompt: {"criteria": [prompt]}, lambda texts: [[1.0, 0.0] for _ in texts],
        lambda *_: {"prompt": RUBRIC}, judge_many=executor.judge_many,
        merge_many_prompts=merge or (lambda _: {"prompt": RUBRIC}), reflect=reflect,
        budget_available=budget_available)
    ctx = BuildContext(services, builder._settings(), None, RUBRIC, samples, targets,
        {"v": demo_sample()}, {"v": "yes"}, [], executor=executor, checkpoint=checkpoint,
        warm_prompt=RUBRIC, case_embeddings={key: [1, 0] for key in samples})

    def optimize_cases(prompt, ids, case_samples, case_targets):
        return OptimizerPlan("evaluate_only").optimize(prompt, ids, ctx).as_tuple()
    ctx.optimize_cases = optimize_cases
    return ctx


def leaves(ctx, groups=None):
    built = []
    for name, ids in (groups or {key: [key] for key in ctx.samples}).items():
        result = LeafController(OptimizerPlan("evaluate_only")).build(RUBRIC, ids, ctx, node_id=f"leaf:{name}")
        ctx.nodes[result.node.id], ctx.artifacts[result.node.id] = result.node, result.snapshot
        built.append(result.node)
    return built


def test_leaf_exports_policy_plan_checks_trace_without_changing_node_wire_fields():
    ctx = context()
    node = leaves(ctx)[0]
    snap = ctx.artifacts[node.id]
    assert snap["scope_ids"] == snap["served_ids"] == snap["correct_ids"] == ["a"]
    row = ctx.executor.evaluations[snap["evaluation_refs"]["a"]]
    assert row["plan"]["edits"][0]["expected"] == "red"
    assert row["checks"]["edits"][0]["key"] == "color"
    assert row["trace"]["label"] == "yes"
    assert "scope_ids" not in asdict(node)


def test_three_children_joint_merge_is_one_call_and_preserves_inputs():
    seen = []
    ctx = context(merge=lambda rows: seen.append(rows) or {"prompt": RUBRIC})
    children = leaves(ctx)[:3]
    before = [asdict(node) for node in children]
    result = MergeCoordinator(CallbackMultiMergeAlgorithm(), GuardedMergeAcceptance()).merge_many(children, ctx)
    assert result.decision.accepted
    assert result.covered_ids == result.served_ids == ["a", "b", "c"]
    assert len(seen) == 1 and [row["id"] for row in seen[0]] == [node.id for node in children]
    assert all(row["policy"]["rubric"] == RUBRIC for row in seen[0])
    assert [asdict(node) for node in children] == before


def test_mixed_children_full_scope_includes_earlier_unserved_cases_and_deduplicates():
    ctx = context()
    originals = leaves(ctx)
    left = CaliTreeMergeNode("parent1", RUBRIC, ["a", "b"], [1, 0], {},
                            level=4, children=[originals[0].id, originals[1].id])
    right = CaliTreeMergeNode("parent2", RUBRIC, ["c"], [1, 0], {}, level=1)
    for node, scope, served in ((left, ["a", "b", "c"], ["a", "b"]),
                                (right, ["b", "c", "d"], ["c"])):
        ctx.nodes[node.id] = node
        ctx.artifacts[node.id] = {"scope_ids": scope, "served_ids": served}
    result = MergeCoordinator(ConcatenateMergeAlgorithm(), GuardedMergeAcceptance()).merge_many(
        [left, right, originals[-1]], ctx)
    assert result.decision.accepted
    assert result.covered_ids == ["a", "b", "c", "d", "e"]
    assert result.served_ids == ["a", "b", "c", "e"]


def test_merge_rejects_duplicates_ancestors_cycles_and_missing_validation():
    ctx = context()
    children = leaves(ctx)
    coordinator = MergeCoordinator(ConcatenateMergeAlgorithm(), GuardedMergeAcceptance())
    for invalid in ([children[0]], [children[0], children[0]]):
        with pytest.raises(ValueError):
            coordinator.merge_many(invalid, ctx)
    children[0].children = [children[1].id]
    with pytest.raises(ValueError, match="descendant"):
        coordinator.merge_many(children[:2], ctx)
    children[0].children = [children[0].id]
    with pytest.raises(ValueError):
        coordinator.merge_many(children[:2], ctx)
    children[0].children = []
    ctx.validation_samples, ctx.validation_targets = {}, {}
    assert coordinator.merge_many(children[:3], ctx).decision.kind == "missing_reserved_validation"


def test_rejected_group_retains_children_and_is_not_retried():
    seen = []
    builder = demo_builder(merge_many_prompts=lambda rows: seen.append(rows) or
                           {"prompt": "", "conflict": True, "conflict_reason": "incompatible"})
    tree = builder.build(initial_prompt=RUBRIC, samples={k: demo_sample() for k in "abc"},
        targets={k: "yes" for k in "abc"}, validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    proposed_groups = [frozenset(row["id"] for row in group) for group in seen]
    assert len(proposed_groups) == len(set(proposed_groups))
    assert proposed_groups.count(frozenset(("leaf:a", "leaf:b", "leaf:c"))) == 1
    assert tree["stats"]["accepted_merges"] == 0
    assert len(tree["nodes"][tree["roots"][0]]["children"]) == 3


def test_partial_promotions_measure_wrong_source_and_full_scope_survives():
    ctx = context(samples={key: demo_sample("blue" if key == "e" else "red") for key in "abcde"})
    children = leaves(ctx)
    result = MergeCoordinator(ConcatenateMergeAlgorithm(), GuardedMergeAcceptance()).merge_many(children, ctx)
    assert result.decision.accepted and result.optimization.accuracy == 0.8
    assert result.covered_ids == list("abcde") and result.served_ids == list("abcd")
    tree = demo_builder(max_merge_children=5).build(initial_prompt=RUBRIC,
        samples=ctx.samples, targets=ctx.targets, validation_samples=ctx.validation_samples,
        validation_targets=ctx.validation_targets)
    promoted = [n for n in tree["nodes"].values() if n["status"] == "promoted"]
    assert promoted and promoted[0]["validation_accuracy"] == 0
    parents = [n for n in tree["nodes"].values() if n["id"].startswith("merge:")]
    assert all(tree["artifacts"]["nodes"][n["id"]]["scope_ids"] == list("abcde") for n in parents)
    assert len(parents) >= 2  # later merges still retain the original full scope


def test_grouping_is_deterministic_and_checks_every_pair():
    ctx = context()
    children = leaves(ctx)
    clustering = SemanticCompleteLinkClustering()
    args = dict(level=2, max_children=3, blocked_pairs={frozenset((children[0].id, children[2].id))},
                blocked_groups=set(), context=ctx)
    first, remaining = clustering.groups(children, 0.9, **args)
    second, _ = clustering.groups(list(reversed(children)), 0.9, **args)
    assert [[n.id for n in g] for g, _ in first] == [[n.id for n in g] for g, _ in second]
    assert all(len(g) <= 3 for g, _ in first)
    assert all(not {children[0].id, children[2].id} <= {n.id for n in g} for g, _ in first)
    assert sum(len(g) for g, _ in first) + len(remaining) == 5


def test_round_trip_reuses_saved_policy_and_detects_tampering():
    tree = demo_builder().build(initial_prompt=RUBRIC, samples={k: demo_sample() for k in "abc"},
        targets={k: "yes" for k in "abc"}, validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    restored = json.loads(json.dumps(tree))
    adapter = demo_adapter()
    adapter.compile = lambda _: pytest.fail("Inference recompiled a frozen policy")
    executor = ArtifactExecutor(adapter)
    validate_tree(restored, executor)
    routed = route_prompt(restored, [1, 0])
    assert executor.judge(routed["prompt"], demo_sample())["label"] == "yes"
    assert any(len(n["children"]) == 3 and n["status"] == "accepted" for n in tree["nodes"].values())
    restored["nodes"][routed["id"]]["prompt"] += "tampered"
    with pytest.raises(ValueError, match="binding"):
        validate_tree(restored, executor)


def test_checkpoint_resume_and_prompt_changes_bind_new_policy(tmp_path):
    store = CheckpointStore(tmp_path / "artifacts.jsonl")
    executor = ArtifactExecutor(demo_adapter(), store)
    assert executor.judge(RUBRIC, demo_sample())["label"] == "yes"
    assert executor.judge(BAD, demo_sample())["label"] == "no"
    assert set(executor.policies) == {prompt_hash(RUBRIC), prompt_hash(BAD)}
    adapter = demo_adapter()
    adapter.compile = adapter.evaluate = lambda *_: pytest.fail("Resume made a model call")
    resumed = ArtifactExecutor(adapter, CheckpointStore(store.path))
    assert resumed.judge(RUBRIC, demo_sample())["label"] == "yes"


def test_evidence_preflight_before_compilation_and_annotated_metadata_not_forwarded():
    adapter = demo_adapter()
    adapter.compile = lambda *_: pytest.fail("Invalid input caused compilation")
    with pytest.raises(ValueError, match="structured evidence"):
        ArtifactExecutor(adapter).judge(RUBRIC, {"input": {"instruction": "Make it red"}, "images": []})
    executor = ArtifactExecutor(demo_adapter())
    row = executor.judge(RUBRIC, {**demo_sample(), "target_label": "no", "editor": "secret", "item_id": "secret"})
    assert "secret" not in json.dumps(row)


def test_optimizer_selects_seed_on_regression_and_reports_budget_stop():
    ctx = context(max_steps=3, optimize=lambda *_: BAD)
    # Seed is imperfect so the optimizer attempts a rewrite, but the rewrite is worse.
    ctx.targets["e"] = "no"
    result = OptimizerPlan().optimize(RUBRIC, list(ctx.samples), ctx)
    assert result.prompt == RUBRIC and result.steps == 3
    ctx.services = replace(ctx.services, budget_available=lambda: False)
    stopped = OptimizerPlan().optimize(BAD, list(ctx.samples), ctx)
    assert stopped.prompt == BAD and stopped.report["stop_reason"] == "budget_exhausted"


def test_empty_training_and_bad_configuration():
    tree = demo_builder().build(initial_prompt=RUBRIC, samples={}, targets={})
    assert tree["stats"]["leaves"] == 0 and len(tree["nodes"]) == 1
    with pytest.raises(ValueError, match="empty|nonempty"):
        LeafController().build(RUBRIC, [], context(), node_id="empty")
    with pytest.raises(ValueError, match="Combined"):
        demo_builder(optimizer_plan="best_of_both", max_steps=1)
    with pytest.raises(ValueError, match="replacement"):
        demo_builder(specialization_mode="additive")


def gepa_python():
    try:
        return resolve_gepa_python()
    except ValueError:
        pytest.skip("Explicit GEPA environment is not installed")


@pytest.mark.parametrize("plan", ["gepa", "textgrad_then_gepa", "gepa_then_textgrad", "best_of_both"])
def test_real_gepa_rpc_and_composition_with_offline_parent_callbacks(plan):
    reflected = []
    def reflect(messages):
        reflected.append(messages)
        return "```\n" + RUBRIC + "\n```"
    # TextGrad's candidate equals the seed, leaving improvement to real GEPA.
    ctx = context(max_steps=2, reflect=reflect)
    ctx.validation_samples = {"secret_validation": {"instruction": "SECRET_VALIDATION_INSTRUCTION"}}
    ctx.validation_targets = {"secret_validation": "no"}
    result = OptimizerPlan(plan, gepa_python=gepa_python()).optimize(BAD, ["a", "b"], ctx)
    assert result.prompt == RUBRIC and result.accuracy == 1
    assert result.steps <= 2 and reflected
    assert all("secret_validation" not in json.dumps(row) for row in reflected)
    assert all("SECRET_VALIDATION_INSTRUCTION" not in json.dumps(row) for row in reflected)
    assert sum(stage["allowance"] for stage in result.report["stages"]) == 2
    events = [e["event"] for stage in result.report["lineage"] for e in stage.get("events", [])]
    assert "evaluate" in events and "reflect" in events


def test_gepa_worker_failure_and_budget_exhaustion_are_explicit():
    ctx = context(max_steps=1, reflect=lambda _: (_ for _ in ()).throw(RuntimeError("reflection failure")))
    with pytest.raises(RuntimeError, match="reflection failure"):
        OptimizerPlan("gepa", gepa_python=gepa_python()).optimize(BAD, ["a"], ctx)
    ctx.services = replace(ctx.services, budget_available=lambda: False)
    result = OptimizerPlan("gepa", gepa_python=gepa_python()).optimize(BAD, ["a"], ctx)
    assert result.report["stop_reason"] == "budget_exhausted" and result.prompt == BAD
    with pytest.raises(ValueError, match="interpreter"):
        resolve_gepa_python("/definitely/missing/python")


def test_real_textgrad_adapter_with_deterministic_engine(tmp_path):
    pytest.importorskip("textgrad")
    from critical.core.optimization.prompt.calitree import TextGradLeafOptimizer
    calls = []
    class Engine:
        model = "offline-textgrad"
        def generate(self, prompt, system=None):
            calls.append((prompt, system))
            return {"content": "<IMPROVED_VARIABLE>" + RUBRIC + "</IMPROVED_VARIABLE>",
                    "promptTokens": 2, "completionTokens": 3, "totalTokens": 5}
    ctx = context(max_steps=2)
    usage = []
    result = TextGradLeafOptimizer(Engine(), usage_cb=usage.append, log_dir=tmp_path).optimize(BAD, ["a"], ctx)
    assert result.prompt == RUBRIC and result.accuracy == 1 and result.steps == 1
    assert len(calls) == len(usage) == 1


def test_automatic_mixed_group_depth_and_attempt_budget():
    samples = {str(key): demo_sample() for key in range(7)}
    tree = demo_builder().build(initial_prompt=RUBRIC, samples=samples,
        targets={key: "yes" for key in samples}, validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    last = tree["nodes"]["merge:3"]
    assert len(last["children"]) == 3 and last["level"] == 2
    assert sum(child.startswith("merge:") for child in last["children"]) == 2
    assert tree["artifacts"]["nodes"][last["id"]]["scope_ids"] == sorted(samples)
    limited = demo_builder(max_merge_attempts=1).build(initial_prompt=RUBRIC, samples=samples,
        targets={key: "yes" for key in samples}, validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    assert limited["stats"]["merge_attempts"] == 1
    assert len(limited["nodes"][limited["roots"][0]]["children"]) == 5


def test_invalid_export_and_mutated_evidence_do_not_hit_old_result():
    adapter = demo_adapter()
    executor = ArtifactExecutor(adapter)
    assert executor.judge(RUBRIC, demo_sample())["label"] == "yes"
    assert executor.judge(RUBRIC, demo_sample("blue"))["label"] == "no"
    adapter.evaluate = lambda *_: {"label": "invalid"}
    with pytest.raises(ValueError, match="Malformed"):
        executor.judge(RUBRIC, demo_sample("purple"))
    payload = deepcopy(executor.policies)
    payload[prompt_hash(RUBRIC)]["payload"]["rubric"] += "changed"
    with pytest.raises(ValueError):
        ArtifactExecutor(demo_adapter()).load_policies(payload, strategy="two_way")


def test_optimizer_checkpoint_identity_stage_allowances_and_usage(tmp_path):
    state = {"calls": 0, "completion_tokens": 0}
    def update(prompt, _):
        state["calls"] += 1
        state["completion_tokens"] += 7
        return prompt
    ctx = context(max_steps=3, checkpoint=CheckpointStore(tmp_path / "checkpoints.jsonl"), optimize=update)
    ctx.services = replace(ctx.services, optimizer_identity={"model": "first"},
                           optimizer_usage=lambda: dict(state))
    plan = OptimizerPlan()
    first = plan.optimize(BAD, ["a"], ctx)
    assert first.report["usage"] == {"calls": 1, "completion_tokens": 7}
    plan.optimize(BAD, ["a"], ctx)
    assert state["calls"] == 1
    ctx.services = replace(ctx.services, optimizer_identity={"model": "second"})
    plan.optimize(BAD, ["a"], ctx)
    assert state["calls"] == 2
    ctx.services = replace(ctx.services, reflect=lambda _: "```\n" + RUBRIC + "\n```")
    both = OptimizerPlan("best_of_both", gepa_python=gepa_python()).optimize(BAD, ["a"], ctx)
    assert [stage["allowance"] for stage in both.report["stages"]] == [1, 2]
    assert both.report["stop_reason"] == "success"


def test_loaded_parent_cannot_shrink_scope_or_change_depth():
    tree = demo_builder().build(initial_prompt=RUBRIC,
        samples={key: demo_sample() for key in ("a", "b", "c")},
        targets={key: "yes" for key in ("a", "b", "c")},
        validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    broken = deepcopy(tree)
    snap = broken["artifacts"]["nodes"]["merge:1"]
    snap["scope_ids"] = snap["served_ids"] = snap["correct_ids"] = ["a"]
    with pytest.raises(ValueError, match="scope union"):
        validate_tree(broken, ArtifactExecutor(demo_adapter()))
    broken = deepcopy(tree)
    broken["nodes"]["merge:1"]["level"] = 99
    with pytest.raises(ValueError, match="depth"):
        validate_tree(broken, ArtifactExecutor(demo_adapter()))


def test_gepa_worker_exit_is_reported_without_credentials(tmp_path, monkeypatch):
    import subprocess
    import critical.core.optimization.prompt.calitree.optimization.gepa as transport
    worker = tmp_path / "fail_worker.py"
    worker.write_text("import json, os, sys\njson.loads(sys.stdin.readline())\n"
                      "assert 'CALITREE_TEST_PROVIDER_SECRET' not in os.environ\n"
                      "sys.stderr.write('offline worker failure')\nsys.exit(3)\n")
    python = gepa_python()
    original = subprocess.Popen
    def launch(command, **kwargs):
        return original([*command[:-1], str(worker)], **kwargs)
    monkeypatch.setenv("CALITREE_TEST_PROVIDER_SECRET", "must-stay-in-parent")
    monkeypatch.setattr(transport, "resolve_gepa_python", lambda _: python)
    monkeypatch.setattr(transport.subprocess, "Popen", launch)
    ctx = context(max_steps=1, reflect=lambda _: "unused")
    with pytest.raises(RuntimeError, match="worker exited.*offline worker failure"):
        OptimizerPlan("gepa", gepa_python=python).optimize(BAD, ["a"], ctx)


def test_rejected_joint_group_allows_a_different_subset():
    calls = []
    def synthesize(rows):
        group = tuple(row["id"] for row in rows)
        calls.append(group)
        return {"prompt": RUBRIC if group == ("leaf:a", "leaf:b") else "", "conflict": len(rows) == 3}
    tree = demo_builder(merge_many_prompts=synthesize).build(initial_prompt=RUBRIC,
        samples={key: demo_sample() for key in "abc"}, targets={key: "yes" for key in "abc"},
        validation_samples={"v": demo_sample()}, validation_targets={"v": "yes"})
    assert calls.count(("leaf:a", "leaf:b", "leaf:c")) == 1
    assert calls.count(("leaf:a", "leaf:b")) == 1
    assert tree["stats"]["accepted_merges"] == 1
    assert len(tree["nodes"][tree["roots"][0]]["children"]) == 2


def test_balanced_candidate_selection_and_stable_ties():
    samples = {key: demo_sample() for key in "abcdef"}
    targets = dict.fromkeys("abcd", "yes") | {"e": "no", "f": "partial"}
    ctx = context(samples=samples, targets=targets, max_steps=1, optimize=lambda *_: "candidate")
    def judge(prompt, selected):
        labels = dict.fromkeys("abcdef", "yes") if prompt == "seed" else {
            "a": "yes", "b": "no", "c": "no", "d": "no", "e": "no", "f": "partial"}
        return {key: {"label": labels[key]} for key in selected}
    ctx.services = replace(ctx.services, judge_many=judge)
    result = OptimizerPlan().optimize("seed", list(samples), ctx)
    assert result.prompt == "candidate" and result.accuracy == 0.5
    assert result.report["history"][0]["accuracy"] == pytest.approx(4 / 6)
    ctx.services = replace(ctx.services, judge_many=lambda _, selected: {
        key: {"label": "yes"} for key in selected})
    assert OptimizerPlan().optimize("seed", list(samples), ctx).prompt == "seed"
