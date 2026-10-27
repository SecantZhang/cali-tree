"""Evaluate meaningful reconstructed rubrics with frozen boosted fallbacks."""
import argparse
from dataclasses import replace
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_rubric_v70 import Config
from critical.core.calibration.semantic_warrants_v71 import WarrantedRubric, warranted
from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_rubric_v70 import data, FROZEN, STUDY, ROOT, read, fingerprint
from run.calitree_accuracy_headroom_v37 import accuracy

TEACHERS = ROOT / 'logs/exps/261023-semantic-rubric-v70-r1'
INNER = ROOT / 'logs/exps/261023-rubric-inner-teachers-v70'


def run(out, correction=False):
    if out.exists():
        raise ValueError('Fresh output directory required')
    examples, names, X = data()
    y = np.asarray([e['reference'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples])
    valid = np.asarray([e['covered'] for e in examples])
    regular = np.asarray([e['regular'] for e in examples])
    positions = {r['case']: i for i, r in enumerate(examples)}
    artifact_ref = read(FROZEN / 'policy.json')['artifact_ref']
    configs = [Config(family=f, max_literals=4, max_rules=12, max_features=160) for f in ('semantic', 'grounded', 'auxiliary')]
    if correction:
        configs += [replace(c, mode='correct', min_sources=2, minimum_precision=.67) for c in configs]
    protocol = {'version': WarrantedRubric.version, 'configs': [vars(c) for c in configs],
                'primary_cases': 276, 'source_groups': 84, 'original_cases': 99, 'original_slots': 144,
                'teacher_control': 'Exactly replay all five original v69 held-source predictions including failures.',
                'semantic_obligations': 'No requires explicit failure evidence; Partial requires progress or achieved outcome with a shortfall; Yes requires endpoint, identity and collateral warrants.',
                'feature_priority': 'Teacher importance with a fixed bonus for explicit meaning predicates, preserving semantic warrants when aliases share a column.',
                'correction_training': 'Five inner source-excluded teachers within each outer training fold. Original-source fitting views are explicitly supervised, not out of sample.',
                'runtime': 'Ordered Boolean rubric over the existing bound LLM evidence, boosted fallback elsewhere. No prose-only LLM execution claim.',
                'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True)
    save_json(out / 'protocol.json', protocol)
    code = [Path(__file__), ROOT / 'critical/core/calibration/semantic_rubric_v70.py',
            ROOT / 'critical/core/calibration/semantic_warrants_v71.py',
            ROOT / 'critical/core/calibration/semantic_rubric_runtime_v70.py']
    hashes = {str(p): fingerprint(p) for p in code}
    for path in code:
        dest = out / 'source_snapshot' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    (out / 'llm-histories.log').write_text('Zero paid API calls. Deterministic rubric execution over cached bound LLM evidence.\n')
    (out / 'run.log').write_text('Warranted semantic rubric fitting in progress.\n')
    baseline = {r['case']: r for r in read(STUDY / 'predictions.json') if r['candidate'] == 'boost_full_vision'}
    records, retention = [], []
    for f in (f for f in read(STUDY / 'folds.json') if f['candidate'] == 'boost_full_vision'):
        train, held = [positions[c] for c in f['train_cases']], [positions[c] for c in f['held_cases']]
        directory = TEACHERS / ('fold' + str(f['fold']))
        contract = read(directory / 'teacher.json')['contract']
        assert contract['rows'] == train and contract['targets_ref'] == digest(y[train].tolist())
        saved = read(directory / 'predictions.json')
        support = np.asarray(saved['support'])
        proposed = np.argmax(support, axis=1)
        proposed[~valid] = regular[~valid]
        assert not set(groups[train]) & set(groups[held])
        assert np.all(proposed[:99] == y[:99])
        assert all(proposed[i] == baseline[examples[i]['case']]['direct'] for i in held)
        priority = {name: saved['priority'].get(name, 0.) + (1000. if name.startswith('meaning_') else 0.) for name in names}
        oof, membership = proposed.copy(), []
        if correction:
            for inner in range(5):
                cache = INNER / directory.name / ('inner' + str(inner))
                entry = read(cache / 'membership.json')
                meta = read(cache / 'teacher.json')['contract']
                held_sources = set(entry['held_sources'])
                assert entry['outer_held_sources'] == sorted(set(groups[held]))
                assert not set(entry['training_sources']) & (held_sources | set(groups[held]))
                assert meta['rows'] == [i for i in train if groups[i] not in held_sources]
                indices = [i for i in train if groups[i] in held_sources]
                ps = np.asarray(read(cache / 'predictions.json')['support'])
                oof[indices] = np.argmax(ps[indices], axis=1)
                membership.append(entry)
            oof[~valid] = regular[~valid]
        folder = out / directory.name
        save_json(folder / 'memberships.json', {'train_cases': f['train_cases'], 'held_cases': f['held_cases'],
                                               'inner_folds': membership})
        fit = [i for i in train if valid[i]]
        for config in configs:
            name = config.family + '_' + config.mode
            rubric = WarrantedRubric(names, config).fit(X[fit], proposed[fit] if config.mode == 'reconstruct' else y[fit],
                groups=groups[fit].tolist(), priority=priority, base_predictions=oof[fit] if config.mode == 'correct' else None,
                protected_X=X[:99], protected_y=y[:99], protected_base=proposed[:99])
            assert all(warranted(r['prediction'], r['conditions']) for r in rubric.rules)
            output = np.asarray(rubric.predict(X, base_predictions=proposed))
            delegated = np.asarray(rubric.predict(X, base_predictions=[-1] * len(X))) if config.mode == 'reconstruct' else None
            output[~valid] = regular[~valid]
            assert np.all(output[:99] == y[:99])
            save_json(folder / (name + '.json'), rubric.artifact(artifact_ref if f['fold'] == 5 else digest(contract)))
            (folder / (name + '.txt')).write_text(rubric.render())
            for i in held:
                records.append({**examples[i], 'teacher': int(proposed[i]), 'prediction': int(output[i]),
                                'candidate': name, 'fold': f['fold'],
                                'rubric_resolved': bool(delegated[i] >= 0) if delegated is not None else bool(output[i] != proposed[i])})
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': int(np.sum(output[:99] == y[:99])),
                              'rules': len(rubric.rules), 'literals': sum(len(r['conditions']) for r in rubric.rules),
                              'fitting_teacher_agreement': int(np.sum(output[fit] == proposed[fit])), 'fitting_cases': len(fit)})
        save_json(out / 'predictions.json', records)
        save_json(out / 'retention.json', retention)
        print({'fold': f['fold'], 'held': len(held), 'configs': len(configs)}, flush=True)
    results = {}
    for config in configs:
        name = config.family + '_' + config.mode
        rows = [r for r in records if r['candidate'] == name]
        results[name] = {'accuracy': accuracy(rows, 'prediction'), 'teacher': accuracy(rows, 'teacher'),
                        'gains': sum(r['prediction'] == r['reference'] != r['teacher'] for r in rows),
                        'losses': sum(r['teacher'] == r['reference'] != r['prediction'] for r in rows),
                        'changed': sum(r['teacher'] != r['prediction'] for r in rows),
                        'rubric_resolved': sum(r['rubric_resolved'] for r in rows), 'coverage': sum(r['covered'] for r in rows),
                        'all_original_fits_retained': all(r['original_correct'] == 99 for r in retention if r['candidate'] == name)}
    assert all(fingerprint(p) == sha for p, sha in hashes.items())
    save_json(out / 'results.json', results)
    save_json(out / 'manifest.json', {'code_sha256': hashes, 'matrix_ref': digest(X.tolist()), 'targets_ref': digest(y.tolist()),
                                    'teacher_study_ref': fingerprint(TEACHERS / 'manifest.json')})
    (out / 'run.log').write_text('Completed all six teacher-bound folds; all rules satisfy semantic warrants, original99 retained and missing-evidence coverage unchanged.\n')
    print(results, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--correction', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.correction)
