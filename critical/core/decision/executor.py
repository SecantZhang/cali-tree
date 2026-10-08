"""Direct saved-program execution with label-isolated atomic requests."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
from .models import STATES, Observation, DecisionResult
from .validation import ordered_checks
from .aggregation import aggregate
from .artifacts import digest, program_ref
from .calls import CallFailure
from .compiler import object_schema, enum, TEXT, media_inputs

OBSERVATION_SCHEMA = object_schema({'status': enum(STATES), 'evidence': TEXT})
class ModelChecker:
    def __init__(self, calls):
        self.calls = calls
        self.identity = {'provider': calls.identity, 'checker': 'atomic-leaf-v2'}
    def check(self, program, check, outcome, evidence, dependencies, *, slot, final=False):
        value, ref = self.calls.call('check', {'instruction': program.instruction, 'rubric': program.rubric,
                'outcome': asdict(outcome), 'check': asdict(check), 'dependencies': dependencies}, OBSERVATION_SCHEMA,
                template=program.checker_template, media=media_inputs(evidence), slot=slot, final=final, max_tokens=1024)
        job = json.loads((self.calls.directory / 'jobs' / (ref + '.json')).read_text())
        return {**value, 'execution_ref': ref, 'completion_tokens': int(job['response'].get('completionTokens', 0))}

class ProgramExecutor:
    def __init__(self, checker, *, checkpoint=None, max_checks=4):
        self.checker, self.checkpoint, self.max_checks = checker, checkpoint, max_checks
        self.cache = {}
    def execute(self, program, evidence, *, repeat='0', final=False):
        ref = program_ref(program)
        checks = ordered_checks(program, self.max_checks)
        evidence = {k: evidence[k] for k in ('source_image', 'edited_image')}
        images = {k: sha256(Path(p).read_bytes()).hexdigest() for k, p in evidence.items()}
        outcomes = {o.id: o for o in program.outcomes}
        observed = {}
        for check in checks:
            deps = [observed[d].to_dict() for d in check.dependencies]
            outcome = outcomes[check.outcome_id]
            key = digest([self.checker.identity, program.checker_template, program.instruction, program.rubric,
                          asdict(check), asdict(outcome), images, deps, str(repeat)])
            if key in self.cache:
                obs = self.cache[key]
            elif self.checkpoint is not None and self.checkpoint.has('leaf-observe:' + key):
                obs = Observation(**self.checkpoint.get('leaf-observe:' + key))
            elif any(d['status'] == 'unknown' or not d['valid'] for d in deps):
                obs = Observation(check.id, 'unknown', 'Required dependency unknown', key)
            else:
                try:
                    row = self.checker.check(program, check, outcome, evidence, deps, slot=str(repeat), final=final)
                    if row.get('status') not in STATES or not isinstance(row.get('evidence'), str) or not row['evidence'].strip():
                        raise ValueError('Invalid atomic observation')
                    obs = Observation(check.id, row['status'], row['evidence'], row.get('execution_ref', key), True,
                                      int(row.get('completion_tokens', 0)))
                except (CallFailure, ValueError, KeyError, TypeError) as exc:
                    obs = Observation(check.id, 'unknown', str(exc), key, False)
            self.cache[key] = obs
            if self.checkpoint is not None and not self.checkpoint.has('leaf-observe:' + key):
                self.checkpoint.put('leaf-observe:' + key, obs.to_dict())
            observed[check.id] = obs
        label, reason = aggregate(program, tuple(observed.values()))
        return DecisionResult(label, reason, tuple(observed.values()), ref)
