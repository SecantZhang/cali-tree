"""Bounded label-blind visual hypotheses from explicitly configured model families."""
from dataclasses import dataclass

from critical.core.decision.calls import CallFailure
from critical.core.decision.compiler import TEXT, array, enum, object_schema, media_inputs
from critical.core.decision.robust.refinement import template

FINDING_SCHEMA = object_schema({
    'kind': enum(('missing_evidence', 'nested_evidence', 'composition', 'no_repair')),
    **{key: TEXT for key in ('requirement_id', 'source_phrase', 'parent_id', 'question', 'criteria', 'evidence', 'rationale')},
})
DISCOVERY_SCHEMA = object_schema({'findings': array(FINDING_SCHEMA)})


@dataclass(frozen=True)
class VisualReviewer:
    name: str
    family: str
    calls: object


class VisualEvidenceDiagnosis:
    def __init__(self, reviewers):
        self.reviewers = tuple(reviewers)
        if not 1 <= len(self.reviewers) <= 2 or len({r.name for r in self.reviewers}) != len(self.reviewers):
            raise ValueError('Configure one or two distinct named reviewers')
        if any(not r.name.strip() or not r.family.strip() for r in self.reviewers):
            raise ValueError('Explicit reviewer names and family identifiers required')

    def discover(self, program, case, report, *, slot):
        # Do not forward report labels, agreement, target, feedback or audit
        # diagnostics. A reviewer discovers instruction-grounded evidence; it
        # does not manufacture an atomic answer from the reference label.
        payload = {'instruction': program.instruction, 'rubric': program.rubric,
            'program': program.to_dict(), 'observations': [
                t['observations'] for t in (report or {}).get('traces', [])], 'max_findings': 2}
        result = {'reviews': [], 'findings': [], 'failures': [], 'hypotheses_only': True}
        requirements = {r.id: r for r in program.requirements}
        nodes = {n.id: n for n in program.nodes}
        for reviewer in self.reviewers:
            identity = {'reviewer': reviewer.name, 'family': reviewer.family,
                        'requested_identity': reviewer.calls.identity}
            try:
                value, ref = reviewer.calls.call('visual_discovery', payload, DISCOVERY_SCHEMA,
                    template=template('discovery'), media=media_inputs(case.evidence),
                    slot=f'{slot}/{reviewer.name}', max_tokens=2048)
                findings = value.get('findings')
                if not isinstance(findings, list) or len(findings) > 2:
                    raise ValueError('Visual discovery exceeded its bounded finding allowance')
                result['reviews'].append({**identity, 'execution_ref': ref, 'findings': findings})
                for finding in findings:
                    try:
                        if set(finding) != set(FINDING_SCHEMA['properties']) or any(
                                not isinstance(finding[k], str) for k in finding):
                            raise ValueError('Malformed visual discovery hypothesis')
                        req = requirements.get(finding['requirement_id'])
                        phrase = finding['source_phrase']
                        if req is None or not phrase.strip() or phrase not in req.source_phrase:
                            raise ValueError('Hypothesis has no exact original requirement provenance')
                        if finding['kind'] not in FINDING_SCHEMA['properties']['kind']['enum']:
                            raise ValueError('Invalid discovery kind')
                        parent = nodes.get(finding['parent_id'])
                        if finding['parent_id'] and (parent is None or parent.role != 'support'):
                            raise ValueError('Discovery parent must be an existing support')
                        if finding['kind'] == 'nested_evidence' and parent is None:
                            raise ValueError('Nested evidence needs an existing support parent')
                        if not all(finding[k].strip() for k in ('evidence', 'rationale')):
                            raise ValueError('Hypothesis needs visual grounding and rationale')
                        if finding['kind'] in ('missing_evidence', 'nested_evidence') and not all(
                                finding[k].strip() for k in ('question', 'criteria')):
                            raise ValueError('Evidence hypothesis needs a focused executable question')
                        result['findings'].append({**finding, **identity, 'execution_ref': ref, 'status': 'hypothesis'})
                    except (ValueError, KeyError, TypeError) as exc:
                        result['failures'].append({**identity, 'execution_ref': ref, 'finding': finding, 'error': str(exc)})
            except (CallFailure, ValueError, KeyError, TypeError) as exc:
                result['failures'].append({**identity, 'error': str(exc), 'failure': type(exc).__name__})
        return result
