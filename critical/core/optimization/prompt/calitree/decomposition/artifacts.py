"""Portable decomposition adapters and a single executor for fit and inference."""

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .decomposition_twoway import DecompositionTwoWay, DecompositionTwoWayVision
from .policy import CompiledPolicy
from .vision_models import SemanticRubric


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


class DecompositionAdapter(ABC):
    """Custom strategies must supply data-only export and restoration explicitly."""

    name: str

    @abstractmethod
    def inputs(self, sample: dict) -> tuple[str, dict]:
        """Validate and strip annotations before any compilation/model call."""

    @abstractmethod
    def compile(self, prompt: str) -> Any:
        ...

    @abstractmethod
    def restore(self, payload: dict) -> Any:
        ...

    @abstractmethod
    def evaluate(self, policy: Any, instruction: str, evidence: dict) -> dict:
        """Return label, rationale, plan, checks and trace as JSON-compatible data."""

    def decompose(self, instruction):
        return self.algorithm.decompose(instruction).to_dict()

    def restore_plan(self, payload, instruction):
        raise ValueError("This adapter does not support staged execution")

    def observe(self, policy, plan, evidence):
        raise ValueError("This adapter does not support staged execution")

    def aggregate(self, policy, plan, observations):
        raise ValueError("This adapter does not support staged execution")

    def export(self, policy: Any) -> dict:
        return policy.to_dict()

    def identity(self) -> dict:
        return {"algorithm": self.name}

    def evidence_identity(self, evidence: dict) -> dict:
        return evidence


class TwoWayAdapter(DecompositionAdapter):
    name = "two_way"

    def __init__(self, algorithm: DecompositionTwoWay):
        self.algorithm = algorithm

    def inputs(self, sample):
        instruction, evidence = self.algorithm._sample(sample)
        allowed = {"color", "shape", "position", "count", "content_recognizable", "subject_identity", "background"}
        return instruction, {key: deepcopy(value) for key, value in evidence.items() if key in allowed}

    def compile(self, prompt):
        return self.algorithm.compile(prompt)

    def restore(self, payload):
        return CompiledPolicy.from_dict(payload)

    def evaluate(self, policy, instruction, evidence):
        plan = self.algorithm.decompose(instruction)
        result = self.algorithm.evaluate_many(policy, {"case": plan}, {"case": evidence})["case"]
        return {**result.judgment(), "plan": plan.to_dict(),
                "checks": {"edits": [c.to_dict() for c in policy.edits(plan)],
                           "guards": [c.to_dict() for c in policy.guards(plan)]},
                "trace": result.trace}

    def restore_plan(self, payload, instruction):
        from .models import parse_plan
        return parse_plan(payload)

    def observe(self, policy, plan, evidence):
        return self.algorithm.observe(policy, plan, evidence)

    def aggregate(self, policy, plan, observations):
        result = self.algorithm.aggregate(policy, observations)
        return {**result.judgment(), "plan": plan.to_dict(), "trace": result.trace,
                "checks": {"edits": [c.to_dict() for c in policy.edits(plan)],
                           "guards": [c.to_dict() for c in policy.guards(plan)]}}

    def identity(self):
        result = super().identity()
        for name in ("rubric_compiler", "instruction_compiler", "condition_evaluator"):
            component = getattr(self.algorithm, name)
            result[name] = component_identity(component)
        return result


def component_identity(component):
    result = {"class": type(component).__module__ + "." + type(component).__qualname__}
    templates = getattr(component, "templates", None)
    if templates is not None:
        result["templates"] = asdict(templates) if is_dataclass(templates) else templates
    engine = getattr(component, "engine", None)
    if engine is not None:
        result["engine"] = {k: getattr(engine, k, None)
                            for k in ("name", "model", "temperature", "max_tokens")}
    return result


class TwoWayVisionAdapter(DecompositionAdapter):
    name = "two_way_vision"

    def __init__(self, algorithm: DecompositionTwoWayVision):
        if algorithm.review or algorithm.resolve_disagreements:
            raise ValueError("Modular vision adapter requires review/resolution disabled")
        self.algorithm = algorithm

    def inputs(self, sample):
        if not isinstance(sample, dict):
            raise ValueError("Sample must be a mapping")
        user_input, output = sample.get("input") or {}, sample.get("output") or {}
        if not isinstance(user_input, dict) or not isinstance(output, dict):
            raise ValueError("Sample input/output must be mappings")
        instruction = sample.get("instruction") or user_input.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Sample requires an instruction")
        evidence = sample.get("evidence")
        if evidence is None:
            images = sample.get("images") or [user_input.get("source_image_path"),
                                               output.get("edited_image_path")]
            if not isinstance(images, (list, tuple)) or len(images) != 2:
                raise ValueError("Sample requires SOURCE and EDITED images")
            evidence = dict(zip(("source_image", "edited_image"), images))
        self.algorithm._media(evidence)
        return instruction, {k: str(evidence[k]) for k in ("source_image", "edited_image")}

    def evidence_identity(self, evidence):
        return {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in evidence.items()}

    def compile(self, prompt):
        return self.algorithm.compile(prompt)

    def restore(self, payload):
        return SemanticRubric.from_dict(payload)

    def evaluate(self, policy, instruction, evidence):
        plan = self.algorithm.decompose(instruction)
        observations = self.algorithm.observe(plan, evidence)
        result = self.algorithm.aggregate(policy, observations)
        return {**result.judgment(), "plan": plan.to_dict(),
                "checks": {"requested": [c.to_dict() for c in plan.conditions],
                           "preservation": True}, "trace": result.trace}

    def restore_plan(self, payload, instruction):
        from .vision_models import parse_semantic_instruction
        return parse_semantic_instruction({"conditions": payload["conditions"]}, instruction)

    def observe(self, policy, plan, evidence):
        return self.algorithm.observe(plan, evidence)

    def aggregate(self, policy, plan, observations):
        result = self.algorithm.aggregate(policy, observations)
        return {**result.judgment(), "plan": plan.to_dict(), "trace": result.trace,
                "checks": {"requested": [c.to_dict() for c in plan.conditions], "preservation": True}}

    def identity(self):
        return {**super().identity(), "templates": self.algorithm.templates,
                "engine": component_identity(self.algorithm),
                "vision_engine": {k: getattr(self.algorithm.vision_engine, k, None)
                                  for k in ("name", "model", "temperature", "max_tokens")}}


class ArtifactExecutor:
    """Run-scoped cache; persisted policies are authoritative when loading a tree."""

    def __init__(self, adapter: DecompositionAdapter, checkpoint=None):
        self.adapter, self.checkpoint = adapter, checkpoint
        self.policies: dict[str, dict] = {}
        self.evaluations: dict[str, dict] = {}
        self.identity = adapter.identity()

    def preflight(self, samples):
        for sample in samples.values():
            self.adapter.inputs(sample)

    def policy(self, prompt):
        key = prompt_hash(prompt)
        if key in self.policies:
            return self.adapter.restore(deepcopy(self.policies[key]["payload"]))
        cache_key = "modular:policy:" + digest([self.identity, key])
        if self.checkpoint is not None and self.checkpoint.has(cache_key):
            payload = self.checkpoint.get(cache_key)
            policy = self.adapter.restore(payload)
        else:
            policy = self.adapter.compile(prompt)
            payload = self.adapter.export(policy)
            self.adapter.restore(payload)  # validate exports before committing
            if self.checkpoint is not None:
                self.checkpoint.put(cache_key, payload)
        if payload.get("rubric", prompt) != prompt:
            raise ValueError("Policy source differs from prompt")
        self.policies[key] = {"strategy": self.adapter.name, "prompt_sha256": key,
                              "payload": deepcopy(payload), "identity": deepcopy(self.identity)}
        return policy

    def judge(self, prompt, sample):
        # Preflight happens before policy compilation, including on cache hits.
        instruction, evidence = self.adapter.inputs(sample)
        policy = self.policy(prompt)
        key = digest([self.identity, prompt_hash(prompt), instruction,
                      self.adapter.evidence_identity(evidence)])
        cache_key = "modular:evaluate:" + key
        if key not in self.evaluations:
            if self.checkpoint is not None and self.checkpoint.has(cache_key):
                row = deepcopy(self.checkpoint.get(cache_key))
            else:
                row = self.adapter.evaluate(policy, instruction, evidence)
            if row.get("label") not in {"no", "partial", "yes"} or any(
                name not in row for name in ("rationale", "plan", "checks", "trace")
            ):
                raise ValueError("Malformed decomposition evaluation")
            json.dumps(row, allow_nan=False)
            self.evaluations[key] = deepcopy(row)
            if self.checkpoint is not None and not self.checkpoint.has(cache_key):
                self.checkpoint.put(cache_key, row)
        return {**deepcopy(self.evaluations[key]), "valid": True, "evaluation_ref": key,
                "policy_ref": prompt_hash(prompt)}

    def judge_many(self, prompt, samples):
        self.preflight(samples)
        return {key: self.judge(prompt, sample) for key, sample in samples.items()}

    def load_policies(self, policies, *, strategy):
        if strategy != self.adapter.name:
            raise ValueError("Tree decomposition strategy does not match executor")
        for key, entry in policies.items():
            if entry.get("strategy") != strategy or entry.get("prompt_sha256") != key:
                raise ValueError("Invalid policy envelope")
            policy = self.adapter.restore(entry["payload"])
            source = self.adapter.export(policy).get("rubric")
            if source is None or prompt_hash(source) != key:
                raise ValueError("Policy source hash mismatch")
        self.policies.update(deepcopy(policies))
