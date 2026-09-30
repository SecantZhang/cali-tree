"""Two-way decomposition implementations and their optional research extensions.

Rubric policy and instruction intent are compiled separately before judging.
DecompositionTwoWay handles structured evidence; DecompositionTwoWayVision
handles image pairs. Research subclasses retain their explicit opt-in behavior.
All two-way implementations live here. Import their classes from this module or
the decomposition package. Unrelated decomposition algorithms can implement
DecompositionAlgorithm in their own modules.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any, Optional

from critical.checkpoint import CheckpointStore
from critical.core.judge.parse import parse_json_object

from .components import ModelConditionEvaluator, ModelInstructionCompiler, ModelRubricCompiler
from .decomposition_base import ConditionEvaluator, DecompositionAlgorithm, InstructionCompiler, RubricCompiler
from .executable_policy import EXECUTABLE_VERSION, ExecutableRubric, parse_executable_policy
from .models import ConditionResult, DecompositionResult, InstructionPlan, parse_plan
from .policy import CompiledPolicy
from .prompts import DecompositionTemplates, load_templates
from .vision_models import (
    SemanticInstruction, SemanticRubric, VISION_VERSION, nonempty_text,
    parse_finding, parse_preservation, parse_semantic_instruction, parse_semantic_rubric,
)
from .visual_calibration import VisualReferenceBank, parse_visual_grade, visual_grade_input

__all__ = [
    "DecompositionTwoWay", "DecompositionTwoWayVision", "DecompositionTwoWayGrounded",
    "DecompositionTwoWayIntent", "DecompositionTwoWayInventory", "DecompositionTwoWayExecutable",
    "DecompositionTwoWayCalibratedVision", "parse_edit_scope", "parse_image_inventory",
    "FrozenCriteriaExecutor",
]


# Structured evidence

class DecompositionTwoWay(DecompositionAlgorithm[CompiledPolicy, InstructionPlan]):
    def __init__(
        self, engine: Any = None, *, rubric_compiler: Optional[RubricCompiler] = None,
        instruction_compiler: Optional[InstructionCompiler] = None,
        condition_evaluator: Optional[ConditionEvaluator] = None,
        templates: Optional[DecompositionTemplates] = None,
        checkpoint: Optional[CheckpointStore] = None, concurrency: int = 4,
        schema_retries: int = 1,
    ) -> None:
        if type(concurrency) is not int or concurrency < 1:
            raise ValueError("Decomposition concurrency must be a positive integer")
        self.concurrency = concurrency
        selected_templates = templates if templates is not None else load_templates()
        options = {"templates": selected_templates, "checkpoint": checkpoint, "schema_retries": schema_retries}
        self.rubric_compiler = rubric_compiler if rubric_compiler is not None else ModelRubricCompiler(engine, **options)
        self.instruction_compiler = instruction_compiler if instruction_compiler is not None else ModelInstructionCompiler(engine, **options)
        self.condition_evaluator = condition_evaluator if condition_evaluator is not None else ModelConditionEvaluator(engine, **options)

    def compile(self, rubric: str) -> CompiledPolicy:
        return self.rubric_compiler.compile(rubric)

    def decompose(self, instruction: str) -> InstructionPlan:
        return self.instruction_compiler.decompose(instruction)

    def evaluate(
        self, policy: CompiledPolicy, instruction: str, evidence: dict[str, Any],
    ) -> DecompositionResult:
        plan = self.decompose(instruction)
        return self.evaluate_many(policy, {"case": plan}, {"case": evidence})["case"]

    def evaluate_many(self, policy, plans, evidence):
        return {key: self.aggregate(policy, row) for key, row in
                self.observe_many(policy, plans, evidence).items()}

    def observe(self, policy, plan, evidence):
        return self.observe_many(policy, {"case": plan}, {"case": evidence})["case"]

    def aggregate(self, policy, observations):
        plan = parse_plan(observations["plan"])
        edits, guards = observations["edits"], observations["guards"]
        for rows, conditions in ((edits, policy.edits(plan)), (guards, policy.guards(plan))):
            if not isinstance(rows, list) or [row["condition"] for row in rows] != [c.to_dict() for c in conditions]:
                raise ValueError("Observation conditions differ from compiled policy/plan")
            for row in rows:
                ConditionResult.from_dict({key: row[key] for key in ("status", "rationale")})
        label, decision = policy.decide(edits, guards, plan)
        trace = {"plan": plan.to_dict(), "edits": edits, "guards": guards,
                 "label": label, "decision": decision}
        return DecompositionResult(label, json.dumps(trace, sort_keys=True), trace)

    def observe_many(
        self, policy: CompiledPolicy, plans: dict[str, InstructionPlan],
        evidence: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Evaluate supplied plans, allowing persisted/reference intent to be used.

        Identical checks are deduplicated within a call using the evaluator's
        evidence-aware key. Model-backed components additionally memoize only
        valid outputs in their run-scoped checkpoint.
        """
        if not isinstance(plans, dict) or not isinstance(evidence, dict) or set(plans) != set(evidence):
            raise ValueError("Plans and evidence must have exactly matching case IDs")
        if any(not isinstance(plan, InstructionPlan) for plan in plans.values()):
            raise ValueError("Each plan must be an InstructionPlan")
        if any(not isinstance(values, dict) for values in evidence.values()):
            raise ValueError("Each evidence record must be a mapping")
        plans = {key: parse_plan(plan.to_dict()) for key, plan in plans.items()}
        edits = {key: policy.edits(plan) for key, plan in plans.items()}
        guards = {key: policy.guards(plan) for key, plan in plans.items()}
        requests = {}
        for key in plans:
            for condition in (*edits[key], *guards[key]):
                request = self.condition_evaluator.cache_key(condition, evidence[key])
                requests.setdefault(request, (condition, evidence[key]))

        def check(request):
            condition, observed = requests[request]
            result = self.condition_evaluator.evaluate(condition, observed)
            if not isinstance(result, ConditionResult):
                raise ValueError("Condition evaluator must return ConditionResult")
            return request, result

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            results = dict(executor.map(check, sorted(requests)))
        output = {}
        for key, plan in plans.items():
            def rows(conditions):
                return [{"condition": condition.to_dict(), **results[
                    self.condition_evaluator.cache_key(condition, evidence[key])
                ].to_dict()} for condition in conditions]
            edit_rows, guard_rows = rows(edits[key]), rows(guards[key])
            output[key] = {"plan": plan.to_dict(), "edits": edit_rows, "guards": guard_rows}
        return output

    @staticmethod
    def _sample(sample: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not isinstance(sample, dict):
            raise ValueError("Decomposition sample must be a mapping")
        instruction = sample.get("instruction")
        if instruction is None:
            user_input = sample.get("input") or {}
            if not isinstance(user_input, dict):
                raise ValueError("Sample input must be a mapping")
            instruction = user_input.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Two-way judging requires a natural-language instruction")
        evidence = sample.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError("Two-way judging requires structured evidence; image evaluation needs a separate adapter")
        return instruction, evidence

    def judge(self, prompt: str, sample: dict[str, Any]) -> dict[str, str]:
        return self.judge_many(prompt, {"case": sample})["case"]

    def judge_many(
        self, prompt: str, samples: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        # Validate input boundaries before any billable compilation call.
        inputs = {key: self._sample(sample) for key, sample in samples.items()}
        if not inputs:
            return {}
        policy = self.compile(prompt)
        plans = {key: self.decompose(instruction) for key, (instruction, _) in inputs.items()}
        evidence = {key: values for key, (_, values) in inputs.items()}
        return {key: result.judgment() for key, result in self.evaluate_many(policy, plans, evidence).items()}


# Image-pair evidence

class DecompositionTwoWayVision(DecompositionAlgorithm[SemanticRubric, SemanticInstruction]):
    def __init__(self, engine, *, vision_engine=None, checkpoint: CheckpointStore | None = None,
                 concurrency: int = 4, schema_retries: int = 1,
                 review: bool = False,
                 resolve_disagreements: bool = False,
                 template_version: str = "calitree_decomposition_vision_v1"):
        if engine is None or not callable(getattr(engine, "generate", None)):
            raise ValueError("An engine with generate() is required")
        if type(concurrency) is not int or concurrency < 1 or type(schema_retries) is not int or schema_retries not in {0, 1}:
            raise ValueError("Invalid concurrency/schema_retries")
        if not isinstance(template_version, str) or not template_version.isidentifier():
            raise ValueError("Invalid template version")
        directory = files("critical.core.prompts").joinpath("templates", template_version)
        if type(review) is not bool or type(resolve_disagreements) is not bool:
            raise ValueError("review/resolve_disagreements must be boolean")
        stages = ["compile_rubric", "decompose_instruction", "check_condition", "check_preservation", "aggregate"]
        if review:
            stages += ["audit_instruction", "review_observations"]
        # Public resolution is also available for controlled ablations reusing
        # frozen independent judgments, without enabling it in evaluate().
        stages += ["resolve_disagreement"]
        self.templates = {stage: directory.joinpath(stage + ".txt").read_text(encoding="utf-8") for stage in stages}
        self.engine, self.vision_engine = engine, vision_engine or engine
        self.review = review
        self.resolve_disagreements = resolve_disagreements
        self.checkpoint, self.concurrency, self.schema_retries = checkpoint, concurrency, schema_retries
        self._cache, self._locks, self._registry_lock = {}, {}, Lock()
        self.calls = []

    def _request(self, stage, payload, parse, *, media=None, media_hashes=None):
        engine = self.vision_engine if media else self.engine
        identity = {"version": VISION_VERSION, "stage": stage, "template": self.templates[stage],
                    "model": getattr(engine, "model", None), "engine": getattr(engine, "name", None),
                    "temperature": getattr(engine, "temperature", None), "max_tokens": getattr(engine, "max_tokens", None),
                    "payload": payload, "media": media_hashes}
        key = "twoway-vision:" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with self._registry_lock:
            lock = self._locks.setdefault(key, Lock())
        with lock:
            if key in self._cache:
                return deepcopy(self._cache[key])
            if self.checkpoint is not None and self.checkpoint.has(key):
                result = parse(self.checkpoint.get(key))
                self._cache[key] = result
                return deepcopy(result)
            user = deepcopy(payload)
            for attempt in range(self.schema_retries + 1):
                kwargs = {"system": self.templates[stage]}
                if media:
                    kwargs["media_inputs"] = media
                response = engine.generate(json.dumps(user, ensure_ascii=False), **kwargs)
                entry = {"stage": stage, "key": key, "attempt": attempt, "input": user,
                         "media_hashes": media_hashes, "response": response}
                with self._registry_lock:
                    self.calls.append(entry)
                try:
                    raw = parse_json_object(str(response.get("content") or ""))
                    result = parse(raw)
                except ValueError as error:
                    entry["validation_error"] = str(error)
                    if attempt == self.schema_retries:
                        raise
                    user = {"input": payload, "invalid_response": response.get("content"),
                            "validation_error": str(error), "request": "Repair only the output schema; retain the task's meaning and observations."}
                    continue
                self._cache[key] = result
                if self.checkpoint is not None:
                    # Store raw parsed responses, so the same strict validator
                    # is executed on resumed artifacts, not only fresh calls.
                    self.checkpoint.put(key, raw)
                return deepcopy(result)
        raise AssertionError("No result")

    def compile(self, rubric: str) -> SemanticRubric:
        if not isinstance(rubric, str) or not rubric.strip():
            raise ValueError("Rubric must be nonempty text")
        payload = {"rubric_lines": [{"line": i, "text": line} for i, line in enumerate(rubric.splitlines(), 1) if line.strip()]}
        return self._request("compile_rubric", payload, lambda value: parse_semantic_rubric(value, rubric))

    def decompose(self, instruction: str) -> SemanticInstruction:
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Instruction must be nonempty text")
        parse = lambda value: parse_semantic_instruction(value, instruction)
        plan = self._request("decompose_instruction", {"instruction": instruction}, parse)
        if self.review:
            plan = self._request("audit_instruction", plan.to_dict(), parse)
        return plan

    @staticmethod
    def _media(evidence):
        if not isinstance(evidence, dict):
            raise ValueError("Vision evidence must be a mapping")
        paths = [evidence.get("source_image"), evidence.get("edited_image")]
        if any(not isinstance(path, (str, Path)) for path in paths):
            raise ValueError("Vision evidence requires source_image and edited_image paths")
        resolved = [Path(path).expanduser().resolve() for path in paths]
        digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in resolved]
        return [{"type": "image", "path": str(path)} for path in resolved], digests

    def _source_context(self, plan: SemanticInstruction, media, digests):
        """Strategies can bind targets in SOURCE before inspecting EDITED."""
        return None

    def observe(self, plan: SemanticInstruction, evidence: dict[str, Any]):
        plan = parse_semantic_instruction({"conditions": plan.to_dict()["conditions"]}, plan.instruction)
        media, digests = self._media(evidence)
        grounding = self._source_context(plan, media, digests)

        def check(condition):
            payload = {"instruction": plan.instruction, "condition": condition.to_dict()}
            if grounding is not None:
                payload["source_grounding"] = next(row for row in grounding["groundings"] if row["condition_id"] == condition.id)
                payload["source_scene"] = grounding["scene"]
            result = self._request("check_condition", payload,
                                   parse_finding, media=media, media_hashes=digests)
            return {"condition": condition.to_dict(), **result}

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            requested = list(executor.map(check, plan.conditions))
        preservation_payload = {"instruction": plan.instruction}
        if grounding is not None:
            preservation_payload["source_grounding"] = grounding
        preservation = self._request("check_preservation", preservation_payload,
                                     parse_preservation, media=media, media_hashes=digests)
        initial = {"requested": requested, "preservation": preservation}
        if self.review:
            def parse_review(value):
                if not isinstance(value, dict) or set(value) != {"requested", "preservation"}:
                    raise ValueError("Invalid observation review")
                rows = value["requested"]
                if not isinstance(rows, list) or len(rows) != len(plan.conditions):
                    raise ValueError("Review must retain every requested condition")
                normalized = []
                for row, condition in zip(rows, plan.conditions):
                    if not isinstance(row, dict) or row.get("condition_id") != condition.id:
                        raise ValueError("Review must retain condition IDs in order")
                    finding = parse_finding({key: item for key, item in row.items() if key != "condition_id"})
                    normalized.append({"condition": condition.to_dict(), **finding})
                parse_preservation(value["preservation"])
                return {"requested": normalized, "preservation": deepcopy(value["preservation"])}
            reviewed = self._request("review_observations", {"instruction": plan.instruction, **initial},
                                     parse_review, media=media, media_hashes=digests)
            requested, preservation = reviewed["requested"], reviewed["preservation"]
        return {"instruction": plan.instruction, "requested": requested, "preservation": preservation,
                "image_sha256": digests, **({"initial_observations": initial} if self.review else {}),
                **({"source_grounding": grounding} if grounding is not None else {})}

    def _aggregation_context(self, observations: dict[str, Any]) -> dict[str, Any]:
        """Validated additional evidence supplied by an observation strategy."""
        return {}

    def aggregate(self, policy: SemanticRubric, observations: dict[str, Any]) -> DecompositionResult:
        policy = SemanticRubric.from_dict(policy.to_dict())
        # Validate supplied observations as well as model-produced ones.
        plan = parse_semantic_instruction({"conditions": [row["condition"] for row in observations["requested"]]}, observations["instruction"])
        for row in observations["requested"]:
            parse_finding({key: value for key, value in row.items() if key != "condition"})
        parse_preservation(observations["preservation"])
        payload = {"rubric_units": deepcopy(list(policy.units)),
                   "instruction": plan.instruction, "requested": deepcopy(observations["requested"]),
                   "preservation": deepcopy(observations["preservation"])}
        if "source_grounding" in observations:
            payload["source_grounding"] = deepcopy(observations["source_grounding"])
        additional = self._aggregation_context(observations)
        if not isinstance(additional, dict) or set(additional) & set(payload):
            raise ValueError("Additional aggregation evidence cannot replace reserved fields")
        payload.update(deepcopy(additional))

        def parse(value):
            if not isinstance(value, dict) or set(value) != {"label", "rationale", "condition_ids", "rubric_unit_ids"} or value["label"] not in {"no", "partial", "yes"}:
                raise ValueError("Invalid aggregated judgment")
            if not isinstance(value["rationale"], str) or not value["rationale"].strip():
                raise ValueError("Missing aggregation rationale")
            for name, allowed in (("condition_ids", {c.id for c in plan.conditions}),
                                  ("rubric_unit_ids", {u["id"] for u in policy.units})):
                ids = value[name]
                if not isinstance(ids, list) or any(not isinstance(x, str) or x not in allowed for x in ids) or len(ids) != len(set(ids)):
                    raise ValueError("Invalid evidence/rubric citation IDs")
                if name == "rubric_unit_ids" and not ids:
                    raise ValueError("A rubric citation is required")
            return deepcopy(value)

        decision = self._request("aggregate", payload, parse)
        trace = {"version": VISION_VERSION, "rubric": policy.to_dict(), "plan": plan.to_dict(),
                 "observations": deepcopy(observations), "decision": decision}
        return DecompositionResult(decision["label"], decision["rationale"], trace)

    def evaluate(self, policy: SemanticRubric, instruction: str, evidence: dict[str, Any]) -> DecompositionResult:
        result = self.aggregate(policy, self.observe(self.decompose(instruction), evidence))
        if not self.resolve_disagreements:
            return result
        media, digests = self._media(evidence)
        response = self.vision_engine.generate(
            f"Instruction: {instruction}\nThe first image is SOURCE; the second is EDITED.",
            media_inputs=media, system=policy.rubric)
        with self._registry_lock:
            self.calls.append({"stage": "holistic_judgment", "input": {"instruction": instruction},
                               "media_hashes": digests, "response": response})
        holistic = parse_json_object(str(response.get("content") or ""))
        return self.resolve(policy, result, holistic, evidence)

    def resolve(self, policy: SemanticRubric, result: DecompositionResult,
                holistic: dict[str, Any], evidence: dict[str, Any]) -> DecompositionResult:
        """Resolve with images; supplied candidates must be independent predictions.

        This method does not accept annotation fields. A frozen real-model
        candidate can be reused to isolate resolution from resampling effects.
        """
        policy = SemanticRubric.from_dict(policy.to_dict())
        if not isinstance(holistic, dict) or holistic.get("label") not in {"no", "partial", "yes"} or not isinstance(holistic.get("rationale"), str):
            raise ValueError("Invalid holistic model judgment")
        if result.trace.get("rubric") != policy.to_dict():
            raise ValueError("Resolution policy must match the decomposed judgment")
        trace = deepcopy(result.trace)
        trace["holistic_judgment"] = {key: holistic[key] for key in ("label", "rationale")}
        media, digests = self._media(evidence)
        observations = result.trace["observations"]
        if observations["image_sha256"] != digests:
            raise ValueError("Resolution images must match the observed pair")
        if result.label == holistic["label"]:
            trace["resolution"] = {"invoked": False, "reason": "Independent predictions agree"}
            return DecompositionResult(result.label, result.rationale, trace)
        payload = {"rubric_units": deepcopy(list(policy.units)), "instruction": observations["instruction"],
                   "requested": observations["requested"], "preservation": observations["preservation"],
                   "holistic_judgment": trace["holistic_judgment"],
                   "decomposed_judgment": result.judgment()}

        def parse(value):
            if not isinstance(value, dict) or set(value) != {"label", "rationale", "condition_ids", "rubric_unit_ids"} or value["label"] not in {"no", "partial", "yes"}:
                raise ValueError("Invalid resolution judgment")
            if not isinstance(value["rationale"], str) or not value["rationale"].strip():
                raise ValueError("Resolution rationale required")
            for name, allowed in (("condition_ids", {c["id"] for c in result.trace["plan"]["conditions"]}),
                                  ("rubric_unit_ids", {u["id"] for u in policy.units})):
                ids = value[name]
                if not isinstance(ids, list) or any(not isinstance(x, str) or x not in allowed for x in ids) or len(ids) != len(set(ids)) or (name == "rubric_unit_ids" and not ids):
                    raise ValueError("Invalid resolution citation IDs")
            return deepcopy(value)

        decision = self._request("resolve_disagreement", payload, parse, media=media, media_hashes=digests)
        trace["resolution"] = {"invoked": True, **decision}
        return DecompositionResult(decision["label"], decision["rationale"], trace)

    def judge(self, prompt: str, sample: dict[str, Any]) -> dict[str, str]:
        if not isinstance(sample, dict):
            raise ValueError("Sample must be a mapping")
        user_input = sample.get("input") or {}
        if not isinstance(user_input, dict):
            raise ValueError("Sample input must be a mapping")
        instruction = sample.get("instruction") or user_input.get("instruction")
        evidence = sample.get("evidence")
        if evidence is None:
            images = sample.get("images")
            if images is None:
                output = sample.get("output") or {}
                if not isinstance(output, dict):
                    raise ValueError("Sample output must be a mapping")
                # Native AuroraBenchLoader sample contract. Metadata and
                # separately loaded annotations are deliberately not forwarded.
                images = [user_input.get("source_image_path"), output.get("edited_image_path")]
            if not isinstance(images, (list, tuple)) or len(images) != 2:
                raise ValueError("Sample requires exactly two images in SOURCE, EDITED order")
            evidence = dict(zip(("source_image", "edited_image"), images))
        self._media(evidence)  # Validate before billable work.
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Sample requires an instruction")
        return self.evaluate(self.compile(prompt), instruction, evidence).judgment()


# Experimental source grounding

class DecompositionTwoWayGrounded(DecompositionTwoWayVision):
    def __init__(self, engine, **kwargs):
        super().__init__(engine, **kwargs)
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_grounded_v1")
        for stage in ("ground_source", "check_condition"):
            self.templates[stage] = directory.joinpath(stage + ".txt").read_text(encoding="utf-8")
        self.templates["decompose_instruction"] += (
            "\nFor source traceability, set source_phrase on EVERY condition to the "
            "ENTIRE original instruction, copied verbatim. Split the requirements "
            "individually but keep that full source quotation on each. Do not "
            "paraphrase the quotation or omit introductory words.\n"
        )

    def _source_context(self, plan, media, digests):
        def parse(value):
            if not isinstance(value, dict) or set(value) != {"scene", "groundings"}:
                raise ValueError("Invalid source grounding report")
            nonempty_text(value["scene"], "Source scene")
            rows = value["groundings"]
            if not isinstance(rows, list) or len(rows) != len(plan.conditions):
                raise ValueError("Grounding must retain each requested condition")
            for row, condition in zip(rows, plan.conditions):
                if not isinstance(row, dict) or set(row) != {"condition_id", "target_description", "reference_description", "source_state", "visibility"}:
                    raise ValueError("Malformed source grounding")
                if row["condition_id"] != condition.id:
                    raise ValueError("Grounding IDs must match conditions in order")
                if not isinstance(row["visibility"], str) or row["visibility"] not in {"clear", "ambiguous", "absent"}:
                    raise ValueError("Invalid source target visibility")
                for key in ("target_description", "source_state"):
                    nonempty_text(row[key], key)
                if row["reference_description"] is not None:
                    nonempty_text(row["reference_description"], "Reference description")
            return deepcopy(value)

        return self._request("ground_source", plan.to_dict(), parse,
                             media=media[:1], media_hashes=digests[:1])


# Experimental instruction intent

def parse_edit_scope(value, instruction):
    if not isinstance(value, dict) or set(value) != {"operations", "ambiguities"}:
        raise ValueError("Malformed edit scope")
    operations = value["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
        raise ValueError("Expected 1-12 edit operations")
    seen = set()
    for operation in operations:
        fields = {"id", "action", "target", "selectors", "quantity", "requested_delta", "permitted_effects", "source_phrase"}
        if not isinstance(operation, dict) or set(operation) != fields:
            raise ValueError("Malformed edit operation")
        identifier = operation["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", identifier) or identifier in seen:
            raise ValueError("Invalid or duplicate operation ID")
        seen.add(identifier)
        for field in ("action", "target", "requested_delta"):
            nonempty_text(operation[field], field)
        quantity = operation["quantity"]
        if quantity is not None and (type(quantity) is not int or quantity < 1):
            raise ValueError("Quantity must be an explicit positive count or null")
        for field in ("selectors", "permitted_effects"):
            rows = operation[field]
            if not isinstance(rows, list) or len(rows) > 12 or any(not isinstance(row, str) or not row.strip() for row in rows):
                raise ValueError("Invalid edit selectors/effects")
        if operation["source_phrase"] != instruction:
            raise ValueError("Edit operation must quote the full instruction verbatim")
    ambiguities = value["ambiguities"]
    if not isinstance(ambiguities, list) or len(ambiguities) > 12 or any(not isinstance(row, str) or not row.strip() for row in ambiguities):
        raise ValueError("Invalid instruction ambiguities")
    return deepcopy(value)


class DecompositionTwoWayIntent(DecompositionTwoWayGrounded):
    """Experimental source-grounded strategy with instruction-only intent scope.

    A descriptor such as 'with feathers' identifies objects; it is not itself
    permission to replace a requested object removal with attribute removal.
    Scope is a model-generated interpretation, not evidence of edit success.
    """

    def __init__(self, engine, **kwargs):
        if kwargs.get("review") or kwargs.get("resolve_disagreements"):
            raise ValueError("Intent scope has not been validated with review/resolution")
        super().__init__(engine, **kwargs)
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_intent_v1")
        for stage in ("parse_edit_scope", "decompose_instruction", "check_condition", "check_preservation"):
            self.templates[stage] = directory.joinpath(stage + ".txt").read_text(encoding="utf-8")

    def scope(self, instruction):
        nonempty_text(instruction, "Instruction")
        return self._request("parse_edit_scope", {"instruction": instruction},
                             lambda value: parse_edit_scope(value, instruction))

    def decompose(self, instruction):
        scope = self.scope(instruction)
        return self._request("decompose_instruction", {"instruction": instruction, "edit_scope": scope},
                             lambda value: parse_semantic_instruction(value, instruction))

    def _source_context(self, plan, media, digests):
        scope = self.scope(plan.instruction)
        grounding = super()._source_context(plan, media, digests)
        # Both downstream vision stages and the original rubric aggregator
        # receive the same interpretation. No sample metadata enters this path.
        grounding["edit_scope"] = scope
        for row in grounding["groundings"]:
            row["edit_scope"] = deepcopy(scope)
        return grounding


# Experimental image inventory

def parse_image_inventory(value):
    if not isinstance(value, dict) or set(value) != {"scene", "objects"}:
        raise ValueError("Malformed image inventory")
    nonempty_text(value["scene"], "Inventory scene")
    rows = value["objects"]
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("Expected at most 24 inventory groups")
    seen = set()
    for row in rows:
        fields = {"id", "name", "description", "location", "count", "alternatives", "visibility"}
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Malformed inventory object")
        identifier = row["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", identifier) or identifier in seen:
            raise ValueError("Invalid or duplicate inventory ID")
        seen.add(identifier)
        for field in ("name", "description", "location"):
            nonempty_text(row[field], field)
        if row["count"] is not None and (type(row["count"]) is not int or row["count"] < 1):
            raise ValueError("Inventory count must be positive or unknown")
        if not isinstance(row["visibility"], str) or row["visibility"] not in {"clear", "uncertain"}:
            raise ValueError("Invalid inventory visibility")
        alternatives = row["alternatives"]
        if not isinstance(alternatives, list) or len(alternatives) > 8 or any(not isinstance(x, str) or not x.strip() for x in alternatives):
            raise ValueError("Invalid alternative object identifications")
    return deepcopy(value)


class DecompositionTwoWayInventory(DecompositionTwoWayIntent):
    """Experimental: captions are independent hypotheses, never ground truth.

    Identical image contents can share inventory work within a run, regardless
    of edit instruction. Source target grounding receives only SOURCE's blind
    inventory. EDITED's inventory is generated afterwards and used for comparison.
    """

    def __init__(self, engine, **kwargs):
        super().__init__(engine, **kwargs)
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_inventory_v1")
        self.templates["inventory_image"] = directory.joinpath("inventory_image.txt").read_text(encoding="utf-8")
        for stage in ("ground_source", "check_condition", "check_preservation", "aggregate"):
            self.templates[stage] += "\n\n" + directory.joinpath(stage + ".txt").read_text(encoding="utf-8")

    def _inventory(self, media, digests):
        # The role of the image, request, rubric, and all sample metadata are
        # deliberately excluded. The same image yields the same cache key.
        return super()._request("inventory_image", {}, parse_image_inventory,
                                media=media, media_hashes=digests)

    def _request(self, stage, payload, parse, *, media=None, media_hashes=None):
        if stage == "ground_source":
            if not media or len(media) != 1 or not media_hashes or len(media_hashes) != 1:
                raise ValueError("Source grounding must receive SOURCE only")
            payload = {**payload, "source_inventory": self._inventory(media, media_hashes)}
        elif stage in {"check_condition", "check_preservation"}:
            if not media or len(media) != 2 or not media_hashes or len(media_hashes) != 2:
                raise ValueError("Image comparison must receive SOURCE and EDITED")
            inventories = {role: self._inventory(media[i:i+1], media_hashes[i:i+1])
                           for i, role in enumerate(("source", "edited"))}
            payload = {**payload, "image_inventory": inventories}
        return super()._request(stage, payload, parse, media=media, media_hashes=media_hashes)

    def observe(self, plan, evidence):
        observations = super().observe(plan, evidence)
        media, digests = self._media(evidence)
        if digests != observations["image_sha256"]:
            raise ValueError("Image contents changed during inventory observation")
        observations["image_inventory"] = {role: self._inventory(media[i:i+1], digests[i:i+1])
                                           for i, role in enumerate(("source", "edited"))}
        return observations

    def _aggregation_context(self, observations):
        value = observations.get("image_inventory")
        if not isinstance(value, dict) or set(value) != {"source", "edited"}:
            raise ValueError("Both image inventories are required for aggregation")
        return {"image_inventory": {role: parse_image_inventory(value[role]) for role in ("source", "edited")}}


# Experimental executable aggregation

class DecompositionTwoWayExecutable(DecompositionTwoWayGrounded):
    """Experimental: predicates are generated from the prompt, never labels.

    Each predicate is independently checked against the recorded observations.
    A deterministic interpreter executes the compiled precedence afterwards.
    No generic hand-written mapping from fulfillment to labels is installed.
    """

    def __init__(self, engine, **kwargs):
        if kwargs.get("resolve_disagreements"):
            raise ValueError("Executable decisions do not support holistic resolution")
        super().__init__(engine, **kwargs)
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_executable_v1")
        for stage in ("compile_execution", "check_predicate"):
            self.templates[stage] = directory.joinpath(stage + ".txt").read_text(encoding="utf-8")

    def compile(self, rubric):
        source = super().compile(rubric)
        payload = {"rubric_units": deepcopy(list(source.units)),
                   "required_rubric_unit_ids": [u["id"] for u in source.units if u["kind"] in {"decision", "exception"}]}
        return self._request("compile_execution", payload,
                             lambda value: parse_executable_policy(value, source))

    def aggregate(self, policy: ExecutableRubric, observations):
        policy = ExecutableRubric.from_dict(policy.to_dict())
        plan = parse_semantic_instruction({"conditions": [r["condition"] for r in observations["requested"]]}, observations["instruction"])
        for row in observations["requested"]:
            parse_finding({key: value for key, value in row.items() if key != "condition"})
        parse_preservation(observations["preservation"])
        condition_ids = {c.id for c in plan.conditions}
        facts = {"instruction": plan.instruction, "requested": deepcopy(observations["requested"]),
                 "preservation": deepcopy(observations["preservation"])}
        if "source_grounding" in observations:
            facts["source_grounding"] = deepcopy(observations["source_grounding"])
        source_units = {u["id"]: u for u in policy.source.units}

        def check(predicate):
            def parse(value):
                if not isinstance(value, dict) or set(value) != {"value", "rationale", "condition_ids", "uses_preservation"}:
                    raise ValueError("Malformed execution finding")
                if not isinstance(value["value"], str) or value["value"] not in {"true", "false", "unknown"}:
                    raise ValueError("Invalid execution truth value")
                nonempty_text(value["rationale"], "Predicate rationale")
                ids = value["condition_ids"]
                if not isinstance(ids, list) or any(not isinstance(x, str) or x not in condition_ids for x in ids) or len(set(ids)) != len(ids):
                    raise ValueError("Invalid execution condition citations")
                if type(value["uses_preservation"]) is not bool or (value["value"] != "unknown" and not ids and not value["uses_preservation"]):
                    raise ValueError("Predicate finding requires observation evidence")
                return deepcopy(value)
            payload = {"question": predicate["question"],
                       "criterion_sources": [source_units[key] for key in predicate["rubric_unit_ids"]],
                       "observations": facts}
            return predicate["id"], self._request("check_predicate", payload, parse)

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            findings = dict(executor.map(check, policy.program["predicates"]))
        values = {key: {"true": True, "false": False, "unknown": None}[row["value"]] for key, row in findings.items()}
        execution = policy.decide(values)
        rationale = f"Compiled rule {execution['rule_id'] or 'default'} selected {execution['label']}. "
        rationale += " ".join(f"{key}: {row['rationale']}" for key, row in findings.items())
        trace = {"version": EXECUTABLE_VERSION, "rubric": policy.source.to_dict(),
                 "executable_policy": policy.to_dict(), "plan": plan.to_dict(),
                 "observations": deepcopy(observations), "predicate_findings": findings,
                 "execution": execution}
        return DecompositionResult(execution["label"], rationale, trace)


# Experimental visual calibration

class DecompositionTwoWayCalibratedVision(DecompositionTwoWayIntent):
    """Grade per-condition findings jointly from images, optionally with training pairs.

    Instruction compilation remains image/label-blind, and rubric units remain
    lossless. Findings and the final label share one vision call, so they are not
    independent observations. Human references can alter rubric interpretation;
    explicit conflicts are returned. This strategy is experimental, not default.
    """

    def __init__(self, engine, *, references=(), **kwargs):
        super().__init__(engine, **kwargs)
        references = tuple(references)
        self.reference_bank = VisualReferenceBank(references) if references else None
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_calibrated_v1")
        self.templates["aggregate_visual"] = directory.joinpath("aggregate_visual.txt").read_text(encoding="utf-8")

    def observe(self, plan, evidence):
        raise NotImplementedError("This strategy jointly observes and grades images; use evaluate")

    def aggregate(self, policy, observations):
        raise NotImplementedError("This strategy requires the query image pair; use evaluate")

    def _grade_visual(self, payload, media):
        engine = self.vision_engine
        media_identity = [{"type": m["type"], "text": m.get("text"),
                           "sha256": hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest() if "path" in m else None}
                          for m in media]
        identity = {"version": "calitree-decomposition-calibrated-vision-v1", "payload": payload,
                    "template": self.templates["aggregate_visual"], "media": media_identity,
                    "model": getattr(engine, "model", None), "engine": getattr(engine, "name", None),
                    "temperature": getattr(engine, "temperature", None), "max_tokens": getattr(engine, "max_tokens", None)}
        key = "twoway-calibrated-vision:" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with self._registry_lock:
            lock = self._locks.setdefault(key, Lock())
        with lock:
            if key in self._cache:
                return deepcopy(parse_visual_grade(self._cache[key], payload))
            if self.checkpoint is not None and self.checkpoint.has(key):
                value = parse_visual_grade(self.checkpoint.get(key), payload)
                self._cache[key] = deepcopy(value)
                return deepcopy(value)
            error = None
            for attempt in range(self.schema_retries + 1):
                # Keep the validated prototype's message placement, not a new system prompt.
                text = self.templates["aggregate_visual"] + "\nINPUT_JSON: " + json.dumps(payload, ensure_ascii=False)
                if error is not None:
                    text += "\nSCHEMA_ERROR: " + error
                response = engine.generate(text, media_inputs=media, schema={})
                entry = {"stage": "aggregate_visual", "key": key, "attempt": attempt,
                         "input": deepcopy(payload), "prompt": text, "media": deepcopy(media),
                         "media_identity": media_identity, "response": response}
                with self._registry_lock:
                    self.calls.append(entry)
                try:
                    value = parse_visual_grade(response.get("parsed"), payload)
                except ValueError as exc:
                    entry["validation_error"] = str(exc)
                    if attempt == self.schema_retries:
                        raise
                    error = str(exc)
                    continue
                self._cache[key] = deepcopy(value)
                if self.checkpoint is not None:
                    self.checkpoint.put(key, value)
                return deepcopy(value)
        raise AssertionError("No visual grading result")

    def evaluate(self, policy, instruction, evidence):
        policy = SemanticRubric.from_dict(policy.to_dict())
        query_media, digests = self._media(evidence)
        plan = self.decompose(instruction)
        references = self.reference_bank.select(plan, query_media[0]["path"]) if self.reference_bank else ()
        payload, media = visual_grade_input(policy, plan, query_media, references)
        decision = self._grade_visual(payload, media)
        trace = {"version": "calitree-decomposition-calibrated-vision-v1", "rubric": policy.to_dict(),
                 "plan": plan.to_dict(), "decision": decision, "grade_input": payload,
                 "observations": {"condition_findings": deepcopy(decision["condition_findings"]), "image_sha256": digests},
                 "calibration": {"reference_source_ids": [r.id for r in references]}, "media": media}
        return DecompositionResult(decision["label"], decision["rationale"], trace)


class FrozenCriteriaExecutor:
    """Execute saved per-case criteria without recompiling or fitting labels.

    This is an observation component for fitted decision sets, not another
    default judging strategy. It preserves unknown statuses and leaves the
    caller's declared aggregation/learned-tree policy separate.
    """

    def __init__(self, engine, *, checkpoint=None, schema_retries=1):
        if not callable(getattr(engine, "generate", None)):
            raise ValueError("An engine with generate() is required")
        if type(schema_retries) is not int or schema_retries not in (0, 1):
            raise ValueError("Expected zero or one schema repair")
        directory = files("critical.core.prompts").joinpath("templates", "calitree_decomposition_casewise_v1")
        self.template = directory.joinpath("check_condition.txt").read_text(encoding="utf-8")
        self.neutral_note = directory.joinpath("neutral_note.txt").read_text(encoding="utf-8")
        self.observer_template = directory.joinpath("observe_neutral.txt").read_text(encoding="utf-8")
        self.engine, self.checkpoint, self.schema_retries = engine, checkpoint, schema_retries
        self.calls = []

    def observe(self, criteria, *, prompt, instruction, evidence, neutral_evidence=None):
        from .decision_sets import (
            FrozenCriteria, NeutralEvidence, CHECK_SCHEMA, validate_criterion_check, json_hash,
        )
        if not isinstance(criteria, FrozenCriteria):
            raise ValueError("Expected FrozenCriteria")
        plan = FrozenCriteria.from_dict(criteria.to_dict()).validate_context(prompt, instruction)
        media, image_hashes = DecompositionTwoWayVision._media(evidence)
        neutral = None
        if neutral_evidence is not None:
            if not isinstance(neutral_evidence, NeutralEvidence):
                raise ValueError("Expected bound NeutralEvidence")
            neutral_evidence = NeutralEvidence.from_dict(neutral_evidence.to_dict())
            neutral = neutral_evidence.checker_payload(image_hashes)
        # All bindings above are checked before any billable condition call.
        marked = [{"type": "text", "text": "SOURCE image"}, media[0],
                  {"type": "text", "text": "EDITED image"}, media[1]]
        checks, features = [], []
        template = self.template + (self.neutral_note if neutral is not None else "")
        for condition in plan["plan"]["conditions"]:
            payload = {"instruction": instruction, "condition": deepcopy(condition)}
            if neutral is not None:
                payload["independent_neutral_observations"] = deepcopy(neutral)
            identity = {
                "version": "calitree-condition-check-v1", "criteria_sha256": plan["artifact_sha256"],
                "payload": payload, "template": template, "schema": CHECK_SCHEMA,
                "image_sha256": image_hashes,
                "engine": {key: getattr(self.engine, key, None)
                           for key in ("name", "model", "temperature", "max_tokens")},
            }
            key = "frozen-criteria:" + json_hash(identity)
            value = self._request(key, identity, "condition_check", payload, template,
                                  CHECK_SCHEMA, validate_criterion_check, marked, image_hashes)
            checks.append({"condition_id": condition["id"], **deepcopy(value), "check_key": key})
            features.append({
                "condition_id": condition["id"],
                "local_criterion_sha256": json_hash({
                    "prompt_sha256": plan["prompt_sha256"], "instruction": instruction,
                    "criterion": {k: v for k, v in condition.items() if k != "id"},
                }),
                "status": value["status"], "observed": value["status"] != "unknown",
            })
        return {"version": "calitree-condition-observations-v1", "criteria": plan,
                "image_sha256": image_hashes, "checks": checks, "local_features": features,
                "neutral_evidence": neutral_evidence.to_dict() if neutral_evidence is not None else None}

    def observe_neutral(self, probes, *, evidence):
        """Measure typed properties on each image without instruction or role.

        Reuse a checkpoint for deterministic replay; use a separate checkpoint
        namespace for each genuinely fresh observation repeat. Selection of
        probe classes remains caller-owned and must exclude desired states.
        """
        from .decision_sets import (
            NeutralEvidence, compile_neutral_probes, json_hash,
            neutral_answer_schema, validate_neutral_answers,
        )
        _, records = compile_neutral_probes(probes)
        media, hashes = DecompositionTwoWayVision._media(evidence)
        # Canonical ordering and new IDs prevent obsolete condition IDs and
        # caller-specific ordering from affecting observer input or reuse.
        records.sort(key=lambda row: row["key"])
        questions = [{"id": f"q{i + 1}", "question": row["question"]}
                     for i, row in enumerate(records)]
        canonical = [{"id": question["id"], **{k: row[k] for k in
                      ("property", "object_class", "reference_class")}}
                     for question, row in zip(questions, records)]
        ids = [q["id"] for q in questions]
        payload, schema = {"questions": questions}, neutral_answer_schema(ids)
        observations, keys = {}, []
        for i, role in enumerate(("source", "edited")):
            identity = {
                "version": "calitree-neutral-observation-v1", "payload": payload,
                "template": self.observer_template, "schema": schema, "image_sha256": [hashes[i]],
                "engine": {key: getattr(self.engine, key, None)
                           for key in ("name", "model", "temperature", "max_tokens")},
            }
            key = "neutral-observation:" + json_hash(identity)
            observations[role] = self._request(
                key, identity, "neutral_observation", payload, self.observer_template,
                schema, lambda value: validate_neutral_answers(value, ids), [media[i]], [hashes[i]])
            keys.append(key)
        return NeutralEvidence.bind(canonical, observations, hashes,
                                    origin="observer-checkpoints:" + json_hash(keys))

    def _request(self, key, identity, stage, payload, template, schema, validate, media, image_hashes):
        if self.checkpoint is not None and self.checkpoint.has(key):
            cached = self.checkpoint.get(key)
            if not isinstance(cached, dict) or cached.get("identity") != identity:
                raise ValueError("Observation checkpoint identity mismatch")
            return validate(cached.get("value"))
        error, invalid = None, None
        for attempt in range(self.schema_retries + 1):
            text = template + "\nINPUT_JSON: " + json.dumps(payload, ensure_ascii=False)
            if error is not None:
                text += "\nSCHEMA_ERROR: " + error + "\nINVALID_RESPONSE: " + str(invalid)
            entry = {"stage": stage, "key": key, "attempt": attempt,
                     "input": deepcopy(payload), "image_sha256": list(image_hashes)}
            self.calls.append(entry)
            try:
                response = self.engine.generate(text, media_inputs=media, schema=schema, strict_schema=True)
            except BaseException as exc:
                entry["error_type"] = type(exc).__name__
                raise
            entry["response"] = deepcopy(response)
            try:
                value = validate(response.get("parsed") if isinstance(response, dict) else None)
            except ValueError as exc:
                error = str(exc)
                invalid = response.get("content") if isinstance(response, dict) else response
                entry["validation_error"] = error
                if attempt == self.schema_retries:
                    raise
                continue
            if self.checkpoint is not None:
                self.checkpoint.put(key, {"identity": identity, "value": value})
            return value
