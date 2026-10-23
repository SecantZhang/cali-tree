"""Train with compatible cached evidence views; evaluate only current inputs.

Alternative evidence is used as fitting augmentation, never as an additional
inference call. All views of a held source are excluded. Human labels and image
hashes must match the current reference pool exactly before a view is admitted.
"""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision import bound_evidence_v2 as physical
from critical.core.decision import semantic_interpretation_v5 as meaning
from critical.core.calibration import shared_regions_v27 as shared
from run.calitree_accuracy_headroom_v37 import encoded, Probe, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'cached-evidence-view-augmentation-v45'
VARIANTS = ('261018-three-sampled-splits-v11-luna', '261018-three-sampled-splits-v11-luna-v2')


def augment(original):
    current = {e['case']: e for e in original if e['case'].startswith('N')}
    metadata = {e['case']: e for e in read(SOURCE / 'manifest.json')['cases']}
    views, provenance, rejected = [], {}, Counter()
    for version in VARIANTS:
        root = SOURCE.parent / version
        manifest = read(root / 'manifest.json')
        provenance[str(root / 'manifest.json')] = fingerprint(root / 'manifest.json')
        for m in manifest['cases']:
            if m['case'] not in current:
                continue
            e, reference = current[m['case']], metadata[m['case']]
            if any(m[k] != reference[k] for k in ('group', 'reference', 'instruction', 'image_hashes')):
                rejected['image_or_target_mismatch'] += 1
                continue
            extraction_path = root / 'extraction/cases' / (m['case'] + '.json')
            interpretation_path = root / 'interpretations' / (m['case'] + '.json')
            if not extraction_path.exists() or not interpretation_path.exists():
                rejected['missing_checkpoint'] += 1
                continue
            c, i = read(extraction_path), read(interpretation_path)
            provenance[str(extraction_path)] = fingerprint(extraction_path)
            provenance[str(interpretation_path)] = fingerprint(interpretation_path)
            if c['error'] or i['error'] or not c['compilation'] or not c['observation']:
                rejected['failed_checkpoint'] += 1
                continue
            p, o, value = c['compilation']['program'], c['observation']['observation'], i['interpretation']
            hashes, pair = physical.image_identity(m['evidence'])
            assert hashes == m['image_hashes'] == reference['image_hashes']
            assert p['instruction'] == m['instruction']
            payload = meaning.make_input(p, o, pair)
            meaning.validate(payload, value)
            features = shared.evidence.project(p, o, pair, value)
            views.append({**e, 'case': e['case'] + ':' + version, 'original_case': e['case'],
                          'program': p, 'features': features, 'view': version})
    return views, provenance, dict(rejected)


def run(out, expanded=False):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    local, recent, experts, _ = examples_and_scores(expanded)
    primary = local + recent
    views, provenance, rejected = augment(primary)
    examples = primary + views
    names, X, actions = encoded(examples, experts)
    n = len(local)
    y = np.asarray([e['reference'] for e in examples])
    groups = sorted({e['source_group'] for e in recent})
    if expanded:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
        held_sets = [[n + int(i) for i in held] for _, held in splitter.split(np.zeros(len(recent)), y[n:len(primary)], [e['source_group'] for e in recent])]
    else:
        held_sets = [[i for i, e in enumerate(primary) if i >= n and e['source_group'] == group] for group in groups]
    configs = [{'max_features': mf, 'view_weight': weight} for mf in ('sqrt', .5) for weight in (.25, 1.0)]
    configs += [{'max_features': 'sqrt', 'view_weight': 0.0}]
    protocol = {'version': VERSION, 'configs': configs, 'expanded': expanded, 'alternative_views': len(views),
                'view_rejections': rejected, 'folds': len(held_sets), 'new_model_calls': 0, 'extra_inference_calls': 0,
                'views': 'Only cached original-N fitting/development views with identical source, edited pixels, instruction and human target; all views of held sources excluded.',
                'retention': 'Require all 99 current original training examples correct in every fit.',
                'scope': 'Reviewed development screening only; reserved 80 sources and frozen historical final set are not accessed.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'augmentation.json', views)
    results, records, memberships = {}, [], []
    for config in configs:
        name = str(config['max_features']) + '_' + str(config['view_weight'])
        selected, counts = [], []
        weights = np.asarray([1.] * len(primary) + [config['view_weight']] * len(views))
        for fold, held in enumerate(held_sets):
            held_sources = {examples[i]['source_group'] for i in held}
            train = [i for i, e in enumerate(examples) if e['source_group'] not in held_sources and weights[i] > 0]
            assert set(range(n)) <= set(train)
            assert not held_sources & {examples[i]['source_group'] for i in train}
            model = Probe('forest', config['max_features']).fit(X[train], y[train], sample_weight=weights[train]).model
            local_correct = sum(int(p) == e['reference'] for p, e in zip(model.predict(X[:n]), local))
            counts.append(local_correct)
            for i, probability in zip(held, model.predict_proba(X[held])):
                scores = {int(c): float(p) for c, p in zip(model.classes_, probability)}
                direct = max(scores, key=lambda c: (scores[c], -c))
                available = sorted({p for p in actions[i] if p >= 0})
                routed = max(available, key=lambda c: (scores[c], -c)) if available else -1
                e = examples[i]
                if e['features'] is None:
                    direct = routed = e['regular']
                selected.append({'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
                                 'reference': e['reference'], 'regular': e['regular'], 'direct': direct, 'routed': routed,
                                 'candidate': name, 'fold': fold})
            memberships.append({'candidate': name, 'fold': fold, 'held_sources': sorted(held_sources),
                                'training_sources': sorted({examples[i]['source_group'] for i in train}),
                                'local_correct': local_correct, 'training_views': len(train)})
        entry = {'config': config, 'minimum_local_correct': min(counts), 'retains_training': min(counts) == n, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rows = [r for r in selected if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {a: accuracy(rows, a) for a in ('regular', 'direct', 'routed')}
        results[name] = entry
        records.extend(selected)
        save_json(out / 'results.json', {'version': VERSION, 'candidates': results, 'target_verified': False,
                  'new_model_calls': 0, 'fresh_validation_performed': False})
        print({'candidate': name, 'local_minimum': min(counts), 'direct': entry['metrics']['all']['direct']['correct'],
               'routed': entry['metrics']['all']['routed']['correct'], 'total': len(recent)}, flush=True)
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', memberships)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'source_hashes': provenance, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'run/calitree_accuracy_headroom_v37.py', ROOT / 'run/calitree_continuous_policy_v43.py')}})
    (out / 'run.log').write_text('Five compatible-evidence augmentation/control policies, with all held-source views excluded and current original training retention checked.\n')
    (out / 'llm-histories.log').write_text('Zero model calls; compatible cached evidence only.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expanded', action='store_true')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.expanded)
