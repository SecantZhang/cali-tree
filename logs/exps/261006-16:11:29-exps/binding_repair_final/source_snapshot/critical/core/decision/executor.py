"""Execute the saved program directly, with isolated atomic model inputs."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json

from .aggregation import aggregate
from .artifacts import digest, program_ref
from .calls import CallFailure
from .compiler import object_schema, template, TEXT
from .models import DecisionResult, Observation, STATES
from .validation import bound_checks

CHECK_SCHEMA = object_schema({"status": {"type": "string", "enum": list(STATES)}, "evidence": TEXT})


class ModelChecker:
    def __init__(self, calls):
        self.calls = calls
        self.identity = {"provider": calls.identity, "checker": "atomic-check-v1"}

    def check(self, predicate, outcome, instruction, evidence, dependencies, *, slot, final=False, template_text):
        payload = {"instruction": instruction, "outcome": asdict(outcome),
                   "predicate": predicate.to_dict(), "dependencies": dependencies}
        media = [{"type": "text", "text": "SOURCE image"},
                 {"type": "image", "path": evidence["source_image"]},
                 {"type": "text", "text": "EDITED image"},
                 {"type": "image", "path": evidence["edited_image"]}]
        value, ref = self.calls.call("check", payload, CHECK_SCHEMA, template=template_text,
                                     media=media, slot=slot, final=final, max_tokens=1024)
        job = json.loads((self.calls.directory / "jobs" / (ref + ".json")).read_text())
        return {**value, "execution_ref": ref,
                "completion_tokens": int(job["response"].get("completionTokens", 0))}


class ProgramExecutor:
    def __init__(self, checker, *, checkpoint=None, max_checks=4):
        self.checker, self.checkpoint, self.max_checks = checker, checkpoint, max_checks
        self.cache = {}

    def execute(self, program, plan, evidence, *, repeat="0", final=False):
        ref = program_ref(program)
        try:
            checks = bound_checks(program, plan, self.max_checks)
        except ValueError as exc:
            return DecisionResult(None, str(exc), (), ref, plan)
        evidence = {key: evidence[key] for key in ("source_image", "edited_image")}
        images = {key: sha256(Path(path).read_bytes()).hexdigest() for key, path in evidence.items()}
        observed, rows = {}, []
        for outcome, predicate in checks:
            dependencies = [observed[(outcome.id, d)].to_dict() for d in predicate.dependencies]
            key = digest([self.checker.identity, program.checker_template, predicate.to_dict(), asdict(outcome), plan.instruction,
                          images, dependencies, str(repeat)])
            if key in self.cache:
                obs = self.cache[key]
            elif self.checkpoint is not None and self.checkpoint.has("program:observe:" + key):
                obs = Observation(**self.checkpoint.get("program:observe:" + key))
            elif any(d["status"] != "complete" or not d["valid"] for d in dependencies):
                obs = Observation(outcome.id, predicate.id, "unknown", "Dependency is not established", key)
            else:
                try:
                    row = self.checker.check(predicate, outcome, plan.instruction, evidence, dependencies,
                                             slot=str(repeat), final=final, template_text=program.checker_template)
                    if row.get("status") not in STATES or not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
                        raise ValueError("Invalid atomic observation")
                    obs = Observation(outcome.id, predicate.id, row["status"], row["evidence"], row.get("execution_ref", key),
                                      True, int(row.get("completion_tokens", 0)))
                except (CallFailure, ValueError) as exc:
                    obs = Observation(outcome.id, predicate.id, "unknown", str(exc), key, False)
            self.cache[key] = obs
            if self.checkpoint is not None and not self.checkpoint.has("program:observe:" + key):
                self.checkpoint.put("program:observe:" + key, obs.to_dict())
            observed[(outcome.id, predicate.id)] = obs
            rows.append(obs)
        label, reason = aggregate(program, plan, rows)
        return DecisionResult(label, reason, tuple(rows), ref, plan)
