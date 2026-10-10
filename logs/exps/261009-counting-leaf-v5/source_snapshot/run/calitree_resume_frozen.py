"""Explicitly authorized continuation of a transport-stopped frozen experiment.

Copy the complete durable ledger, release only its transport-stop latch, and
execute its exact frozen sources. Failed slots and all usage remain charged.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from critical.core.decision.artifacts import save_json

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError('Continuation needs a separate directory')
    manifest = json.loads((source/'manifest.json').read_text())
    budget = json.loads((source/'budget.json').read_text())
    result = json.loads((source/'results.json').read_text())
    if budget['stopped'] != 'Three consecutive transport failures' or result['status'] != 'stopped':
        raise ValueError('Only a transport-stopped experiment can be explicitly continued')
    if manifest['model'] != 'gpt-6-luna' or manifest['provider'] != 'openai':
        raise ValueError('This continuation preserves the approved OpenAI GPT-6 Luna configuration')
    required = ['manifest.json','budget.json','results.json','observations.jsonl']
    for folder in ('prepared','frozen','jobs','source_snapshot'):
        required += [str(p.relative_to(source)) for p in sorted((source/folder).rglob('*')) if p.is_file()]
    for i,case in enumerate(manifest['cases']):
        for arm in manifest['arms']:
            path = source/'frozen'/arm/f'{i}.json'
            local = json.loads(path.read_text())
            if 'nodes' not in local or 'leaf:'+case['id'] not in local['nodes']:
                raise ValueError('All case-arm selections must already be frozen')
    record = {'version':'authorized-frozen-continuation-v1','source':str(source),
        'authorization':'User explicitly requested continue after the reported transport stop.',
        'hashes':{relative:fingerprint(source/relative) for relative in required},
        'inherited_calls':budget['calls'],'inherited_charged_tokens':budget['completion_tokens_or_reserved'],
        'remaining_calls':budget['limits']['max_calls']-budget['calls'],
        'remaining_completion_tokens':budget['limits']['max_completion_tokens']-budget['completion_tokens_or_reserved'],
        'failed_slots_retried':False,'search_reopened':False,'configuration_changed':False}
    if (output/'continuation.json').exists():
        if json.loads((output/'continuation.json').read_text()) != record:
            raise ValueError('Source accounting, selections or configuration changed on resume')
        for folder in ('prepared','frozen','source_snapshot'):
            for relative,expected in record['hashes'].items():
                if relative.startswith(folder+'/') and fingerprint(output/relative) != expected:
                    raise ValueError('Frozen continuation assets changed')
        if fingerprint(output/'manifest.json') != record['hashes']['manifest.json']:
            raise ValueError('Frozen continuation manifest changed')
        current=json.loads((output/'budget.json').read_text())
        prior_slots=budget.get('attempted_slots',[])
        if current['limits'] != budget['limits'] or current.get('attempted_slots',[])[:len(prior_slots)] != prior_slots:
            raise ValueError('Inherited durable protocol or slots changed')
        for field in ('calls','completion_tokens_or_reserved','input_tokens','final_calls','final_tokens'):
            if current.get(field,0)<budget.get(field,0):
                raise ValueError('Inherited accounting was rolled back')
        for scope,counts in budget.get('cases',{}).items():
            if any(current.get('cases',{}).get(scope,{}).get(phase,0)<counts.get(phase,0) for phase in ('search','final')):
                raise ValueError('Inherited case accounting was rolled back')
        for relative,expected in record['hashes'].items():
            if relative.startswith('jobs/') and fingerprint(output/relative)!=expected:
                raise ValueError('Attempted slot history changed')
        return record
    if output.exists():
        raise ValueError('New continuation directory must not already exist')
    shutil.copytree(source, output, ignore=shutil.ignore_patterns('llm-histories.log','console.log','textgrad-v3'))
    save_json(output/'initial_budget.json',budget)
    save_json(output/'initial_results.json',result)
    resumed = {**budget,'stopped':None,'consecutive_errors':0,
        'authorized_resumes':[*budget.get('authorized_resumes',[]),
            {'source':str(source),'stop':budget['stopped'],'consecutive_errors':budget['consecutive_errors'],
             'calls':budget['calls'],'completion_tokens_or_reserved':budget['completion_tokens_or_reserved']}]}
    save_json(output/'budget.json',resumed)
    save_json(output/'continuation.json',record)
    return record


def frozen_workspace(output, destination):
    """Restore pinned execution code; no credentials or image files are copied."""
    output, destination = Path(output).resolve(), Path(destination).resolve()
    manifest = json.loads((output/'manifest.json').read_text())
    ignored = shutil.ignore_patterns('__pycache__','.DS_Store','*.pyc')
    for folder in ('critical','run'):
        shutil.copytree(ROOT/folder,destination/folder,ignore=ignored)
    for relative,expected in manifest['code_hashes'].items():
        source = output/'source_snapshot'/relative
        if fingerprint(source) != expected:
            raise ValueError('Frozen source hash mismatch')
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    for path in (destination/'critical/core/prompts/templates/forced_decomposition_v1').glob('*.txt'):
        if str(path.relative_to(destination)) not in manifest['code_hashes']:
            path.unlink()
    historical='logs/exps/261007-robust-hard-cases-v3'
    (destination/historical).mkdir(parents=True)
    shutil.copyfile(ROOT/historical/'manifest.json',destination/historical/'manifest.json')
    shutil.copytree(ROOT/historical/'prepared',destination/historical/'prepared')


def run_frozen(output, *, live=False):
    output=Path(output).resolve()
    with tempfile.TemporaryDirectory() as temporary:
        clone=Path(temporary).resolve()/'repository';clone.mkdir()
        frozen_workspace(output,clone)
        if live:
            # Credential discovery uses the original private settings; neither the
            # key nor settings file is copied into the frozen workspace/artifact.
            code = """import sys
from pathlib import Path
import critical.config as cfg
import os
cfg.PROJECT_ROOT=Path(sys.argv[1])
cfg.CREDENTIALS_FILE=Path(os.environ.get('CRITICAL_CREDENTIALS_FILE','').strip() or str(cfg.PROJECT_ROOT/'.interface_credentials.json'))
from run.calitree_forced_decomposition import main
output=sys.argv[2]
sys.argv=['frozen-runner','--live','--resume','--output-dir',output]
main()
"""
        else:
            code = """import json,sys
from pathlib import Path
from run.calitree_forced_decomposition import preflight
manifest=preflight(Path(sys.argv[2]))
print(json.dumps({'status':'frozen-preflight-passed','cases':len(manifest['cases'])}))
"""
        child=subprocess.run([str(ROOT/'.venv/bin/python'),'-c',code,str(ROOT),str(output)],
            cwd=clone,env={**os.environ,'PYTHONPATH':str(clone)})
        if child.returncode:
            raise RuntimeError('Frozen runner failed; retained all durable state')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--preflight',action='store_true');modes.add_argument('--live',action='store_true')
    args=parser.parse_args()
    record=prepare(args.source,args.output_dir)
    print(json.dumps({k:record[k] for k in ('remaining_calls','remaining_completion_tokens','inherited_calls')}),flush=True)
    run_frozen(args.output_dir,live=args.live)


if __name__=='__main__':main()
