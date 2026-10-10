"""Independent scheduling and explicit advisory/required evidence semantics."""
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from critical.core.decision.artifacts import digest
from critical.core.decision.calls import CallFailure
from critical.core.decision.compiler import array, object_schema, TEXT, media_inputs
from .executor import OBS_SCHEMA, reduced
from .models import STATES, GATES
from .v4_models import validate


class EvidenceChecker:
    def __init__(self, calls):
        self.calls = calls
        self.identity = {'provider': calls.identity, 'checker': 'typed-evidence-v2', 'scope': getattr(calls,'case_id',None)}

    def check(self, program, node, outcome, evidence, dependencies, *, slot, final=False):
        schema = object_schema({**OBS_SCHEMA['properties'], 'used_dependency_ids': array(TEXT)})
        value, ref = self.calls.call('check_v4', {'instruction':program.instruction,'rubric':program.rubric,
            'node':asdict(node),'outcome':asdict(outcome) if outcome else None,'dependencies':dependencies}, schema,
            template=program.checker_template, media=media_inputs(evidence) if node.role=='support' else (),
            slot=slot, final=final, max_tokens=1024)
        job = json.loads((self.calls.directory/'jobs'/f'{ref}.json').read_text())
        row = {**value,'execution_ref':ref,'completion_tokens':int(job['response'].get('completionTokens',1024))}
        if value.get('used_dependency_ids') != list(node.dependencies):
            row.update(status='invalid_dependency_consumption',evidence='Declared context was not acknowledged in saved order')
        return row


class EvidenceExecutor:
    def __init__(self, checker, *, checkpoint=None, max_checks=4):
        if max_checks != 4: raise ValueError('V4 execution cap is four')
        self.checker,self.checkpoint,self.max_checks = checker,checkpoint,max_checks
        self.cache = {}

    def execute(self, program, evidence, *, repeat='0', final=False):
        validate(program)
        evidence = {k:evidence[k] for k in ('source_image','edited_image')}
        hashes = {k:sha256(Path(v).read_bytes()).hexdigest() for k,v in evidence.items()}
        observed, transitions = {}, []
        accounted = {o.id:{'status':'unknown','applicability':o.applicability,'source':'unresolved',
                           'reason':'Fulfillment has not been established'} for o in program.outcomes}
        outs = {o.id:o for o in program.outcomes}
        for node in program.nodes:
            outcome = outs.get(node.outcome_id)
            reason, event = '', ''
            if node.activation and observed[node.activation.check_id]['status'] not in node.activation.states:
                reason,event = 'Saved activation condition not satisfied','conditional_skip'
            elif outcome and outcome.applicability != 'applicable':
                reason,event = 'Declared applicability: '+outcome.applicability,'applicability_skip'
            elif any(not observed[d]['valid'] or observed[d]['status']=='unknown' for d in node.required_dependencies):
                reason,event = 'Unknown required evidence dependency','required_dependency_block'
            # Invalid/absent context is supplied honestly, without internal exception text.
            context = [{'check_id':d,'status':observed[d]['status'],'valid':observed[d]['valid'],
                        'queried':observed[d]['queried'],'evidence':observed[d]['evidence'] if observed[d]['valid'] else 'No valid observation: '+observed[d]['event'],
                        'confidence':observed[d]['confidence']} for d in node.dependencies]
            obs = {'check_id':node.id,'status':'unknown','evidence':reason,'valid':False,'eligible':not bool(event),
                   'queried':False,'confidence':None,'completion_tokens':0,'dependencies':context,
                   'event':event,'failure':None,'execution_ref':''}
            if not event:
                key = digest([program.ref,self.checker.identity,hashes,node.id,context,str(repeat),final])
                if key in self.cache: obs = self.cache[key]
                elif self.checkpoint is not None and self.checkpoint.has('v4-observe:'+key):
                    obs = self.checkpoint.get('v4-observe:'+key)
                else:
                    obs.update(queried=True,execution_ref=key)
                    try:
                        value = self.checker.check(program,node,outcome,evidence,context,slot=f'{repeat}/{node.id}',final=final)
                        obs.update(completion_tokens=int(value.get('completion_tokens',0)),execution_ref=value.get('execution_ref',key))
                        if value.get('status') not in (STATES if node.role=='requested' else GATES) or not isinstance(value.get('evidence'),str) or not value['evidence'].strip():
                            raise ValueError('Invalid atomic observation or dependency acknowledgment')
                        confidence = value.get('confidence')
                        if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0 <= confidence <= 1: confidence = None
                        obs.update(status=value['status'],evidence=value['evidence'],confidence=confidence,valid=True,
                                   event='valid_uncertainty' if value['status']=='unknown' else 'observed')
                    except (CallFailure, ValueError, KeyError, TypeError) as exc:
                        obs.update(evidence=str(exc),failure=type(exc).__name__,event='invalid_response')
                        if isinstance(exc,CallFailure):
                            obs['completion_tokens']=1024
                            keys=re.findall(r'\b[a-f0-9]{64}\b',str(exc))
                            path=self.checker.calls.directory/'jobs'/f'{keys[0]}.json' if keys else None
                            job=json.loads(path.read_text()) if path and path.exists() else {}
                            obs['event']='invalid_response' if job.get('outcome')=='invalid' or 'Invalid model response' in str(exc) else 'transport_failure'
                            obs['execution_ref']=job.get('execution_ref',obs['execution_ref'])
                            if job.get('response'):obs['completion_tokens']=int(job['response'].get('completionTokens',1024))
                    self.cache[key]=obs
                    if self.checkpoint is not None:self.checkpoint.put('v4-observe:'+key,obs)
            observed[node.id]=obs
            transitions.append({'node':node.id,'parent':node.parent,'activation':asdict(node.activation) if node.activation else None,
                'eligible':obs['eligible'],'state':obs['status'],'event':obs['event'],'skip_reason':reason})
            if node.role=='requested':
                accounted[node.outcome_id]={'status':obs['status'],'applicability':outcome.applicability,
                    'source':'queried' if obs['valid'] else 'unresolved','reason':obs['evidence']}
        values = [v['status'] if v['applicability']=='applicable' else 'unknown' for v in accounted.values() if v['applicability']!='not_applicable']
        state = reduced(values)
        requirements = {}
        for r in program.requirements:
            rows=[accounted[o.id] for o in program.outcomes if r.id in o.requirement_ids and accounted[o.id]['applicability']!='not_applicable']
            requirements[r.id]=reduced([v['status'] if v['applicability']=='applicable' else 'unknown' for v in rows]) if rows else 'not_applicable'
        return {'program_ref':program.ref,'label':{'complete':'yes','partial':'partial','absent':'no'}.get(state),
            'resolved':state!='unknown','outcomes':accounted,'requirements':requirements,
            'observations':list(observed.values()),'transitions':transitions}
