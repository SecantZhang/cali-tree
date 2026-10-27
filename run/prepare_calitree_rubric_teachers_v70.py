"""Prepare source-excluded teacher predictions for semantic correction fitting."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import save_json
from run.calitree_semantic_rubric_v70 import data, teacher, read, STUDY, fingerprint


def run(out, workers=3):
    examples, names, X = data()
    y = np.asarray([r['reference'] for r in examples])
    groups = np.asarray([r['source_group'] for r in examples])
    positions = {r['case']: i for i, r in enumerate(examples)}
    originals = set(groups[:99])
    jobs = []
    for outer in (f for f in read(STUDY / 'folds.json') if f['candidate'] == 'boost_full_vision'):
        train = [positions[c] for c in outer['train_cases']]
        outer_held = {groups[positions[c]] for c in outer['held_cases']}
        pool = [i for i in train if groups[i] not in originals]
        split = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261023)
        for inner, (_, held) in enumerate(split.split(np.zeros(len(pool)), y[pool], groups[pool])):
            excluded = {groups[pool[int(i)]] for i in held}
            fitting = [i for i in train if groups[i] not in excluded]
            assert not set(groups[fitting]) & (excluded | outer_held)
            jobs.append({'outer': outer['fold'], 'inner': inner, 'train': fitting,
                         'training_sources': sorted(set(groups[fitting])), 'held_sources': sorted(excluded),
                         'outer_held_sources': sorted(outer_held)})
    out.mkdir(parents=True, exist_ok=True)
    protocol = {'jobs': jobs, 'workers': workers, 'threads_per_teacher': 2,
                'new_paid_calls': 0, 'reserved_sources_used': 0,
                'scope': 'Inner predictions for source-held correction learning. Protected original sources stay in fitting.'}
    if (out / 'protocol.json').exists():
        assert read(out / 'protocol.json') == protocol
    else:
        save_json(out / 'protocol.json', protocol)
    (out / 'llm-histories.log').write_text('Zero API calls. Native local CatBoost fitting only.\n')
    completed = []
    def execute(job):
        folder = out / ('fold' + str(job['outer'])) / ('inner' + str(job['inner']))
        teacher(names, X, y, job['train'], folder)
        save_json(folder / 'membership.json', job)
        return {'outer': job['outer'], 'inner': job['inner']}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_jobs = [pool.submit(execute, job) for job in jobs]
        for future in as_completed(future_jobs):
            completed.append(future.result())
            save_json(out / 'progress.json', {'completed': completed, 'total': len(jobs)})
            print({'completed': len(completed), 'total': len(jobs), 'last': completed[-1]}, flush=True)
    save_json(out / 'manifest.json', {'code_sha256': fingerprint(__file__),
                                    'fitting_code_sha256': fingerprint(Path(__file__).with_name('calitree_semantic_rubric_v70.py'))})
    (out / 'run.log').write_text('Completed all30 independently source-excluded teacher caches; outer held sources absent from every inner fit.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.workers)
