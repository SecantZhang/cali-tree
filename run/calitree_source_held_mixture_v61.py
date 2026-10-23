"""Nested source-held mixture of legacy, expanded and explanation experts."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration.source_held_mixture_v61 import SemanticPanel, SourceHeldMixture, MEMBERS
from critical.core.decision.artifacts import digest, save_json
from run.calitree_intent_policy_v60 import arrays
from run.calitree_matched_policy_v58 import fixed_splits, THRESHOLDS, ARMS, decisions
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

FAMILIES = ('forest', 'balanced_forest', 'boundary')
VERSION = 'nested-source-held-semantic-mixture-v61'


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, extra, _, names, X, actions, _, sources = arrays()
    examples = local + recent + extra
    y = np.asarray([e['reference'] for e in examples])
    groups = np.asarray([e['source_group'] for e in examples])
    original, legacy = np.arange(915) < 99, np.arange(915) < 375
    splits = list(fixed_splits(local, recent, extra, 'full')) + [(list(range(915)), [])]
    out.mkdir(parents=True)
    protocol = {'version': VERSION, 'families': FAMILIES, 'members': MEMBERS, 'trees': 128, 'inner_folds': 5,
                'outer_folds': 5, 'primary_cases': 276, 'primary_sources': 84, 'protected_cases': 99,
                'base_training': 'Legacy boundary uses old375 training rows only; expanded semantic and explanation experts use all allowed rows. Every outer and inner held source has ALL siblings excluded.',
                'meta_training': 'Base predictions for each router-training row come from an inner source-excluded fit. Final-panel views of protected original examples are added as explicitly supervised fitting views.',
                'local_constraint': 'Choose the first original weight in 1,5,25 that keeps actual original argmax labels correct. Uses original fitting labels only, never primary held labels.',
                'features': 'Closed old/intent/explanation predicates plus fixed Boolean bins and comparisons of three expert supports. No source/case/editor identifiers or signatures in inference.',
                'decisions': 'Actual routed/direct/gated labels including missing-evidence regular fallback. Available actions include regular, frozen experts and each newly fitted expert proposal.',
                'thresholds': THRESHOLDS, 'new_model_calls': 0, 'reserved_sources_used': 0,
                'scope': 'Nested cached development screen, no final validation or serving change.'}
    save_json(out / 'protocol.json', protocol)
    records, folds, full_retention = [], [], {}
    for fold, (train, held) in enumerate(splits):
        panel = SemanticPanel(names).fit(X[train], y[train], groups=groups[train], original=original[train], legacy=legacy[train])
        directory = out / f'fold{fold}'
        save_json(directory / 'panel_oof.json', {'cases': [examples[i]['case'] for i in train], 'supports': panel.oof.tolist()})
        save_json(directory / 'inner_folds.json', panel.inner_trace)
        local_cube = panel.expert_supports(X[:99])
        held_cube = panel.expert_supports(X[held]) if held else None
        counts = {}
        for family in FAMILIES:
            mixture = SourceHeldMixture(names, family=family).fit_from_panel(panel, X[train], y[train], original=original[train])
            local_rows = [decisions(p, e, actions[i] + [int(v) for v in np.argmax(cube, axis=1)])
                          for i, (p, cube, e) in enumerate(zip(mixture.predict_proba(X[:99]), local_cube, local))]
            counts[family] = {arm: sum(r[arm] == e['reference'] for r, e in zip(local_rows, local)) for arm in ARMS}
            if held:
                for i, p, cube in zip(held, mixture.predict_proba(X[held]), held_cube):
                    e = examples[i]
                    row = decisions(p, e, actions[i] + [int(v) for v in np.argmax(cube, axis=1)])
                    records.append({k: e[k] for k in ('case', 'source_group', 'cohort', 'reference', 'regular')} |
                                   row | {'candidate': family, 'fold': fold, 'expert_proposals': [int(v) for v in np.argmax(cube, axis=1)]})
            else:
                full_retention[family] = counts[family]
            save_json(directory / (family + '.json'), {'protected_weight': mixture.protected_weight,
                      'protected_argmax_correct': mixture.protected_correct,
                      'original_actual_correct': counts[family],
                      'meta_features': [mixture.meta_names[i] for i in mixture.columns],
                      'base_feature_sets': {m['name']: [names[i] for i in m['columns']] for m in panel.members}})
        folds.append({'fold': fold, 'train_cases': [examples[i]['case'] for i in train],
                      'held_cases': [examples[i]['case'] for i in held], 'training_sources': sorted(set(groups[train])),
                      'held_sources': sorted(set(groups[held])), 'original_actual_correct': counts})
        print({'fold': fold, 'full_fit': not held, 'original_actual_correct': counts}, flush=True)
        save_json(out / 'predictions.json', records)
    results = {}
    for family in FAMILIES:
        rows = [r for r in records if r['candidate'] == family]
        retained = {arm: {'fold_original_correct': [f['original_actual_correct'][family][arm] for f in folds[:5]],
                          'full_original_correct': full_retention[family][arm]} for arm in ARMS}
        for entry in retained.values():
            entry['retains_training'] = min(entry['fold_original_correct'] + [entry['full_original_correct']]) == 99
        metrics = {}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            metrics[cohort] = {arm: accuracy(rs, arm) for arm in ('regular',) + ARMS}
            metrics[cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rs) for t in THRESHOLDS}
        results[family] = {'retention': retained, 'metrics': metrics}
        print({'candidate': family, 'correct': {arm: metrics['all'][arm]['correct'] for arm in ARMS},
               'eligible': {arm: retained[arm]['retains_training'] for arm in ARMS}}, flush=True)
    eligible = [(name, arm, e) for name, e in results.items() for arm in ARMS if e['retention'][arm]['retains_training']]
    eligible.sort(key=lambda item: (-item[2]['metrics']['all'][item[1]]['correct'], -item[2]['metrics']['all'][item[1]]['macro_f1'], item[1] != 'routed', item[0], item[1]))
    name, arm, winner = eligible[0]
    save_json(out / 'results.json', {'candidates': results, 'new_model_calls': 0, 'target_verified': False})
    save_json(out / 'folds.json', folds)
    save_json(out / 'selection.json', {'candidate': name, 'arm': arm, 'metrics': winner['metrics']['all'][arm],
              'retention': winner['retention'][arm], 'development_target_exceeded': winner['metrics']['all'][arm]['correct'] >= 235,
              'target_verified': False, 'new_model_calls': 0, 'fresh_validation_performed': False})
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'source_hashes': sources, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, ROOT / 'critical/core/calibration/source_held_mixture_v61.py', ROOT / 'run/calitree_intent_policy_v60.py',
               ROOT / 'critical/core/calibration/judge_semantics_v60.py', ROOT / 'run/calitree_matched_policy_v58.py')}})
    (out / 'run.log').write_text('Five outer source folds plus full fit; every router-training expert prediction source-excluded in five inner folds. Actual original decisions retained per arm.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    print(read(out / 'selection.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
