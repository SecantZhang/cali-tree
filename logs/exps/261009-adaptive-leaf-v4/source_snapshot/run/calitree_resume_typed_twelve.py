"""Authorized continuation of a partially fitted, transport-stopped twelve-case run.

Use a separate directory, retain every attempted slot and frozen selection, and
execute the original pinned runtime. One invocation releases one stop only.
"""
from hashlib import sha256
import argparse
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from critical.core.decision.artifacts import save_json
from run.calitree_resume_frozen import ROOT, fingerprint, frozen_workspace


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


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError('Continuation needs a separate directory')
    manifest=json.loads((source/'manifest.json').read_text())
    budget=json.loads((source/'budget.json').read_text())
    results=json.loads((source/'results.json').read_text())
    if results['status']!='stopped' or budget['stopped']!='Three consecutive transport failures':
        raise ValueError('Only a transport-stopped experiment can be explicitly continued')
    if manifest['version']!='typed-evidence-twelve-v1' or manifest['model']!='gpt-6-luna' or manifest['provider']!='openai':
        raise ValueError('Wrong frozen twelve-case protocol')
    # Existing selections may include invalid seeds. Preserve them exactly;
    # unattempted fitting may proceed without reopening any frozen selection.
    immutable=['manifest.json','budget.json','results.json']
    for folder in ('prepared','frozen','jobs','source_snapshot','constructions'):
        immutable += [str(p.relative_to(source)) for p in sorted((source/folder).rglob('*')) if p.is_file()]
    observations=[str(p.relative_to(source)) for p in sorted((source/'observations').glob('*.jsonl'))]
    deviation_path=source/'protocol_deviations.json'
    inherited_deviations=json.loads(deviation_path.read_text()) if deviation_path.exists() else {}
    record={'version':'authorized-typed-twelve-continuation-v1','source':str(source),
        'authorization':'User explicitly requested resume the experiment after its reported transport stop.',
        'hashes':{rel:fingerprint(source/rel) for rel in immutable},
        'observation_prefixes':{rel:{'bytes':(source/rel).stat().st_size,'sha256':fingerprint(source/rel)} for rel in observations},
        'inherited_calls':budget['calls'],'inherited_charged_tokens':budget['completion_tokens_or_reserved'],
        'remaining_calls':budget['limits']['max_calls']-budget['calls'],
        'remaining_completion_tokens':budget['limits']['max_completion_tokens']-budget['completion_tokens_or_reserved'],
        'failed_slots_retried':False,'frozen_selections_reopened':False,'configuration_changed':False,
        'partial_search_continued':True,
        'replay_protocol':'historical-failure-diagnostics-v2-logical-slot-guard',
        'inherited_protocol_deviations':inherited_deviations,
        'continuation_runtime':{'run/calitree_resume_typed_twelve.py':fingerprint(__file__)}}
    if (output/'continuation.json').exists():
        if json.loads((output/'continuation.json').read_text())!=record:
            raise ValueError('Source accounting or frozen configuration changed')
        for rel,h in record['hashes'].items():
            if rel not in ('budget.json','results.json') and fingerprint(output/rel)!=h:
                raise ValueError('Inherited immutable asset changed: '+rel)
        for rel,expected in record['observation_prefixes'].items():
            if sha256((output/rel).read_bytes()[:expected['bytes']]).hexdigest()!=expected['sha256']:
                raise ValueError('Inherited observation prefix changed: '+rel)
        for rel,h in record['continuation_runtime'].items():
            if fingerprint(output/'continuation_snapshot'/rel)!=h:
                raise ValueError('Continuation runtime changed: '+rel)
        current=json.loads((output/'budget.json').read_text())
        slots=budget.get('attempted_slots',[])
        if current['limits']!=budget['limits'] or current.get('attempted_slots',[])[:len(slots)]!=slots:
            raise ValueError('Inherited limits or slots changed')
        for field in ('calls','completion_tokens_or_reserved','input_tokens','final_calls','final_tokens'):
            if current.get(field,0)<budget.get(field,0):raise ValueError('Inherited accounting rolled back')
        for scope,counts in budget.get('cases',{}).items():
            for phase in ('search','final','completion_tokens_or_reserved','input_tokens'):
                if current.get('cases',{}).get(scope,{}).get(phase,0)<counts.get(phase,0):
                    raise ValueError('Inherited scope accounting rolled back')
        return record  # A later stop stays latched; this is not another authorization.
    if output.exists():raise ValueError('New continuation directory must not already exist')
    shutil.copytree(source,output,ignore=shutil.ignore_patterns('llm-histories.log','console.log','textgrad-v3','__pycache__'))
    save_json(output/'initial_budget.json',budget)
    save_json(output/'initial_results.json',results)
    save_json(output/'initial_protocol_deviations.json',inherited_deviations)
    resumed={**budget,'stopped':None,'consecutive_errors':0,
        'authorized_resumes':[*budget.get('authorized_resumes',[]),
            {'source':str(source),'stop':budget['stopped'],'calls':budget['calls'],
             'consecutive_errors':budget['consecutive_errors'],
             'completion_tokens_or_reserved':budget['completion_tokens_or_reserved']}]}
    save_json(output/'budget.json',resumed);save_json(output/'continuation.json',record)
    target=output/'continuation_snapshot/run/calitree_resume_typed_twelve.py'
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(__file__,target)
    return record


def run_frozen(output, *, live=False):
    output=Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix='calitree-twelve-continuation-') as temporary:
        clone=Path(temporary)/'repository';clone.mkdir();frozen_workspace(output,clone)
        record=json.loads((output/'continuation.json').read_text())
        for rel,h in record['continuation_runtime'].items():
            source=output/'continuation_snapshot'/rel
            if fingerprint(source)!=h:raise ValueError('Continuation runtime changed: '+rel)
            target=clone/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        # Direct dispatch avoids rebuilding a new manifest or depending on a
        # temporary checkout's Git HEAD. Every executable source is hash pinned.
        code='''import hashlib,importlib.util,json,os,sys
from pathlib import Path
from run.calitree_typed_twelve import execute,bridge_reference
from run.calitree_resume_typed_twelve import install_failure_replay
root,output,live=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]=='live'
m=json.loads((output/'manifest.json').read_text())
for rel,h in m['code_hashes'].items():
    assert hashlib.sha256(Path(rel).read_bytes()).hexdigest()==h,rel
package=Path(importlib.util.find_spec('textgrad').origin).parent
for rel,h in m['dependencies']['hashes'].items():
    assert hashlib.sha256((package/rel).read_bytes()).hexdigest()==h,rel
for case in m['cases']:
    assert bridge_reference(case['legacy_seed']).ref==case['original']['program_ref']
    for key,path in case['evidence'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==case['image_hashes'][key]
if not live:
    print(json.dumps({'status':'frozen-preflight-passed','cases':len(m['cases'])}));sys.exit(0)
import critical.config as cfg
cfg.PROJECT_ROOT=root
cfg.CREDENTIALS_FILE=Path(os.environ.get('CRITICAL_CREDENTIALS_FILE','').strip() or str(root/'.interface_credentials.json'))
from critical.lm_engine import get_engine,load_creds,require_live
from critical.logging.llm_history import LLMHistoryWriter
require_live(True);creds=load_creds(engine='gpt',provider='openai')
assert creds.provider=='openai' and creds.endpoints==['https://api.openai.com/v1']
history=LLMHistoryWriter(output/'llm-histories.log')
install_failure_replay()
r=execute(output,m,lambda cap:get_engine('gpt',model=m['model'],creds=creds,history=history,
    max_tokens=cap,temperature=0,max_http_attempts=1,timeout=60))
print(json.dumps({'status':r['status'],'error':r.get('error'),'output':str(output)}))
'''
        child=subprocess.run([str(ROOT/'.venv/bin/python'),'-u','-c',code,str(ROOT),str(output),'live' if live else 'preflight'],
            cwd=clone,env={**os.environ,'PYTHONPATH':str(clone)})
        if child.returncode:raise RuntimeError('Frozen continuation failed; durable state retained')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--preflight',action='store_true');modes.add_argument('--live',action='store_true')
    args=parser.parse_args();record=prepare(args.source,args.output_dir)
    print(json.dumps({k:record[k] for k in ('remaining_calls','remaining_completion_tokens','inherited_calls')}),flush=True)
    run_frozen(args.output_dir,live=args.live)


if __name__=='__main__':main()
