"""One-shot cache completion -> strict audit -> fitting -> runtime verification.

This is a bounded dependency runner, not a recurring job or a collector retry.
It never changes serving defaults or claims the thread goal complete.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from critical.core.decision.artifacts import save_json

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def run(cache, out, cache_audit, study, policy_audit, timeout):
    if out.exists() or any(p.exists() for p in (cache_audit, study, policy_audit)):
        raise ValueError('Fresh dependency-runner and downstream outputs required')
    out.mkdir(parents=True); (out/'llm-histories.log').write_text('Zero model/API calls. This runner coordinates local audits and fitting only; it never restarts collection.\n')
    (out/'run.log').write_text('Waiting for the already-running frozen observation collector.\n')
    snapshot = out/'source_snapshot/run'/Path(__file__).name; snapshot.parent.mkdir(parents=True); shutil.copyfile(__file__, snapshot)
    save_json(out/'protocol.json', {'cache': str(cache), 'cache_audit': str(cache_audit), 'study': str(study), 'policy_audit': str(policy_audit),
                'max_wait_seconds': timeout, 'poll_seconds': 10, 'collection_retries': 0, 'new_model_calls': 0, 'serving_changed': False})
    state = {'stage': 'waiting_for_cache', 'complete': False, 'goal_complete': False}; save_json(out/'state.json', state)
    start = time.monotonic()
    try:
        while not (cache/'results.json').exists():
            if time.monotonic()-start > timeout:
                raise TimeoutError('Frozen collector has not produced a terminal result; no restart attempted')
            time.sleep(10)
        if not read(cache/'results.json')['complete']:
            raise ValueError('Collector stopped incomplete; no fitting or retry performed')
        def stage(label, module, args):
            state.update(stage=label); save_json(out/'state.json', state)
            command = [sys.executable, '-u', '-m', module, *map(str, args)]
            with (out/'run.log').open('a') as f:
                f.write('Starting '+label+': '+json.dumps(command)+'\n')
            print({'stage': label, 'command': command}, flush=True)
            subprocess.run(command, cwd=ROOT, check=True)
        stage('complete_cache_audit', 'run.verify_calitree_local_review_cache_v98', ['--cache', cache, '--output-dir', cache_audit, '--require-complete'])
        verified = read(cache_audit/'verification.json'); assert verified['passed'] and verified['complete'] and not verified['snapshot_only']
        stage('source_held_fitting', 'run.calitree_local_warranted_rules_v97', ['--cache', cache, '--output-dir', study])
        selection = read(study/'selection.json'); state.update(selection=selection)
        if selection['accuracy']['correct'] > 225:
            stage('bound_policy_audit', 'run.verify_calitree_local_policy_v100', ['--cache', cache, '--study', study, '--cache-audit', cache_audit, '--output-dir', policy_audit])
            result = read(policy_audit/'verification.json'); assert result['passed']
            state.update(verified_accuracy=result['accuracy'], target_exceeded=result['target_exceeded'], policy_verified=True)
        else:
            state.update(target_exceeded=False, policy_verified=False, reason='No candidate improves the retained225/276 policy')
        state.update(stage='complete', complete=True); save_json(out/'state.json', state)
        with (out/'run.log').open('a') as f:
            f.write('Completed the one-shot comparison. No serving defaults or goal status changed.\n')
        print(state, flush=True)
    except Exception as exc:
        state.update(stage='failed', error=type(exc).__name__+': '+str(exc)); save_json(out/'state.json', state)
        with (out/'run.log').open('a') as f:
            f.write(state['error']+'\n')
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for argument in ('cache', 'output-dir', 'cache-audit', 'study', 'policy-audit'):
        p.add_argument('--'+argument, type=Path, required=True)
    p.add_argument('--max-wait-seconds', type=int, default=7200); a = p.parse_args()
    run(a.cache.resolve(), a.output_dir.resolve(), a.cache_audit.resolve(), a.study.resolve(), a.policy_audit.resolve(), a.max_wait_seconds)
