"""Label-isolated execution of saved flat and conditional programs."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import math
from critical.core.decision.artifacts import digest
from critical.core.decision.calls import CallFailure
from critical.core.decision.compiler import object_schema, enum, TEXT, media_inputs
from .models import STATES, GATES, validate

OBS_SCHEMA = object_schema({'status': enum((*STATES, 'pass', 'fail')), 'evidence': TEXT,
                            'confidence': {'type': ['number', 'null']}})

class RobustChecker:
    def __init__(self, calls):
        self.calls = calls
        self.identity = {'provider': calls.identity, 'checker': 'robust-atomic-v3', 'scope': getattr(calls, 'case_id', None)}

    def check(self, program, node, outcome, evidence, dependencies, *, slot, final=False):
        value, ref = self.calls.call('check', {'instruction': program.instruction, 'rubric': program.rubric,
            'node': asdict(node), 'outcome': asdict(outcome) if outcome else None,
            'dependencies': dependencies}, OBS_SCHEMA, template=program.checker_template,
            media=media_inputs(evidence), slot=slot, final=final, max_tokens=1024)
        job = json.loads((self.calls.directory / 'jobs' / (ref + '.json')).read_text())
        return {**value, 'execution_ref': ref, 'completion_tokens': int(job['response'].get('completionTokens', 0))}


def reduced(states):
    if not states or 'unknown' in states:
        return 'unknown'
    if all(s == 'complete' for s in states):
        return 'complete'
    if all(s == 'absent' for s in states):
        return 'absent'
    return 'partial'


class RobustExecutor:
    def __init__(self, checker, *, checkpoint=None, max_checks=4):
        if max_checks != 4:
            raise ValueError('v3 execution cap is four')
        self.checker, self.checkpoint, self.max_checks = checker, checkpoint, max_checks
        self.cache = {}

    def execute(self, program, evidence, *, repeat='0', final=False):
        validate(program)
        evidence = {k: evidence[k] for k in ('source_image', 'edited_image')}
        images = {k: sha256(Path(v).read_bytes()).hexdigest() for k, v in evidence.items()}
        observed, transitions = {}, []
        outs = {o.id: o for o in program.outcomes}
        accounted = {o.id: {'status': 'unknown', 'applicability': o.applicability,
                           'source': 'unresolved', 'reason': 'Fulfillment has not been established'} for o in program.outcomes}

        def account(oid, status, applicability, source, reason):
            previous = accounted[oid]
            if previous['source'] != 'unresolved' and (previous['status'], previous['applicability']) != (status, applicability):
                accounted[oid] = {'status': 'unknown', 'applicability': 'unknown', 'source': 'conflict', 'reason': 'Conflicting evidence/inference'}
            else:
                accounted[oid] = {'status': status, 'applicability': applicability, 'source': source, 'reason': reason}

        def visit(node, parent_active=True):
            parent = observed.get(node.parent)
            eligible = parent_active and (not parent or program.mode == 'flat' or parent['status'] in node.active_on)
            deps = [observed[d] for d in node.dependencies]
            outcome = outs.get(node.outcome_id)
            reason = ''
            if not eligible:
                reason = 'Inactive conditional branch'
            elif outcome and outcome.applicability != 'applicable':
                eligible, reason = False, 'Declared applicability: ' + outcome.applicability
            elif any(d['status'] == 'unknown' or not d['valid'] for d in deps):
                eligible, reason = False, 'Unknown required evidence dependency'
            obs = {'check_id': node.id, 'status': 'unknown', 'evidence': reason, 'valid': False,
                   'eligible': eligible, 'queried': False, 'confidence': None, 'completion_tokens': 0,
                   'dependencies': deps, 'execution_ref': '', 'failure': None}
            if eligible:
                # Complete identity safely invalidates all results after routing/semantic edits.
                key = digest([program.ref, self.checker.identity, images, node.id, deps, str(repeat), final])
                if key in self.cache:
                    obs = self.cache[key]
                elif self.checkpoint is not None and self.checkpoint.has('robust-observe:' + key):
                    obs = self.checkpoint.get('robust-observe:' + key)
                else:
                    obs.update(queried=True, execution_ref=key)
                    try:
                        row = self.checker.check(program, node, outcome, evidence, deps,
                                                 slot=f'{repeat}/{node.id}', final=final)
                        obs['completion_tokens'] = int(row.get('completion_tokens', 0))
                        allowed = STATES if node.role == 'requested' else GATES
                        if row.get('status') not in allowed or not isinstance(row.get('evidence'), str) or not row['evidence'].strip():
                            raise ValueError('Invalid atomic observation')
                        confidence = row.get('confidence')
                        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                            confidence = None
                        obs.update({k: row[k] for k in ('status', 'evidence')}, valid=True, confidence=confidence,
                                   execution_ref=row.get('execution_ref', key), completion_tokens=int(row.get('completion_tokens', 0)))
                    except (CallFailure, ValueError, KeyError, TypeError) as exc:
                        obs.update(evidence=str(exc), failure=type(exc).__name__)
                        # Failed/interrupted durable calls remain charged at their output cap.
                        obs['completion_tokens'] = 1024 if isinstance(exc, CallFailure) else obs['completion_tokens']
                    self.cache[key] = obs
                    if self.checkpoint is not None:
                        self.checkpoint.put('robust-observe:' + key, obs)
            observed[node.id] = obs
            transitions.append({'node': node.id, 'parent': node.parent, 'active_on': list(node.active_on),
                                'eligible': eligible, 'state': obs['status'], 'skip_reason': reason})
            if node.role == 'requested' and obs['queried']:
                account(node.outcome_id, obs['status'], outcome.applicability, 'queried', obs['evidence'])
            if program.mode == 'tree' and obs['valid']:
                for inference in node.inferences:
                    if inference.when == obs['status']:
                        account(inference.outcome_id, inference.status, inference.applicability,
                                'inferred:' + node.id, inference.justification)
            for child in program.nodes:
                if child.parent == node.id:
                    visit(child, eligible if program.mode == 'tree' else True)

        for root in program.nodes:
            if not root.parent:
                visit(root)
        values = [v['status'] if v['applicability'] == 'applicable' else 'unknown'
                  for v in accounted.values() if v['applicability'] != 'not_applicable']
        state = reduced(values)
        requirements = {}
        for req in program.requirements:
            relevant = [accounted[o.id] for o in program.outcomes if req.id in o.requirement_ids]
            applicable = [v for v in relevant if v['applicability'] != 'not_applicable']
            requirements[req.id] = ('not_applicable' if not applicable else reduced([
                v['status'] if v['applicability'] == 'applicable' else 'unknown' for v in applicable]))
        return {'program_ref': program.ref, 'label': {'complete': 'yes', 'partial': 'partial', 'absent': 'no'}.get(state),
                'resolved': state != 'unknown', 'outcomes': accounted, 'requirements': requirements,
                'observations': list(observed.values()), 'transitions': transitions}
