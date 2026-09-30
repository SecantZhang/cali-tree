"""Model-backed, replaceable compilers and isolated structured-value checks."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from threading import Lock
from typing import Any, Optional

from critical.checkpoint import CheckpointStore
from critical.core.judge.parse import parse_json_object

from .decomposition_base import ConditionEvaluator, InstructionCompiler, RubricCompiler
from .models import Condition, ConditionResult, InstructionPlan, parse_condition, parse_plan
from .policy import CompiledPolicy, UnsupportedDecompositionError, parse_policy
from .prompts import DecompositionTemplates, load_templates


class _ModelComponent:
    def __init__(
        self, engine: Any, *, templates: Optional[DecompositionTemplates] = None,
        checkpoint: Optional[CheckpointStore] = None, schema_retries: int = 1,
    ) -> None:
        if engine is None or not callable(getattr(engine, "generate", None)):
            raise ValueError("Model-backed decomposition requires an engine with generate()")
        if type(schema_retries) is not int or schema_retries not in {0, 1}:
            raise ValueError("schema_retries must be 0 or 1; quality retries are not supported")
        self.engine = engine
        self.templates = templates if templates is not None else load_templates()
        self.checkpoint = checkpoint
        self.schema_retries = schema_retries
        self._mutex = Lock()
        self._locks: dict[str, Any] = {}

    def _key(self, system: str, payload: Any) -> str:
        identity = {"schema": "twoway-v1", "template_version": self.templates.version,
                    "template": system, "component": type(self).__name__,
                    "model": str(getattr(self.engine, "model", "")),
                    "temperature": getattr(self.engine, "temperature", None),
                    "max_tokens": getattr(self.engine, "max_tokens", None),
                    "engine": str(getattr(self.engine, "name", "")), "input": payload}
        value = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return f"calitree::decomposition::{type(self).__name__}::{value}"

    def _lock(self, key: str):
        with self._mutex:
            return self._locks.setdefault(key, Lock())


class ModelRubricCompiler(_ModelComponent, RubricCompiler):
    def __init__(self, engine: Any, **kwargs: Any) -> None:
        super().__init__(engine, **kwargs)
        self.cache: dict[str, CompiledPolicy] = {}
        self.attempts: dict[str, list[dict[str, str]]] = {}

    def compile(self, rubric: str) -> CompiledPolicy:
        if not isinstance(rubric, str) or not rubric.strip():
            raise ValueError("Rubric must be nonempty text")
        key = self._key(self.templates.compile_policy, rubric)
        with self._lock(key):
            if key in self.cache:
                return self.cache[key]
            if self.checkpoint is not None and self.checkpoint.has(key):
                policy = CompiledPolicy.from_dict(self.checkpoint.get(key))
                if policy.rubric != rubric:
                    raise ValueError("Cached policy belongs to a different rubric")
                self.cache[key] = policy
                return policy
            lines = [{"line": i, "text": line} for i, line in enumerate(rubric.splitlines(), 1)]
            payload: dict[str, Any] = {"rubric_lines": lines}
            self.attempts[rubric] = []
            for attempt in range(self.schema_retries + 1):
                response = self.engine.generate(json.dumps(payload), system=self.templates.compile_policy)
                raw = str(response.get("content") or "")
                entry = {"content": raw}
                self.attempts[rubric].append(entry)
                try:
                    value = parse_json_object(raw)
                    policy = parse_policy(value, rubric)
                    if "decision_rules" not in policy.specification:
                        raise ValueError("The current compiler requires a staged policy")
                    self.cache[key] = policy
                    if self.checkpoint is not None:
                        self.checkpoint.put(key, policy.to_dict())
                    return policy
                except UnsupportedDecompositionError as error:
                    entry["validation_error"] = str(error)
                    raise
                except ValueError as error:
                    entry["validation_error"] = str(error)
                    if attempt == self.schema_retries:
                        raise
                    payload = {"rubric_lines": lines, "previous_policy": raw,
                               "validation_error": str(error),
                               "request": "Repair this policy to satisfy the schema while preserving the rubric's semantics. Use explicit status equalities, including any groups when multiple statuses match."}
        raise AssertionError("Compiler exhausted without a result")


class ModelInstructionCompiler(_ModelComponent, InstructionCompiler):
    def __init__(self, engine: Any, **kwargs: Any) -> None:
        super().__init__(engine, **kwargs)
        self._cache: dict[str, InstructionPlan] = {}
        self.plans: dict[str, InstructionPlan] = {}
        self.attempts: dict[str, list[dict[str, str]]] = {}

    def decompose(self, instruction: str) -> InstructionPlan:
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Instruction must be nonempty text")
        key = self._key(self.templates.decompose_instruction, instruction)
        with self._lock(key):
            if key in self._cache:
                return deepcopy(self._cache[key])
            if self.checkpoint is not None and self.checkpoint.has(key):
                plan = parse_plan(self.checkpoint.get(key))
                self._cache[key] = plan
                self.plans[instruction] = deepcopy(plan)
                return deepcopy(plan)
            payload = instruction
            self.attempts[instruction] = []
            for attempt in range(self.schema_retries + 1):
                response = self.engine.generate(payload, system=self.templates.decompose_instruction)
                raw = str(response.get("content") or "")
                entry = {"content": raw}
                self.attempts[instruction].append(entry)
                try:
                    plan = parse_plan(parse_json_object(raw))
                    self._cache[key] = plan
                    self.plans[instruction] = deepcopy(plan)
                    if self.checkpoint is not None:
                        self.checkpoint.put(key, plan.to_dict())
                    return deepcopy(plan)
                except ValueError as error:
                    entry["validation_error"] = str(error)
                    if attempt == self.schema_retries:
                        raise
                    payload = json.dumps({"instruction": instruction, "previous_plan": raw,
                                          "validation_error": str(error),
                                          "request": "Repair the schema while retaining every requested condition, and only those conditions."})
        raise AssertionError("Instruction compiler exhausted without a result")


class ModelConditionEvaluator(_ModelComponent, ConditionEvaluator):
    def __init__(self, engine: Any, **kwargs: Any) -> None:
        super().__init__(engine, **kwargs)
        self._cache: dict[str, ConditionResult] = {}
        self.checks: dict[str, dict[str, str]] = {}

    @staticmethod
    def request(condition: Condition, evidence: dict[str, Any]) -> str:
        if not isinstance(condition, Condition) or not isinstance(condition.key, str):
            raise ValueError("Expected a named Condition")
        if not isinstance(evidence, dict):
            raise ValueError("Structured evidence must be a mapping")
        if condition.key in {"color", "shape", "position", "count"}:
            parse_condition(condition.to_dict())
        elif condition.key == "content_recognizable":
            if condition.operator != "equals" or type(condition.expected) is not bool:
                raise ValueError("Recognizability requires an explicit boolean equality")
        elif condition.key in {"subject_identity", "background"}:
            if (condition.operator != "equals" or not isinstance(condition.expected, str)
                    or condition.expected not in {"preserved", "changed"}):
                raise ValueError("Preservation requires an explicit equality")
        else:
            raise UnsupportedDecompositionError(f"Unsupported evidence condition: {condition.key}")
        if condition.key not in evidence:
            raise ValueError(f"Missing evidence for {condition.key}")
        observed = evidence[condition.key]
        if (condition.key == "count" and observed is not None and observed != "unknown"
                and (type(observed) is not int or observed < 0)):
            raise ValueError("Observed count must be a nonnegative integer, null, or unknown")
        return json.dumps({"condition": condition.to_dict(), "observed": observed},
                          sort_keys=True, allow_nan=False)

    def cache_key(self, condition: Condition, evidence: dict[str, Any]) -> str:
        return self.request(condition, evidence)

    def evaluate(self, condition: Condition, evidence: dict[str, Any]) -> ConditionResult:
        request = self.request(condition, evidence)
        key = self._key(self.templates.check_condition, request)
        with self._lock(key):
            if key in self._cache:
                return self._cache[key]
            if self.checkpoint is not None and self.checkpoint.has(key):
                result = ConditionResult.from_dict(self.checkpoint.get(key))
            else:
                response = self.engine.generate(request, system=self.templates.check_condition)
                result = ConditionResult.from_dict(parse_json_object(str(response.get("content") or "")))
                if self.checkpoint is not None:
                    self.checkpoint.put(key, result.to_dict())
            self._cache[key] = result
            self.checks[request] = result.to_dict()
            return result
