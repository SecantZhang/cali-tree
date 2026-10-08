"""Shared genome, validation and confirmation policy for external optimizers."""
from copy import deepcopy
from dataclasses import asdict
import json

from critical.core.decision.artifacts import export_program, program_ref, digest
from critical.core.decision.models import ProgramSpec
from critical.core.decision.compiler import GRAPH_SCHEMA, object_schema, TEXT, media_inputs
from critical.core.decision.calls import BudgetExhausted, CallFailure
from critical.core.optimization.program.models import LeafResult
from critical.core.optimization.program.evaluation import LocalAcceptance

FIELDS = ('requirements', 'outcomes', 'checks')
TEXT_SCHEMA = object_schema({'text': TEXT})
CONSTRAINTS = (
    'Optimize the executable JSON graph, not a final answer or a prompt wrapper. Return all three keys: requirements, outcomes, checks.',
    'Keep existing requirement IDs, text and exact source quotes unchanged. Add requirements only if supported by the original instruction.',
    'You may add/remove/split outcomes and checks, repair target/reference bindings, change applicability, and revise criteria or dependencies.',
    'Exactly one requested fulfillment check per outcome; support checks only provide evidence and never count as completed edits.',
    'At most four total checks. Preserve coverage of every requirement; do not omit edits to satisfy this cap.',
    'Every support must be used by a requested check in its own outcome. Dependencies must be acyclic support IDs. All graph IDs are unique.',
    'Do not prescribe the reference label, weaken the instruction, invent edits, or mark unsuccessful requested edits inapplicable.',
)

def encode(program):
    return json.dumps({k: program.to_dict()[k] for k in FIELDS}, sort_keys=True, ensure_ascii=False)

def decode(text, parent):
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError('Expected only requirements, outcomes and checks')
    program = ProgramSpec.from_dict({**parent.to_dict(), **value})
    by_id = {r.id: r for r in program.requirements}
    if any(by_id.get(r.id) != r for r in parent.requirements):
        raise ValueError('Required provenance was deleted or rewritten')
    return program

def structural_diff(parent, child):
    result = {}
    for field in FIELDS:
        old = {r['id']: r for r in parent.to_dict()[field]}
        new = {r['id']: r for r in child.to_dict()[field]}
        result[field] = {'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys()),
                         'changed': sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}
    result['outcome_mapping'] = {o.id: [n.id for n in child.outcomes if set(n.requirement_ids) & set(o.requirement_ids)]
                                 for o in parent.outcomes}
    return result

class LocalConvergence(Exception):
    """A candidate met the shared confirmation contract; no more search is needed."""

class ProgramTrial:
    def __init__(self, method, case, target, seed, compiler, evaluator):
        if target not in ('yes', 'partial', 'no') or case.instruction != seed.instruction:
            raise ValueError('Case, target and seed disagree')
        self.method, self.case, self.target, self.seed = method, case, target, seed
        self.compiler, self.evaluator = compiler, evaluator
        self.result = LeafResult(case.id, seed=export_program(seed), selected=export_program(seed))
        self.programs, self.reports, self.confirmed, self.audits = {}, {}, set(), {}
        self.evaluations = {}
        self.valid_texts = {}
        self.success = None
        self.policy = LocalAcceptance()

    def evaluate(self, text, parent_text=None):
        if text in self.valid_texts:
            return deepcopy(self.valid_texts[text])
        parent = decode(parent_text, self.seed) if parent_text else self.seed
        key = digest([text, program_ref(parent)])
        if key in self.evaluations:
            return deepcopy(self.evaluations[key])
        record = {'method': self.method, 'parent': program_ref(parent), 'genome': text}
        self.result.lineage.append(record)
        try:
            program = decode(text, parent)
        except (ValueError, TypeError, KeyError) as exc:
            feedback = {'score': -1.0, 'validation_error': str(exc), 'reference_label': self.target,
                        'instruction': self.case.instruction, 'constraints': CONSTRAINTS}
            record.update(valid=False, reason=str(exc))
            self.evaluations[key] = feedback
            return deepcopy(feedback)
        ref = program_ref(program)
        record.update(valid=True, program_ref=ref, diff=structural_diff(parent, program))
        if ref in self.reports:
            feedback = self.feedback(ref)
            self.evaluations[key] = feedback
            return deepcopy(feedback)
        self.programs[ref] = program
        candidate = export_program(program)
        self.result.candidates[ref] = candidate
        audit = self.compiler.audit(program, slot=f'{self.case.id}/audit/{ref}')
        candidate['audit'] = self.audits[ref] = audit
        report = self.evaluator.evaluate(program, self.case, self.target, repeats=1,
                         namespace=f'{self.case.id}/screen/{ref}')
        candidate['screen'] = self.reports[ref] = report
        if audit['accepted'] and report['agreement'] == 1 and report['coverage'] == 1:
            confirmation = self.evaluator.evaluate(program, self.case, self.target, repeats=3,
                              namespace=f'{self.case.id}/confirm/{ref}')
            candidate['confirmation'] = self.reports[ref] = confirmation
            self.confirmed.add(ref)
            if confirmation['agreement'] == 1 and confirmation['coverage'] == 1:
                self.success = ref
        feedback = self.feedback(ref)
        self.evaluations[key] = self.valid_texts[text] = feedback
        return deepcopy(feedback)

    def feedback(self, ref):
        report, audit = self.reports[ref], self.audits[ref]
        return {'score': report['agreement'] if audit['accepted'] else -1.0,
                'instruction': self.case.instruction, 'reference_label': self.target,
                'report': report, 'audit': audit, 'program_ref': ref, 'constraints': CONSTRAINTS}

    def finish(self, stop_reason):
        self.result.stop_reason = stop_reason
        base = program_ref(self.seed)
        eligible = [r for r in sorted(self.confirmed) if self.audits[r]['accepted']]
        choices = ([base] if base in self.reports else []) + eligible
        best = self.success or (max(choices, key=lambda r: self.policy.rank(self.reports[r], self.programs[r])) if choices else base)
        self.result.selected = export_program(self.programs.get(best, self.seed))
        report = self.reports.get(best)
        self.result.status = ('confirmed_local' if self.success else 'budget_limited' if stop_reason.startswith('budget') else
                              'unresolved' if not report or report['coverage'] < 1 else
                              'unstable' if report['flip_rate'] > 0 else 'unmatched')
        calls = getattr(self.compiler, 'calls', None)
        if calls is not None:
            self.result.usage = deepcopy(calls.budget.get('cases', {}).get(getattr(calls, 'case_id', self.case.id), {}))
        return self.result


def native_text_call(calls, case, target, seed, stage, prompt, system_prompt, *, slot, current_text):
    """Route every native algorithm call through the same capped durable provider."""
    row, _ = calls.call(stage, {'native_prompt': prompt, 'native_system_prompt': system_prompt,
             'instruction': case.instruction, 'rubric': seed.rubric, 'reference_label': target,
             'current_graph': current_text, 'graph_schema': GRAPH_SCHEMA, 'constraints': CONSTRAINTS}, TEXT_SCHEMA,
             template=('Execute the supplied optimizer prompt and system instructions. The optimized variable is an executable '
                       'decision graph. Honor the graph constraints. Source and edited images are attached for grounded feedback. '
                       'Return the native algorithm response verbatim in the JSON text field, including any requested delimiters.'),
             media=media_inputs(case.evidence), slot=slot, max_tokens=2048)
    if not isinstance(row.get('text'), str) or not row['text'].strip():
        raise ValueError('Empty native optimizer response')
    return row['text']
