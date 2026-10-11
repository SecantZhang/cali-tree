"""Source pinning, original requirement conversion and durable failure replay."""
from hashlib import sha256
import inspect
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def code_hashes():
    """Capture active and compatibility sources so a fresh run can pin both."""
    folders=('critical/core/decision','critical/core/optimization/program',
             'critical/core/optimization/prompt/calitree','critical/lm_engine')
    files={ROOT/'critical/checkpoint.py',Path(__file__),ROOT/'run/calitree_fulfillment.py'}
    for folder in folders:
        files.update((ROOT/folder).rglob('*.py'))
    files.update((ROOT/'critical/core/prompts/templates').rglob('*.txt'))
    # Historical run exports and frozen-workspace construction remain replayable.
    files.update(ROOT/p for p in ('run/calitree_adaptive_leaf.py','run/legacy/calitree_adaptive_leaf.py',
        'run/calitree_resume_frozen.py','run/calitree_resume_typed_twelve.py'))
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def bridge_reference(artifact):
    """Explicit v2 -> v3 compilation reference; never reinterpret saved inference."""
    from critical.core.decision.artifacts import restore_program as restore_legacy
    from critical.core.decision.robust.models import RobustProgram, Node, GATES
    from critical.core.decision.robust.compiler import template as runtime_template
    p=restore_legacy(artifact)
    if len(p.outcomes)!=1:raise ValueError('Twelve-case study needs one original requested outcome')
    supports=[c for c in p.checks if c.role=='support'];requested=[c for c in p.checks if c.role=='requested']
    if len(requested)!=1:raise ValueError('Need exactly one original fulfillment check')
    nodes=[]
    for c in (*supports,*requested):
        criteria=(f'pass: {c.complete_when}; fail: {c.absent_when}; unknown: {c.unknown_when}; '
                  f'incomplete evidence: {c.partial_when}' if c.role=='support' else
                  f'complete: {c.complete_when}; partial: {c.partial_when}; absent: {c.absent_when}; unknown: {c.unknown_when}')
        outcome=p.outcomes[0]
        nodes.append(Node(c.id,c.role,c.outcome_id if c.role=='requested' else '',nodes[-1].id if nodes else '',
            GATES if nodes else (),c.dependencies,c.question,criteria,
            f'Target: {outcome.target}. Reference: {outcome.reference}.'))
    result=RobustProgram(p.instruction,p.rubric,p.requirements,p.outcomes,tuple(nodes),runtime_template('check'))
    result.ref  # validate identity, ancestor references and frozen coverage
    return result

def status_for(report, audit, policy):
    assessment = policy.assess(report, audit)
    if assessment['qualified']:
        return 'locally_robust', assessment
    reasons = assessment['reasons']
    status = ('unresolved' if 'unresolved' in reasons or 'semantic_audit' in reasons else
              'insufficient_evidence' if any('insufficient' in r for r in reasons) else
              ('stable_but_mismatched' if report.get('label_consistency') == 1 else 'unstable_and_mismatched')
              if 'target_mismatch' in reasons else 'label_matched_but_unstable')
    if 'target_mismatch' in reasons and report.get('label_consistency') == 1 and audit.get('accepted'):
        assessment['reference_conflict_suspected'] = True
    return status, assessment

def install_failure_replay():
    """Preserve historical diagnostics so downstream request hashes replay exactly.

    This changes no execution, prompt or schema. No request is retried: a retained
    transport failure raises the same diagnostic as its original failed attempt.
    """
    from critical.core.decision.calls import DurableCalls,CallFailure
    from critical.core.decision.calls import ProviderStopped
    from critical.core.decision.artifacts import digest
    original=DurableCalls.call
    if getattr(original,'historical_diagnostics',False):return
    signature=inspect.signature(original)
    def call(self,*args,**kwargs):
        bound=signature.bind(self,*args,**kwargs);bound.apply_defaults();values=bound.arguments
        if not hasattr(self,'_inherited_logical_slots'):
            slots={};path=self.directory/'initial_budget.json'
            existing=json.loads(path.read_text()) if path.exists() else self.budget
            if existing:
                for key in existing.get('attempted_slots',[]):
                    job=self.directory/'jobs'/f'{key}.json'
                    if job.exists():
                        row=json.loads(job.read_text())
                        slots.setdefault((row['case_id'],row['stage'],row['slot']),set()).add(key)
            self._inherited_logical_slots=slots
        logical=(values['case_id'],values['stage'],values['slot'])
        inherited=self._inherited_logical_slots.get(logical)
        if inherited:
            identity=self.identity if values['route'] is None else self.routes[values['route']]['identity']
            media=[{'type':m['type'],'sha256':fingerprint(m['path'])} if m['type']=='image' else m for m in values['media']]
            key=digest([identity,values['case_id'],values['stage'],values['payload'],values['schema'],
                        values['template'],media,values['slot'],values['max_tokens']])
            if values['route'] is not None:key=digest([key,values['route']])
            if key not in inherited:
                raise ProviderStopped('Replay divergence at previously attempted logical slot: '+str(logical))
        try:return original(self,*args,**kwargs)
        except CallFailure as exc:
            prefix='Retained transport_error slot '
            if str(exc).startswith(prefix):
                key=str(exc)[len(prefix):]
                row=json.loads((self.directory/'jobs'/f'{key}.json').read_text())
                raise CallFailure(f"Transport failure in slot {key}: {row['error']}") from exc
            invalid='Retained invalid slot '
            if str(exc).startswith(invalid):
                raise CallFailure('Invalid model response in slot '+str(exc)[len(invalid):]) from exc
            raise
    call.historical_diagnostics=True
    DurableCalls.call=call
