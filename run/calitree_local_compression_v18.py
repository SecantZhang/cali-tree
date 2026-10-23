"""Offline local-accuracy-preserving child optimization and bounded merges.

Only the existing 48-case training records and their full/original4 fitted
policies are consumed. No final/development evaluation predictions or API calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from critical.core.calibration import local_compression_v18 as local
from critical.core.decision.artifacts import digest, save_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/261018-union-challenger-validation-v12'


def read(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(out):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new output directory; completed experiments are immutable')
    out.mkdir(parents=True, exist_ok=True)
    protocol = {'version': local.VERSION, 'config': local.asdict(local.Config()),
                'objective': 'Preserve or improve every local child accuracy; then minimize terminal rules.',
                'merge_requirement': 'Strictly fewer terminal rules; no regression on immediate children or original descendants.',
                'schedule': 'Optimize four seeds, try six pairs, then up to three complete-root partitions.',
                'seed_selection': 'Highest training correct count, then fewest rules, depth, artifact hash among existing original4 seeds.',
                'warm_start': 'Existing full/original4 registry policies on the exact union; no outside-union fitted policies.',
                'inference': 'Portable feature-only trees. Incomplete forests have no synthesized router.',
                'new_model_calls': 0, 'final_set_access': False, 'generalization_gate': False,
                'scope': 'Exploratory training optimization under the revised local-fit-first objective; no fresh generalization claim.'}
    source_files = [SOURCE / f'split{i}' / name for i in (1, 2, 3)
                    for name in ('training_data.json', 'full/original4/seeds.json', 'full/original4/result.json')]
    code_files = [Path(__file__).resolve(), Path(local.__file__).resolve(), ROOT / 'run/verify_calitree_local_compression_v18.py']
    code_files += list((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code_files += list((ROOT / 'critical/core/decision').glob('*.py'))
    manifest = {'protocol_ref': digest(protocol),
                'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in source_files},
                'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in code_files}}
    save_json(out / 'protocol.json', protocol); save_json(out / 'manifest.json', manifest)
    (out / 'llm-histories.log').write_text('No model calls: cached training evidence only.\n')
    summaries = []
    for i in (1, 2, 3):
        base = SOURCE / f'split{i}'; rows = read(base / 'training_data.json')
        seed_artifact = read(base / 'full/original4/seeds.json')
        seeds = [min((seed_artifact['nodes'][k] for k in group['policies']), key=local.rank) for group in seed_artifact['groups']]
        cached = list(read(base / 'full/original4/result.json')['registry'].values())
        start = time.monotonic(); result = local.learn(rows, seeds, cached=cached)
        elapsed = time.monotonic() - start
        save_json(out / f'split{i}/training_data.json', rows)
        save_json(out / f'split{i}/seeds.json', seeds)
        save_json(out / f'split{i}/result.json', result)
        runtime = {'version': local.VERSION, 'complete_root': result['root'] is not None,
                   'root': result['root']['runtime'] if result['root'] else None,
                   'trees': [result['registry'][k]['runtime'] for k in result['forest']],
                   'routing': result['forest_routing']}
        save_json(out / f'split{i}/portable_forest.json', runtime)
        summary = {'split': i, **result['summary'], 'elapsed_seconds': elapsed,
                   'complete_root': result['root'] is not None, 'cached_registry_candidates': len(cached),
                   'full_union_equality_certificate': local.equality_certificate(rows, result['optimized_requirements'])}
        summaries.append(summary); print(summary, flush=True)
        with (out / 'run.log').open('a') as stream:
            stream.write(json.dumps(summary) + '\n')
    results = {'version': local.VERSION, 'splits': summaries, 'new_model_calls': 0, 'final_set_predictions': 0,
               'measurement': 'Forest correct counts use each tree only on its own training scope; not combined unseen-case inference.',
               'efficiency': 'Incremental offline work reuses historical fitted policies; prior fit cost is not included.',
               'limitations': ['Bounded depth/shortlists/search states; failed searches do not prove tree infeasibility.',
                               'Equality certificates prove only incompatibility with stated local floors and fixed features.',
                               'No full roots in this run unless explicitly indicated by complete_root.',
                               'No new held-out evaluation is required for this local optimization milestone.']}
    save_json(out / 'results.json', results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    run(parser.parse_args().output_dir.resolve())
