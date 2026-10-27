"""One-shot local cache audit, frozen semantic comparison and optional verification.

Never launches observation or API calls, retries failed collection, changes a
serving default or marks the user's objective complete.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from critical.core.decision.artifacts import save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_semantic_rubric_v70 import ROOT, read


def run(cache, previous, previous_audit, out, cache_audit, study, policy_audit):
    if out.exists() or cache_audit.exists() or study.exists() or policy_audit.exists():
        raise ValueError('Fresh supervisor and downstream outputs required')
    out.mkdir(parents=True); (out/'llm-histories.log').write_text('No observer, encoder, API or reserved-source calls; offline downstream supervision only.\n')
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True); shutil.copyfile(__file__, snapshot)
    paths = [Path(__file__), ROOT/'run/verify_calitree_high_resolution_cache_v109.py', ROOT/'run/verify_calitree_local_review_cache_v98.py',
             ROOT/'run/calitree_local_score_v102.py', ROOT/'run/verify_calitree_semantic_residual_v105.py', ROOT/'critical/core/calibration/semantic_residual_v103.py',
             ROOT/'critical/core/calibration/semantic_residual_runtime_v104.py', ROOT/'critical/core/optimization/prompt/calitree/semantic_residual_judge_v104.py']
    code = {str(p): file_hash(p) for p in paths}
    protocol = {'version':'high-resolution-local-pipeline-v110', 'cache':str(cache), 'previous':str(previous), 'previous_audit':str(previous_audit),
        'cache_audit':str(cache_audit), 'study':str(study), 'policy_audit':str(policy_audit), 'baseline_verified_correct':227,
        'selection':'Only guarded arms are eligible. Choose higher correct, fewer losses, smaller depth, lexical name. Audit only if strictly above227; no automatic serving or goal-status change.',
        'code_sha256':code, 'new_observer_calls':0, 'new_api_calls':0, 'reserved_sources_used':0}
    save_json(out/'protocol.json', protocol)
    def state(stage, **extra):
        save_json(out/'state.json', {'stage':stage, 'updated_utc':datetime.now(timezone.utc).isoformat(), **extra})
        with (out/'run.log').open('a') as f:
            f.write(stage+' '+str(extra)+'\n')
    def check_code():
        for path, sha in code.items():
            assert file_hash(path)==sha, 'Supervised code changed: '+path
    def command(stage, module, args):
        check_code(); state(stage)
        env = os.environ.copy(); env['PYTHONPATH']='/tmp/calitree-catboost-v62:.'
        with (out/(stage+'.log')).open('x') as log:
            subprocess.run([sys.executable,'-u','-m',module,*args], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    state('waiting_for_collection', saved=len(list((cache/'responses').glob('*.json'))))
    try:
        while not (cache/'results.json').exists():
            if (out/'stop_requested.json').exists():
                state('stopped_before_fitting'); return
            time.sleep(30)
            # Heartbeat is a live read, never an instruction to resume a collector.
            save_json(out/'state.json', {'stage':'waiting_for_collection', 'saved':len(list((cache/'responses').glob('*.json'))), 'updated_utc':datetime.now(timezone.utc).isoformat()})
        result=read(cache/'results.json')
        if not result['complete']:
            state('collection_incomplete', result=result); return
        command('cache_audit','run.verify_calitree_high_resolution_cache_v109',['--previous-cache',str(previous),'--previous-audit',str(previous_audit),'--cache',str(cache),'--output-dir',str(cache_audit),'--require-complete'])
        command('semantic_comparison','run.calitree_local_score_v102',['--cache',str(cache),'--cache-audit',str(cache_audit),'--output-dir',str(study),'--method','tree_residual'])
        results=read(study/'results.json'); eligible=[k for k in results if k.endswith('_guarded')]
        selected=min(eligible,key=lambda k:(-results[k]['accuracy']['correct'],results[k]['losses'],int(k.split('_depth')[1].split('_')[0]),k))
        if results[selected]['accuracy']['correct']>227:
            command('policy_audit','run.verify_calitree_semantic_residual_v105',['--cache',str(cache),'--cache-audit',str(cache_audit),'--study',str(study),'--output-dir',str(policy_audit),'--candidate',selected])
            verification=read(policy_audit/'verification.json'); assert verification['passed']
            state('complete', candidate=selected, verified=verification, promotion_performed=False)
        else:
            state('complete', candidate=selected, result=results[selected], policy_audit_skipped='No improvement over verified227/276.',promotion_performed=False)
    except Exception as exc:
        state('failed', error=type(exc).__name__+': '+str(exc)); raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cache','previous','previous-audit','output-dir','cache-audit','study','policy-audit'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); run(a.cache.resolve(),a.previous.resolve(),a.previous_audit.resolve(),a.output_dir.resolve(),a.cache_audit.resolve(),a.study.resolve(),a.policy_audit.resolve())
