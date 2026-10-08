"""Failure-selected local stress test of the unchanged robust v3 optimizer."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path

from PIL import Image

from critical.core.decision.artifacts import save_json
from critical.core.optimization.program.robust import RobustPolicy
from run.calitree_robust_leaf_optimization import ARMS, ROOT, SOURCE, code_hashes, execute, write_report

HISTORY = ROOT / 'logs/exps/261006-optimizer-comparison-v1/results.json'
PREVIOUS = ROOT / 'logs/exps/261007-robust-leaf-v3-network/manifest.json'
SCOPE = ('Three failure-selected, previously observed local fitting cases outside the prior six-case v3 pilot. '
         'Selected before new calls by lowest mean saved seed agreement across custom, GEPA and TextGrad. '
         'This intentionally difficult subset is not class-balanced or a held-out generalization evaluation. '
         'Repetitions measure behavior within cases, not independent cases.')


def select_hard_cases(source, history, previous):
    excluded = {row['id'] for row in previous['cases']}
    ranking = []
    for raw in source['cases']:
        if raw['id'] in excluded:
            continue
        scores = {method: history['cases'][raw['id']][method]['final']['seed']['agreement']
                  for method in ('custom', 'gepa', 'textgrad')}
        mean = sum(scores.values()) / len(scores)
        if mean < .8:
            ranking.append({'id': raw['id'], 'mean_seed_agreement': mean, 'seed_agreement': scores})
    ranking.sort(key=lambda row: (row['mean_seed_agreement'], row['id']))
    if len(ranking) < 3:
        raise ValueError('Need three prior-failure cases outside the previous pilot')
    selected = {row['id'] for row in ranking[:3]}
    return sorted((deepcopy(row) for row in source['cases'] if row['id'] in selected), key=lambda row: row['id']), ranking


def preflight(output):
    source = json.loads(SOURCE.read_text())
    cases, ranking = select_hard_cases(source, json.loads(HISTORY.read_text()), json.loads(PREVIOUS.read_text()))
    rows, groups = [], set()
    for raw in cases:
        row = {key: deepcopy(raw[key]) for key in ('id', 'instruction', 'target', 'evidence', 'image_hashes', 'group')}
        row['rubric'] = raw['seed']['program']['rubric']
        for key, path in row['evidence'].items():
            if sha256(Path(path).read_bytes()).hexdigest() != row['image_hashes'][key]:
                raise ValueError('Frozen image changed')
        with Image.open(row['evidence']['source_image']) as image:
            pixels = image.convert('RGB')
            group = sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
        if group != row['group'] or group in groups:
            raise ValueError('Changed or repeated source-pixel group')
        groups.add(group)
        rows.append(row)
    if importlib.metadata.version('textgrad') != '0.1.8':
        raise ValueError('Expected pinned TextGrad 0.1.8')
    folder = Path(importlib.util.find_spec('textgrad').origin).parent
    hashes = code_hashes()
    hashes[str(Path(__file__).relative_to(ROOT))] = sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {
        'version': 'robust-leaf-hard-cases-v3', 'scope': SCOPE, 'model': 'gpt-6-luna',
        'temperature': 0, 'reasoning_effort': 'none', 'provider': 'openai', 'random_seed': 20261007,
        'cases': rows, 'arms': list(ARMS), 'policy': asdict(RobustPolicy()), 'round_batches': [1, 2],
        'proposals_per_batch': 2, 'frontier_capacity': 6, 'max_nodes': 4, 'max_depth': 4,
        'screen_repeats': 1, 'max_calls': 1800, 'max_completion_tokens': 2304000,
        'reserve_calls': 480, 'reserve_tokens': 491520, 'scope_limits': {'search': 109, 'final': 40},
        'shared_calls_per_case': 2, 'planned_maximum_calls': 1794,
        'selection': {'rule': 'lowest prior seed agreement < 0.8; exclude previous six; tie by case ID',
                      'ranking': ranking, 'feedback_from_new_results': False},
        'source_manifest_hash': sha256(SOURCE.read_bytes()).hexdigest(),
        'history_sha256': sha256(HISTORY.read_bytes()).hexdigest(),
        'previous_manifest_sha256': sha256(PREVIOUS.read_bytes()).hexdigest(),
        'code_hashes': hashes,
        'dependencies': {'textgrad': '0.1.8', 'hashes': {
            str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*.py'))}},
    }
    output = Path(output)
    path = output / 'manifest.json'
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError('Frozen configuration, code, dependency or source changed; cannot resume')
    else:
        save_json(path, manifest)
        for relative in manifest['code_hashes']:
            dest = output / 'source_snapshot' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / relative).read_bytes())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    for mode in ('preflight', 'live', 'report'):
        modes.add_argument('--' + mode, action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.report:
        write_report(args.output_dir, json.loads((args.output_dir / 'results.json').read_text()),
                     json.loads((args.output_dir / 'manifest.json').read_text()))
        return
    if args.resume and not (args.output_dir / 'manifest.json').exists():
        parser.error('Resume requires an existing manifest')
    manifest = preflight(args.output_dir)
    if not args.live:
        print(json.dumps({'status': 'ready', 'cases': [r['instruction'] for r in manifest['cases']],
                          'max_calls': manifest['max_calls'], 'max_completion_tokens': manifest['max_completion_tokens']}))
        return
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    creds = load_creds(engine='gpt', provider='openai')
    if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official OpenAI endpoint required; no fallback')
    history = LLMHistoryWriter(args.output_dir / 'llm-histories.log')
    result = execute(args.output_dir, manifest, lambda cap: get_engine(
        'gpt', model=manifest['model'], creds=creds, history=history, max_tokens=cap,
        temperature=0, max_http_attempts=1, timeout=60))
    print(json.dumps({'status': result['status'], 'error': result.get('error'), 'output': str(args.output_dir)}))


if __name__ == '__main__':
    main()
