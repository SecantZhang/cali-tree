"""Independent checks, exact observation caching and single-slot transport recovery."""
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from critical.core.decision.artifacts import digest
from critical.core.decision.calls import CallFailure

class IndependentExecutor:
    def __init__(self,checker,*,checkpoint=None,max_checks=4,validator,
                 observation_states=('pass','fail','unknown'),observation_fields=()):
        if max_checks!=4:raise ValueError('Counting execution cap is four')
        self.checker,self.checkpoint,self.max_checks=checker,checkpoint,max_checks;self.cache={};self.validate=validator
        self.observation_states,self.observation_fields=observation_states,observation_fields
    def execute(self,p,evidence,*,repeat='0',final=False):
        self.validate(p);evidence={k:evidence[k] for k in ('source_image','edited_image')}
        images={k:sha256(Path(v).read_bytes()).hexdigest() for k,v in evidence.items()}
        observations=[];transitions=[]
        applicable_req={rid for o in p.outcomes if o.applicability=='applicable' for rid in o.requirement_ids}
        unknown_req={rid for o in p.outcomes if o.applicability=='unknown' for rid in o.requirement_ids}
        for n in p.nodes:
            applicable=n.requirement_id in applicable_req and n.requirement_id not in unknown_req
            obs={'check_id':n.id,'status':'unknown','valid':False,'eligible':applicable,'queried':False,'confidence':None,
                'evidence':'Declared applicability does not establish an applicable decision' if not applicable else '',
                'event':'applicability_skip' if not applicable else '', 'completion_tokens':0,'execution_ref':'','failure':None,'dependencies':[]}
            if applicable:
                key=digest([p.ref,self.checker.identity,images,n.id,str(repeat),final])
                if key in self.cache:obs=self.cache[key]
                elif self.checkpoint is not None and self.checkpoint.has('count-observe:'+key):obs=self.checkpoint.get('count-observe:'+key)
                else:
                    obs.update(queried=True,execution_ref=key)
                    try:
                        row=self.checker.check(p,n,evidence,slot=f'{repeat}/{n.id}',final=final)
                        obs.update(execution_ref=row.get('execution_ref',key),completion_tokens=int(row.get('completion_tokens',0)))
                        if row.get('status') not in self.observation_states or not isinstance(row.get('evidence'),str) or not row['evidence'].strip():raise ValueError('Invalid independent observation')
                        confidence=row.get('confidence')
                        if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:confidence=None
                        obs.update(status=row['status'],valid=True,evidence=row['evidence'],confidence=confidence,
                            event='valid_uncertainty' if row['status']=='unknown' else 'observed')
                        obs.update({k:row.get(k) for k in self.observation_fields})
                    except (CallFailure,ValueError,TypeError,KeyError) as exc:
                        obs.update(event='invalid_response',evidence=str(exc),failure=type(exc).__name__)
                        if isinstance(exc,CallFailure):
                            obs.update(event='transport_failure',completion_tokens=1024)
                            keys=re.findall(r'\b[a-f0-9]{64}\b',str(exc));path=self.checker.calls.directory/'jobs'/f'{keys[0]}.json' if keys else None
                            job=json.loads(path.read_text()) if path and path.exists() else {}
                            if job.get('outcome')=='invalid':obs['event']='invalid_response'
                            if job.get('response'):obs['completion_tokens']=int(job['response'].get('completionTokens',1024))
                            if job.get('execution_ref'):obs['execution_ref']=job['execution_ref']
                    self.cache[key]=obs
                    if self.checkpoint is not None:self.checkpoint.put('count-observe:'+key,obs)
            observations.append(obs);transitions.append({'node':n.id,'parent':'','activation':None,'eligible':applicable,'state':obs['status'],'event':obs['event']})
        return self.aggregate(p,observations,transitions)


class TransportRecoveryMixin:
    def recover_transport(self,p,evidence,trace,index,*,repeat,final):
        """A new single-attempt slot for ONE failed check; all other observations stay exact."""
        self.validate(p)
        if trace['program_ref']!=p.ref:raise ValueError('Recovery program mismatch')
        original=trace['observations'][index]
        if original['event']!='transport_failure':raise ValueError('Only transport failures qualify; never replace valid wrong/uncertain answers')
        n=p.nodes[index]
        if original['check_id']!=n.id:raise ValueError('Recovery check mismatch')
        recovered=deepcopy(original);recovered.update(execution_ref='',failure=None,completion_tokens=0)
        try:
            row=self.checker.check(p,n,evidence,slot=repeat+'/'+n.id,final=final)
            recovered.update(execution_ref=row['execution_ref'],completion_tokens=row['completion_tokens'])
            if row.get('status') not in self.observation_states or not isinstance(row.get('evidence'),str) or not row['evidence'].strip():raise ValueError('Invalid recovery observation')
            c=row.get('confidence');c=c if type(c) in (int,float) and math.isfinite(c) and 0<=c<=1 else None
            recovered.update(status=row['status'],valid=True,evidence=row['evidence'],confidence=c,
                event='valid_uncertainty' if row['status']=='unknown' else 'observed')
            recovered.update({k:row.get(k) for k in self.observation_fields})
        except CallFailure as exc:
            keys=re.findall(r'\b[a-f0-9]{64}\b',str(exc));path=self.checker.calls.directory/'jobs'/f'{keys[0]}.json' if keys else None
            job=json.loads(path.read_text()) if path and path.exists() else {}
            recovered.update(status='unknown',valid=False,confidence=None,evidence=str(exc),failure='CallFailure',
                event='invalid_response' if job.get('outcome')=='invalid' else 'transport_failure',
                execution_ref=job.get('execution_ref',''),completion_tokens=int((job.get('response') or {}).get('completionTokens',1024)))
        except (ValueError,TypeError,KeyError) as exc:
            recovered.update(status='unknown',valid=False,confidence=None,evidence=str(exc),failure=type(exc).__name__,event='invalid_response')
        recovered['attempts']=[deepcopy(original),deepcopy(recovered)]
        recovered['completion_tokens']+=original['completion_tokens']
        observations=deepcopy(trace['observations']);observations[index]=recovered
        transitions=deepcopy(trace['transitions']);transitions[index].update(state=recovered['status'],event=recovered['event'])
        result=self.aggregate(p,observations,transitions)
        if 'counting' in result:result['counting']['partial_representable']=result['counting']['total']>1
        return result
