"""Collect the frozen M1 v2 representation on M0's 48 training cases only."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION as EVIDENCE_VERSION, COMPILER_SCHEMA, TEMPLATES
from run.calitree_bound_evidence_v2 import collect, audit_payloads, usage, exact, CAPS
from run.calitree_single_call import ROOT, IDENTITY, read, fingerprint

VERSION = 'm2-m4-frozen-bound-training48-v1'
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
M1 = ROOT / 'logs/exps/261014-m1-bound-evidence-development12-v2'


def allowed_cases():
    rows = read(M0 / 'splits/train.json')['cases']
    forbidden = {r['group'] for name in ('validation', 'test') for r in read(M0 / 'splits' / (name + '.json'))['cases']}
    assert len(rows) == len({c['group'] for c in rows}) == 48
    assert not {c['group'] for c in rows} & forbidden
    assert Counter(c['reference'] for c in rows) == {'no': 16, 'partial': 16, 'yes': 16}
    return rows


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    cases = allowed_cases(); old = read(M1 / 'manifest.json')
    files = [Path(__file__).resolve(), ROOT / 'run/calitree_bound_evidence_v2.py']
    files += [ROOT / p for p in old['code_hashes']]
    code = {}
    for path in dict.fromkeys(files):
        rel = str(path.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dst); code[rel] = fingerprint(path)
    for rel, h in old['code_hashes'].items():
        if fingerprint(ROOT / rel) != h:
            raise ValueError('The accepted M1 implementation changed: ' + rel)
    pinned = [M0 / 'seal.json', M0 / 'completion_seal.json', M0 / 'splits/train.json', M0 / 'splits/test.json',
              M0 / 'selection_protocol.json', M1 / 'completion_seal.json', M1 / 'manifest.json',
              M1 / 'observations.json', M1 / 'development_budget_revision.json']
    m = {'version': VERSION, 'evidence_version': EVIDENCE_VERSION, 'cases': cases, 'judge_identity': IDENTITY,
         'workers': 8, 'caps': CAPS, 'max_calls': 96, 'image_presentations_per_case': 1, 'attempts_per_stage': 1,
         'presentation': 'source_first', 'code_hashes': code, 'compiler_schema_ref': digest(COMPILER_SCHEMA),
         'pinned_files': {str(p): fingerprint(p) for p in pinned},
         'scope': 'Training collection only. Reuse the twelve saved development records; no final-test collection. No case retries or label-informed extraction.',
         'search_protocol': 'features/scopes/search budgets are separately sealed before fitting; labels reach only offline fitting/scoring.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'max_new_calls': 96, 'compiler_calls': 48, 'image_calls': 48,
              'max_completion_tokens': 48 * sum(CAPS.values()), 'prior_M1_calls': 47,
              'cumulative_development_extraction_ceiling': 143, 'reserved_test_calls': 0})
    release = read(ROOT / 'data/aurora/bench/manifest.json'); images = []
    for c in cases:
        for k, path in c['evidence'].items():
            rel = str(Path(path).relative_to(ROOT / 'data/aurora/bench'))
            if fingerprint(path) != c['image_hashes'][k] or fingerprint(path) != release['files'][rel]['sha256']:
                raise ValueError('Asset differs from frozen public release')
            images.append({'case': c['case'], 'role': k, 'release_path': rel, 'sha256': fingerprint(path)})
    save_json(output / 'public_data_provenance.json', {'repository': 'https://github.com/McGill-NLP/AURORA#human-ratings',
              'images_google_drive_id': release['images_google_drive_id'], 'images': images,
              'destination': 'https://api.openai.com/v1', 'payload': 'Published image pairs/instructions and their bound physical questions, without labels or prior judgments.'})
    verify(output, m); return m


def verify(output, m):
    if m['version'] != VERSION or m['cases'] != allowed_cases() or m['judge_identity'] != IDENTITY or m['caps'] != CAPS or digest(m) != read(output / 'seal.json')['manifest_ref']:
        raise ValueError('Changed training collection protocol')
    if m['compiler_schema_ref'] != digest(COMPILER_SCHEMA):
        raise ValueError('Changed M1 schema')
    for p, h in m['pinned_files'].items():
        if fingerprint(p) != h:
            raise ValueError('Changed pinned source: ' + p)
    for rel, h in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != h or fingerprint(output / 'source_snapshot' / rel) != h:
            raise ValueError('Changed extraction implementation: ' + rel)
    for c in m['cases']:
        for k, path in c['evidence'].items():
            if fingerprint(path) != c['image_hashes'][k]:
                raise ValueError('Changed image')
    if (M0 / 'predictions.json').exists() or list(M0.glob('ledgers/**/jobs/*.json')):
        raise ValueError('Final reservation has been evaluated')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    modes = p.add_mutually_exclusive_group(required=True)
    for k in ('preflight', 'live', 'replay'):
        modes.add_argument('--' + k, action='store_true')
    args = p.parse_args(); output = args.output_dir.resolve(); m = prepare(output)
    if args.preflight:
        print(read(output / 'estimate.json')); return
    rows = collect(output, m, args.live); verify(output, m)
    exact(output / 'observations.json', rows)
    result = {'version': VERSION, 'model': IDENTITY, 'manifest_ref': digest(m),
              'compiled': sum(r['compilation'] is not None for r in rows),
              'observed': sum(r['record'] is not None for r in rows),
              'failures': [{'case': r['case'], 'error': r['error']} for r in rows if r['record'] is None],
              'audit': audit_payloads(output, m, rows), 'usage': usage(output)}
    exact(output / 'results.json', result)
    if args.replay:
        exact(output / 'replay.json', {'exact_replay': True, 'new_model_calls': 0, 'results_sha256': fingerprint(output / 'results.json')})
    else:
        (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/*/llm-histories.log'))))
    print(result)


if __name__ == '__main__':
    main()
