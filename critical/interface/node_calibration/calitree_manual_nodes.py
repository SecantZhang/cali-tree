"""Manual CaliTree canvas operations and durable, independently pinnable stages."""
from dataclasses import asdict, replace
from copy import deepcopy
from uuid import uuid4

from ...core.optimization.prompt.calitree import CaliTreeBuilder
from ...core.optimization.prompt.calitree.annotation_quality import partition_annotations
from ...core.optimization.prompt.calitree.context import BuildContext, OptimizationResult
from ...core.optimization.prompt.calitree.decomposition.artifacts import digest, prompt_hash
from ...core.optimization.prompt.calitree.evaluation import balanced_accuracy
from ...core.optimization.prompt.calitree.node.base import CaliTreeNode
from ...core.optimization.prompt.calitree.node.leaf_controller import LeafController
from ...core.optimization.prompt.calitree.node.stages import StageRunner, LEAF_STAGES, MERGE_STAGES
from ...core.optimization.prompt.calitree.optimization.composite import OptimizerPlan, PLANS
from ...core.optimization.prompt.calitree.merge.coordinator import MergeCoordinator
from ...core.optimization.prompt.calitree.merge.acceptance import GuardedMergeAcceptance
from ...core.optimization.prompt.calitree.merge.callback import CallbackMultiMergeAlgorithm, ConcatenateMergeAlgorithm
from ..server.registry import NodeExecutor, NodeRunResult, register
from ..server.artifacts import load_artifact, save_artifact
from . import calitree_nodes as legacy

NODE_VERSION = "calitree-node-v1"


@register
class CaliTreePartitionNodeExecutor(NodeExecutor):
    node_type, category = "calitree_partition", "node_calibration"
    input_sockets = {"samples": "samples", "labels": "labels"}
    output_sockets = {"partition": "calitree_data", "test_samples": "samples", "test_labels": "labels"}
    param_schema = {"validation_fraction": {"type": "number", "default": .25, "min": .01, "max": .99},
                    "seed": {"type": "number", "default": 44}}

    def run(self, ctx):
        try:
            samples, labels = ctx.inputs["samples"], ctx.inputs["labels"]
            fraction, seed = float(ctx.params.get("validation_fraction", .25)), int(ctx.params.get("seed", 44))
            if not 0 < fraction < 1:
                raise ValueError("validation_fraction must be between zero and one")
            _, quarantined = partition_annotations(labels)
            groups, train, test = {}, [], []
            for key, sample in sorted(samples.items()):
                label = labels.get(key)
                if not isinstance(label, dict) or (key not in quarantined and legacy._target(label) not in {"no", "partial", "yes"}):
                    raise ValueError(f"Missing no/partial/yes annotation for {key}")
                split = label.get("split")
                task = str(sample.get("task_uid") or label.get("task_uid") or key.split("::")[0])
                if split not in {"train", "test"} or sample.get("split", split) != split:
                    raise ValueError(f"Official train/test partition is missing or inconsistent for {key}")
                if task in groups and groups[task] != split:
                    raise ValueError(f"Task {task} crosses official partitions")
                if sample.get("task_uid") and label.get("task_uid") and sample["task_uid"] != label["task_uid"]:
                    raise ValueError(f"Conflicting task identity for {key}")
                if sample.get("item_id", key) != key:
                    raise ValueError(f"Conflicting case identity for {key}")
                groups[task] = split
                if split == "test":
                    test.append(key)  # Preserve the official test set; Eval reports quarantine separately.
                elif key not in quarantined:
                    train.append(key)
            fit, validation = legacy._calibration_split(train, labels, validation_fraction=fraction, seed=seed)
            if not fit or not validation:
                raise ValueError("Shared partition requires at least two official training tasks")
            data = {"version": "calitree-partition-v1", "fit_ids": fit, "validation_ids": validation,
                    "test_ids": test, "samples": deepcopy(samples), "labels": deepcopy(labels),
                    "settings": {"validation_fraction": fraction, "seed": seed}}
            if quarantined:
                data["annotation_quarantine"] = quarantined
            data["id"] = digest(data)
            return NodeRunResult(outputs={"partition": data,
                "test_samples": {key: samples[key] for key in test}, "test_labels": {key: labels[key] for key in test}})
        except (ValueError, KeyError, TypeError) as error:
            return NodeRunResult(status="error", error=str(error))


class _NamespaceCheckpoint:
    def __init__(self, checkpoint, namespace):
        self.checkpoint, self.namespace = checkpoint, namespace
    def has(self, key): return self.checkpoint.has(self.namespace + key)
    def get(self, key): return self.checkpoint.get(self.namespace + key)
    def put(self, key, value): return self.checkpoint.put(self.namespace + key, value)


class _LazyEngine:
    """Cached stages and metrics never initialize a provider or require credentials."""
    def __init__(self, config, ctx):
        self.config, self.ctx, self.engine = config, ctx, None
        self.name, self.model = "manual:" + digest(config), config.get("model", "")
        self.temperature, self.max_tokens = config.get("temperature", 0), int(config.get("max_tokens") or 4096)
    def generate(self, *args, **kwargs):
        if self.ctx.should_stop and self.ctx.should_stop():
            raise InterruptedError("CaliTree execution stopped")
        legacy.require_live(self.ctx.allow_live, context="manual CaliTree stages")
        if self.engine is None:
            self.engine = legacy._engine_from(self.config, self.ctx)
        engine = self.engine
        # Bounded optimizer copies cap the actual provider's completion allowance.
        original = getattr(engine, "max_tokens", self.max_tokens)
        engine.max_tokens = self.max_tokens
        try: return engine.generate(*args, **kwargs)
        finally: engine.max_tokens = original


def _metrics(ids, targets, predictions):
    correct = [key for key in ids if predictions[key].get("label") == targets[key]]
    return {"n": len(ids), "accuracy": len(correct) / len(ids) if ids else 0,
            "balanced_accuracy": balanced_accuracy(ids, targets, predictions), "correct_ids": correct}


def validate_node(node):
    if node.get("version") != NODE_VERSION or not node.get("prompt", "").strip():
        raise ValueError("Invalid or unavailable CaliTree node artifact")
    if node.get("prompt_sha256") != prompt_hash(node["prompt"]):
        raise ValueError("CaliTree prompt hash mismatch")
    if (node["id"] in node.get("children", []) or node["id"] in node.get("ancestors", [])
            or not set(node.get("children", [])) <= set(node.get("ancestors", []))):
        raise ValueError("Cycle or invalid CaliTree lineage")
    if len(set(node.get("children", []))) != len(node.get("children", [])):
        raise ValueError("Duplicate CaliTree lineage children")
    scope = node.get("scope_ids") or []
    if not scope or len(set(scope)) != len(scope) or not set(node.get("served_ids", [])) <= set(scope):
        raise ValueError("Invalid CaliTree scope/assignments")
    policy = node.get("decision_sets")
    if policy:
        if policy.get("prompt_sha256") != node["prompt_sha256"] or policy.get("payload", {}).get("rubric") != node["prompt"]:
            raise ValueError("CaliTree prompt-policy binding mismatch")
    return node


COMMON_SCHEMA = {
    "initial_prompt": {"type": "text", "default": ""},
    "output_mode": {"type": "enum", "default": "raw_prompt", "options": ["raw_prompt", "decision_sets", "both"]},
    "run_until": {"type": "enum", "default": "validation", "options": list(LEAF_STAGES)},
    "optimizer_plan": {"type": "enum", "default": "textgrad", "options": list(PLANS)},
    "optimization_evaluator": {"type": "enum", "default": "raw_prompt", "options": ["raw_prompt", "decomposed"]},
    "decomposition_strategy": {"type": "enum", "default": "two_way_vision", "options": ["two_way_vision", "two_way"]},
    "max_steps": {"type": "number", "default": 3, "min": 0},
    "optimizer_token_budget": {"type": "number", "default": 60000, "min": 0},
    "gepa_python": {"type": "string", "default": ""},
}


class _ManualNode(NodeExecutor):
    category = "node_calibration"
    input_sockets = {"partition": "calitree_data", "judge_engine": "engine_config", "optimizer_engine": "engine_config"}
    output_sockets = {"node": "calitree_node", "optimized_prompt": "optimized_prompt",
                      "decision_sets": "decision_sets", "calitree_report": "calitree_report"}

    def run(self, ctx):
        try: return self._run(ctx)
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, InterruptedError) as error:
            return NodeRunResult(status="error", error=str(error))

    def _run(self, ctx):
        p = ctx.params
        partition = ctx.inputs.get("partition") or {}
        if partition.get("version") != "calitree-partition-v1" or partition.get("id") != digest({k: v for k, v in partition.items() if k != "id"}):
            raise ValueError("A valid shared CaliTree partition is required")
        merging = self.node_type == "calitree_merge"
        children = ctx.inputs.get("children") or []
        if merging:
            if len(children) < 2: raise ValueError("Merge requires at least two children")
            identities = [validate_node(child)["id"] for child in children]
            if len(set(identities)) != len(identities): raise ValueError("Duplicate merge children")
            for child in children:
                if child["partition_id"] != partition["id"]: raise ValueError("Children use mismatched partition identities")
                if ctx.node_id == child["id"] or ctx.node_id in child["ancestors"] or set(identities) & set(child["ancestors"]):
                    raise ValueError("Cycle or ancestor/descendant pair in merge children")
                for key in child["scope_ids"]:
                    if child["case_records"].get(key) != digest(partition["samples"].get(key)):
                        raise ValueError(f"Conflicting child case record: {key}")
            ids = sorted({key for child in children for key in child["scope_ids"]})
        else:
            ids = p.get("selected_ids") or []
        if not ids or len(set(ids)) != len(ids) or not set(ids) <= set(partition["fit_ids"]):
            raise ValueError("Select a nonempty, unique set of fit cases; reserved validation and test cases cannot be selected")
        _, quarantined = partition_annotations(partition["labels"])
        excluded = sorted(set(ids + partition["validation_ids"]) & set(quarantined))
        if excluded:
            raise ValueError("Uncertain annotations cannot be used for fitting or validation: " + ", ".join(excluded))
        if p.get("output_mode", "raw_prompt") not in {"raw_prompt", "decision_sets", "both"}:
            raise ValueError("Unknown output mode")
        steps = int(p.get("max_steps", 3))
        plan = p.get("optimizer_plan", "textgrad")
        if plan not in PLANS or steps < 0 or steps != p.get("max_steps", steps): raise ValueError("Invalid optimizer settings")
        if plan in {"best_of_both", "textgrad_then_gepa", "gepa_then_textgrad"} and steps < 2:
            raise ValueError("Combined optimizer plans require at least two steps")
        strategy = p.get("decomposition_strategy", "two_way_vision")
        evaluator = p.get("optimization_evaluator", "raw_prompt")
        if evaluator not in {"raw_prompt", "decomposed"}: raise ValueError("Unknown optimization evaluator")
        if strategy not in {"two_way", "two_way_vision"}: raise ValueError("Unknown decomposition strategy")
        stages = MERGE_STAGES if merging else LEAF_STAGES
        options = {"run_until": p.get("run_until", "validation"), **{key: value for key, value in ctx.execution_options.items() if value is not None}}
        reuse = {**p.get("stage_cache", {}), **options.get("reuse", {})}
        report = {"version": "calitree-report-v1", "node_id": ctx.node_id, "stages": {},
                  "scope_ids": ids, "partition_id": partition["id"], "children": [
                      {"id": c["id"], "validation_state": c["validation_state"], "has_policy": bool(c.get("decision_sets"))} for c in children],
                  "scope_overlap": sum(len(c["scope_ids"]) for c in children) - len(ids) if merging else 0}
        def progress(stage, row):
            report["stages"][stage] = row
            if ctx.progress_cb: ctx.progress_cb("calitree_stage", {"stage": stage, **row})
            if ctx.on_batch: ctx.on_batch("calitree_report", deepcopy(report))
        runner = StageRunner(stages, pins=p.get("stage_pins", {}), reuse=reuse, load=load_artifact,
            save=lambda stage, row: save_artifact(ctx.run, ctx.node_id, stage, row), checkpoint=ctx.checkpoint,
            options=options, progress=progress, should_stop=ctx.should_stop)
        for stage in runner.pins:
            missing = [earlier for earlier in stages[:stages.index(stage)] if not runner.available(earlier)]
            if missing: raise ValueError(f"Pinned {stage} requires completed predecessor artifacts: {', '.join(missing)}")
        if ctx.dry_run:
            seed = p.get("initial_prompt") or legacy._prompt("initial_rubric.txt")
            node = {"version": NODE_VERSION, "id": ctx.node_id, "prompt": seed, "prompt_sha256": prompt_hash(seed),
                "partition_id": partition["id"], "scope_ids": ids, "served_ids": ids, "children": [c["id"] for c in children],
                "ancestors": sorted({c["id"] for c in children} | {a for c in children for a in c["ancestors"]}),
                "depth": 1 + max(c["depth"] for c in children) if merging else 0, "validation_state": "candidate",
                "case_records": {key: digest(partition["samples"][key]) for key in ids}, "decision_sets": None,
                "output_mode": p.get("output_mode", "raw_prompt"), "dry_run": True}
            return NodeRunResult(outputs={"node": node, "calitree_report": report}, meta={"dry_run": True,
                "estimated_stages": list(stages[:stages.index(runner.end)+1]), "estimated_cases": len(ids) + len(partition["validation_ids"]),
                "estimated_optimizer_proposals": steps, "estimated_calls": 0 if options.get("action") == "metrics" else None})
        # A rerun's component caches must not hide required model calls. Stage artifacts
        # provide predecessor reuse; a fresh namespace bypasses all observation/judge caches.
        namespace = (options.get("execution_id") or uuid4().hex) + ":" if runner.start else ""
        runtime_ctx = replace(ctx, checkpoint=_NamespaceCheckpoint(ctx.checkpoint, namespace))
        judge_config = ctx.inputs.get("judge_engine") or {}
        optimizer_config = ctx.inputs.get("optimizer_engine") or judge_config
        runtime = legacy._CaliTreeRuntime(runtime_ctx, judge_engine=_LazyEngine(judge_config, ctx),
            optimizer_engine=_LazyEngine(optimizer_config, ctx), embedding_model="", optimizer_budget=int(p.get("optimizer_token_budget", 60000)))
        adapter = runtime.configure_modular(strategy)
        all_ids = ids + partition["validation_ids"]
        samples = {key: partition["samples"][key] for key in all_ids}
        targets = {key: legacy._target(partition["labels"][key]) for key in all_ids}
        inputs = {key: adapter.inputs(sample) for key, sample in samples.items()}
        evidence_ids = {key: adapter.evidence_identity(value[1]) for key, value in inputs.items()}
        instructions = {key: value[0] for key, value in inputs.items()}
        seed = p.get("initial_prompt") or legacy._prompt("initial_rubric.txt")
        def raw_judge(prompt, sample):
            executor = runtime.modular_executor
            runtime.modular_executor = None
            try:
                key = sample["item_id"]
                safe_sample = {**sample, "item_id": key + "::" + digest([inputs[key][0], evidence_ids[key], judge_config])}
                return runtime.judge(prompt, safe_sample)
            finally: runtime.modular_executor = executor
        judge = raw_judge if evaluator == "raw_prompt" else runtime.judge
        builder = CaliTreeBuilder(judge=judge, optimize=runtime.optimize, extract_components=lambda _: {},
            embed=lambda _: [], merge_prompts=runtime.merge, max_steps=steps,
            merge_acceptance=float(p.get("merge_acceptance", .8)), merge_generalization_floor=float(p.get("merge_generalization_floor", .8)),
            merge_regression_tolerance=float(p.get("merge_regression_tolerance", .05)), merge_validation_cap=0,
            reflect=runtime.reflect, budget_available=lambda: runtime.optimizer_completion_tokens < runtime.optimizer_budget,
            optimizer_identity=runtime.optimizer_identity(), optimizer_usage=runtime.optimizer_usage, merge_many_prompts=runtime.merge_many)
        context = BuildContext(builder._services(), builder._settings(), None, seed,
            {k: samples[k] for k in ids}, {k: targets[k] for k in ids},
            {k: samples[k] for k in partition["validation_ids"]}, {k: targets[k] for k in partition["validation_ids"]}, [],
            executor=runtime.modular_executor if evaluator == "decomposed" else None, checkpoint=runtime_ctx.checkpoint)
        def candidate(row):
            report.setdefault("optimization", {"evaluator": evaluator, "history": []})["history"].append(row)
            if ctx.on_batch: ctx.on_batch("calitree_report", deepcopy(report))
        context.services = replace(context.services, on_candidate=candidate)
        optimizer = LeafController(OptimizerPlan(plan, gepa_python=p.get("gepa_python") or None))
        opt_inputs = {"seed": seed, "scope": ids, "samples": context.samples, "targets": context.targets,
                      "evidence": {k: evidence_ids[k] for k in ids}, "settings": {key: p.get(key, schema["default"]) for key, schema in self.param_schema.items() if key not in {"run_until", "output_mode", "selected_ids"}},
                      "engines": [judge_config, optimizer_config]}
        terminal_prompt_stage = "refinement" if merging else "optimization"
        # Preflight all pins from their saved predecessor artifacts before optimization.
        pinned = runner.pins
        if any(stage != stages[0] for stage in pinned):
            saved = runner.available(terminal_prompt_stage)
            if not saved: raise ValueError("Pinned downstream stage requires its completed prompt predecessor")
            if merging and any(stage not in {"synthesis", "refinement"} for stage in pinned):
                synthesis = runner.available("synthesis")
                expected = {"children": children, "strategy": p.get("merge_strategy", "joint"), "engine": optimizer_config}
                if not synthesis or ("synthesis" not in pinned and synthesis["input_digest"] != digest(expected)):
                    raise ValueError("Synthesis inputs changed; pin synthesis or unfreeze dependent stages")
                refinement_inputs = {**opt_inputs, "seed": synthesis["data"]["prompt"] or seed, "proposal": synthesis["data"]}
                if terminal_prompt_stage not in pinned and saved["input_digest"] != digest(refinement_inputs):
                    raise ValueError("Refinement inputs changed; pin refinement or unfreeze dependent stages")
            if not merging and terminal_prompt_stage not in pinned and saved["input_digest"] != digest(opt_inputs):
                raise ValueError("Optimization inputs changed; pin optimization or unfreeze dependent stages")
            bound_prompt = saved["data"]["prompt"]
            binding = {"prompt": prompt_hash(bound_prompt), "strategy": strategy, "adapter": adapter.identity()}
            pin_bindings = {"compilation": binding, "instruction_decomposition": {**binding, "instructions": digest(instructions)}}
            compiled, planned = runner.available("compilation"), runner.available("instruction_decomposition")
            if compiled and planned:
                observation_binding = {**binding, "policy": digest(compiled["data"]), "plans": digest(planned["data"]), "evidence": digest(evidence_ids)}
                pin_bindings["evidence_checks"] = observation_binding
                observed = runner.available("evidence_checks")
                if observed:
                    pin_bindings["aggregation"] = {**observation_binding, "observations": digest(observed["data"]), "output_mode": p.get("output_mode", "raw_prompt"), "baseline": seed if merging else None}
                    aggregated = runner.available("aggregation")
                    if aggregated:
                        pin_bindings["validation"] = {"predictions": digest(aggregated["data"]), "targets": digest(targets), "scope": digest(ids),
                            "guards": [builder.merge_acceptance, builder.merge_generalization_floor, builder.merge_regression_tolerance]}
            runner.check_pins(pin_bindings)
        if "gepa" in plan or plan == "best_of_both":
            from ...core.optimization.prompt.calitree.optimization.gepa import resolve_gepa_python
            if terminal_prompt_stage not in runner.pins:
                resolve_gepa_python(p.get("gepa_python") or None)
        if ctx.progress_cb: ctx.progress_cb("calitree_progress_init", {"total": stages.index(runner.end) + 1})
        runner.usage = lambda: dict(runtime.usage)
        proposal = None
        if merging:
            merge_strategy = p.get("merge_strategy", "joint")
            if merge_strategy not in {"joint", "concatenate"}: raise ValueError("Unknown merge strategy")
            algorithm = CallbackMultiMergeAlgorithm() if merge_strategy == "joint" else ConcatenateMergeAlgorithm()
            coordinator = MergeCoordinator(algorithm, GuardedMergeAcceptance())
            child_nodes = [CaliTreeNode(c["id"], c["prompt"], c["scope_ids"], [], {}, children=c["children"], level=c["depth"]) for c in children]
            context.executor = runtime.modular_executor
            for child in children:
                context.artifacts[child["id"]] = {"policy_ref": child["prompt_sha256"]}
                if child.get("decision_sets"): runtime.modular_executor.policies[child["prompt_sha256"]] = child["decision_sets"]
            proposal = runner.run("synthesis", {"children": children, "strategy": merge_strategy, "engine": optimizer_config}, {},
                                  lambda: asdict(coordinator.propose_many(child_nodes, context)))
            prompt = proposal["prompt"] or seed
            if runner.includes("refinement"):
                # Refine using fit labels only; candidate children do not require policies.
                context.executor = runtime.modular_executor if evaluator == "decomposed" else None
                optimized = runner.run("refinement", {**opt_inputs, "seed": prompt, "proposal": proposal}, {},
                    lambda: asdict(optimizer.optimize(prompt, ids, context)))
                prompt = optimized["prompt"]
            else: optimized = {"prompt": prompt, "report": {}}
        else:
            optimized = runner.run("optimization", opt_inputs, {}, lambda: asdict(optimizer.optimize(seed, ids, context)))
            prompt = optimized["prompt"]
        report["optimization"] = {**optimized, "evaluator": evaluator}
        binding = {"prompt": prompt_hash(prompt), "strategy": strategy, "adapter": adapter.identity()}
        policy_data, plans, observations, predictions, validation = None, {}, {}, {}, None
        def collect(stage, field, operation):
            rows = {}
            for index, key in enumerate(all_ids):
                if ctx.should_stop and ctx.should_stop(): raise InterruptedError("CaliTree stage execution stopped")
                rows[key] = operation(key)
                report[field] = {"decomposed": deepcopy(rows)} if field == "predictions" else deepcopy(rows)
                report["stages"][stage] = {"state": "running", "completed": index + 1, "total": len(all_ids)}
                if ctx.on_batch: ctx.on_batch("calitree_report", deepcopy(report))
            return rows
        if runner.includes("compilation"):
            policy_data = runner.run("compilation", {"prompt": prompt, "strategy": strategy, "engine": judge_config, "adapter": adapter.identity()}, binding, lambda: {"strategy": strategy, "prompt_sha256": prompt_hash(prompt),
                "payload": adapter.export(adapter.compile(prompt)), "identity": adapter.identity()})
            if policy_data["prompt_sha256"] != prompt_hash(prompt) or policy_data["payload"].get("rubric") != prompt:
                raise ValueError("Compilation prompt-policy binding mismatch")
            policy = adapter.restore(policy_data["payload"])
        plan_binding = {**binding, "instructions": digest(instructions)}
        if runner.includes("instruction_decomposition"):
            plans = runner.run("instruction_decomposition", {"instructions": instructions, "binding": plan_binding}, plan_binding,
                lambda: collect("instruction_decomposition", "instruction_plans", lambda key: adapter.decompose(instructions[key])))
        observation_binding = {**binding, "policy": digest(policy_data), "plans": digest(plans), "evidence": digest(evidence_ids)}
        if runner.includes("evidence_checks"):
            observations = runner.run("evidence_checks", {"evidence": {key: inputs[key][1] for key in all_ids}, "evidence_identities": evidence_ids, "plans": plans, "binding": observation_binding}, observation_binding, lambda: collect("evidence_checks", "observations", lambda key: adapter.observe(policy, adapter.restore_plan(plans[key], instructions[key]), inputs[key][1])))
        aggregation_binding = {**observation_binding, "observations": digest(observations), "output_mode": p.get("output_mode", "raw_prompt"), "baseline": seed if merging else None}
        if runner.includes("aggregation"):
            def aggregate():
                rows = collect("aggregation", "predictions", lambda key: adapter.aggregate(policy, adapter.restore_plan(plans[key], instructions[key]), observations[key]))
                # Baseline and raw-prompt measurements belong to execution, so validation
                # and metric-only reruns consume saved predictions without model calls.
                raw = {key: raw_judge(prompt, samples[key]) for key in all_ids} if p.get("output_mode", "raw_prompt") != "decision_sets" else {}
                baseline_judge = raw_judge if p.get("output_mode", "raw_prompt") != "decision_sets" else runtime.judge
                baseline = ({key: (raw or rows)[key] for key in partition["validation_ids"]} if seed == prompt else
                            {key: baseline_judge(seed, samples[key]) for key in partition["validation_ids"]}) if merging else {}
                return {"decomposed": rows, "raw_prompt": raw, "baseline": baseline}
            predictions = runner.run("aggregation", {"observations": observations, "policy": policy_data, "binding": aggregation_binding}, aggregation_binding, aggregate)
        validation_binding = {"predictions": digest(predictions), "targets": digest(targets), "scope": digest(ids),
            "guards": [builder.merge_acceptance, builder.merge_generalization_floor, builder.merge_regression_tolerance]}
        if runner.includes("validation"):
            def measure():
                rows = predictions["raw_prompt"] or predictions["decomposed"]
                result = {"fit": _metrics(ids, targets, rows), "reserved_validation": _metrics(partition["validation_ids"], targets, rows),
                          "raw_prompt": _metrics(all_ids, targets, predictions["raw_prompt"]) if predictions["raw_prompt"] else None,
                          "decomposed": {"fit": _metrics(ids, targets, predictions["decomposed"]),
                                         "reserved_validation": _metrics(partition["validation_ids"], targets, predictions["decomposed"])}}
                if merging:
                    saved_judge = lambda text, sample: (predictions["baseline"] if text == seed else rows)[sample["item_id"]]
                    services = replace(context.services, judge=saved_judge, judge_many=None)
                    acceptance_context = replace(context, services=services, warm_prompt=seed)
                    # Use the parent rows for a proposal equal to its baseline too.
                    decision = coordinator.assess(OptimizationResult(prompt, result["fit"]["accuracy"], result["fit"]["correct_ids"], rows, 0), ids, acceptance_context)
                    if proposal["conflict"]: decision.accepted, decision.kind = False, "synthesis_conflict"
                    result["acceptance"] = asdict(decision)
                return result
            validation = runner.run("validation", {"predictions": predictions, "targets": targets, "scope": ids, "guards": validation_binding["guards"]}, validation_binding, measure)
        state = "candidate" if validation is None else "accepted" if not merging or validation["acceptance"]["accepted"] else "rejected"
        node = {"version": NODE_VERSION, "id": ctx.node_id, "kind": "merge" if merging else "leaf",
                "prompt": prompt, "prompt_sha256": prompt_hash(prompt), "partition_id": partition["id"],
                "scope_ids": ids, "served_ids": validation["fit"]["correct_ids"] if merging and state == "accepted" else ids,
                "correct_ids": validation["fit"]["correct_ids"] if validation else [],
                "children": [c["id"] for c in children], "ancestors": sorted({c["id"] for c in children} | {a for c in children for a in c["ancestors"]}),
                "depth": 1 + max(c["depth"] for c in children) if merging else 0,
                "case_records": {key: digest(samples[key]) for key in ids}, "decision_sets": policy_data,
                "instruction_plans": plans, "observations": observations, "predictions": predictions,
                "stages": runner.records, "validation_state": state, "validation": validation,
                "output_mode": p.get("output_mode", "raw_prompt"), "decomposition_strategy": strategy, "optimization": report["optimization"]}
        report.update(node=node, validation=validation, decision_sets=policy_data, instruction_plans=plans,
                      observations=observations, predictions=predictions, stages=runner.records)
        outputs = {"node": node, "calitree_report": report}
        if node["output_mode"] in {"raw_prompt", "both"}: outputs["optimized_prompt"] = prompt
        if node["output_mode"] in {"decision_sets", "both"} and policy_data: outputs["decision_sets"] = {**policy_data, "instruction_plans": plans, "observations": observations, "predictions": predictions}
        return NodeRunResult(outputs=outputs, meta={"artifact_run_id": ctx.run.run_dir.name.removesuffix("-exps"), "usage": runtime.usage, "output_readiness": {key: key in outputs for key in self.output_sockets}})


@register
class CaliTreeLeafNodeExecutor(_ManualNode):
    node_type = "calitree_leaf"
    param_schema = {**COMMON_SCHEMA, "selected_ids": {"type": "list[string]", "default": []}}


@register
class CaliTreeMergeNodeExecutor(_ManualNode):
    node_type = "calitree_merge"
    input_sockets = {**_ManualNode.input_sockets, "children": "calitree_node"}
    multi_input_sockets = frozenset({"children"})
    param_schema = {**COMMON_SCHEMA, "run_until": {"type": "enum", "default": "validation", "options": list(MERGE_STAGES)},
        "merge_strategy": {"type": "enum", "default": "joint", "options": ["joint", "concatenate"]},
        "merge_acceptance": {"type": "number", "default": .8, "min": 0, "max": 1},
        "merge_generalization_floor": {"type": "number", "default": .8, "min": 0, "max": 1},
        "merge_regression_tolerance": {"type": "number", "default": .05, "min": 0, "max": 1}}


def judge_manual_node(ctx):
    try:
        node = validate_node(ctx.inputs["calitree_node"])
        samples = ctx.inputs.get("samples")
        if samples is None or not ctx.inputs.get("judge_engine"): raise ValueError("Manual judging requires samples and judge_engine")
        if ctx.inputs.get("prompt_tree") is not None: raise ValueError("Connect exactly one of prompt_tree or calitree_node")
        use_policy = node["output_mode"] == "decision_sets"
        if use_policy and not node.get("decision_sets") and not ctx.dry_run: raise ValueError("Decision sets are unavailable; run compilation or publish raw_prompt")
        if ctx.dry_run: return NodeRunResult(outputs={"judge_result": {}}, meta={"dry_run": True, "estimated_calls": len(samples)})
        runtime = legacy._CaliTreeRuntime(ctx, judge_engine=_LazyEngine(ctx.inputs["judge_engine"], ctx),
            optimizer_engine=_LazyEngine(ctx.inputs["judge_engine"], ctx), embedding_model="", optimizer_budget=0)
        if use_policy:
            adapter = runtime.configure_modular(node["decision_sets"]["strategy"])
            runtime.modular_executor.preflight(samples)
            runtime.modular_executor.load_policies({node["prompt_sha256"]: node["decision_sets"]}, strategy=adapter.name)
        if not use_policy:
            # Manual raw inference binds checkpoints to current evidence bytes too.
            adapter = runtime.configure_modular(node.get("decomposition_strategy", "two_way_vision"))
            identities = {}
            for key, sample in samples.items():
                instruction, evidence = adapter.inputs(sample)
                identities[key] = digest([instruction, adapter.evidence_identity(evidence)])
            runtime.modular_executor = None
            rows = {key: runtime.judge(node["prompt"], {**sample, "item_id": key + "::" + identities[key]}) for key, sample in samples.items()}
        else:
            rows = runtime.judge_many(node["prompt"], samples)
        return NodeRunResult(outputs={"judge_result": {key: {"calitree": {**row, "node_id": node["id"], "validation_state": node["validation_state"]}} for key, row in rows.items()}}, meta={"usage": runtime.usage, "direct_node": node["id"]})
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        return NodeRunResult(status="error", error=str(error))
