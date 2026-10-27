"""One-shot completion audit and frozen source-held32B policy comparison.

Never launches/restarts an observer, retries missing slots, promotes a policy
or changes goal status. An improved score still needs a bound runtime audit.
"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_semantic_rubric_v70 import ROOT,read


def run(cache,out,cache_audit,study,vision_python):
    if any(p.exists() for p in(out,cache_audit,study)):raise ValueError('Fresh pipeline outputs required')
    out.mkdir(parents=True);(out/'llm-histories.log').write_text('No observer/API/encoder calls. Downstream cache audit and offline classifier fitting only.\n')
    files=[Path(__file__),ROOT/'run/calitree_large_review_cache_v132.py',ROOT/'run/verify_calitree_large_cache_v134.py',ROOT/'run/calitree_large_semantic_policy_v135.py',
        ROOT/'run/verify_calitree_large_probe_v130.py',ROOT/'run/verify_calitree_semantic_residual_v105.py',ROOT/'critical/core/calibration/decision_flow_strength_v133.py',
        ROOT/'critical/core/calibration/semantic_residual_v103.py',ROOT/'critical/core/calibration/local_warranted_rubric_v97.py',
        ROOT/'critical/lm_engine/local_mlx_large_v128.py',ROOT/'critical/lm_engine/local_mlx_v118.py',ROOT/'critical/core/decision/bounded_local_schema_v131.py']
    hashes={str(p):file_hash(p) for p in files}
    for p in files:
        target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    save_json(out/'protocol.json',{'version':'large-policy-pipeline-v136','cache':str(cache),'cache_audit':str(cache_audit),'study':str(study),
        'code_sha256':hashes,'baseline_verified_correct':227,'required_correct':235,
        'flow':'Wait for terminal collection, require a complete v134 audit, then run exactly the eight v135 native-fit configurations and three predefined guard/score modes. No observer calls or automatic policy/goal promotion.',
        'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0})
    def state(stage,**extra):
        value={'stage':stage,'updated_utc':datetime.now(timezone.utc).isoformat(),**extra};save_json(out/'state.json',value)
        with(out/'run.log').open('a') as f:f.write(stage+' '+str(extra)+'\n')
    def command(stage,python,module,args):
        for path,sha in hashes.items():assert file_hash(path)==sha,'Frozen downstream source changed: '+path
        state(stage);env=os.environ.copy();env['PYTHONPATH']='/tmp/calitree-catboost-v62:.' if python==sys.executable else '.'
        env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
        with(out/(stage+'.log')).open('x') as log:subprocess.run([python,'-u','-m',module,*args],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    state('waiting_for_collection',saved=len(list((cache/'responses').glob('*.json'))))
    try:
        while not(cache/'results.json').exists():
            if(out/'stop_requested.json').exists():state('stopped_before_fitting');return
            time.sleep(30)
            save_json(out/'state.json',{'stage':'waiting_for_collection','updated_utc':datetime.now(timezone.utc).isoformat(),'saved':len(list((cache/'responses').glob('*.json')))})
        terminal=read(cache/'results.json')
        if not terminal['complete']:state('collection_incomplete',result=terminal);return
        command('cache_audit',str(vision_python),'run.verify_calitree_large_cache_v134',['--cache',str(cache),'--output-dir',str(cache_audit),'--require-complete'])
        command('semantic_comparison',sys.executable,'run.calitree_large_semantic_policy_v135',['--cache',str(cache),'--cache-audit',str(cache_audit),'--output-dir',str(study)])
        selected=read(study/'selection.json');assert not selected['verified']
        state('complete',selected=selected,needs_independent_runtime_audit=selected['result']['accuracy']['correct']>227,promotion_performed=False,goal_status_changed=False)
    except Exception as exc:state('failed',error=type(exc).__name__+': '+str(exc));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','output-dir','cache-audit','study'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--vision-python',type=Path,default=Path('/tmp/calitree-mlx-v116/bin/python'));a=p.parse_args();run(a.cache.resolve(),a.output_dir.resolve(),a.cache_audit.resolve(),a.study.resolve(),a.vision_python)
