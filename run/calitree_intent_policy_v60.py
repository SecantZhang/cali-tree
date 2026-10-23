"""Evaluate finer task operations and regular-explanation cues on fixed folds."""
import argparse
from pathlib import Path

import numpy as np

from critical.core.calibration import judge_semantics_v60 as semantics
from critical.core.decision.artifacts import digest, save_json
from run.calitree_accuracy_headroom_v37 import encoded, accuracy
from run.calitree_continuous_policy_v43 import examples_and_scores
from run.calitree_simplified_policy_v44 import feature_columns
from run.calitree_matched_policy_v58 import COLLECTION, THRESHOLDS, ARMS, fixed_splits, model_for, probabilities, decisions
from run.calitree_cached_judgments_v60 import judgments
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint

VERSION = 'intent-explanation-policy-v60'
CONFIGS = [dict(family=f, coverage='zero', features='control', original_weight=1.) for f in ('forest', 'boundary')]
CONFIGS += [dict(family=f, coverage=c, features=features, original_weight=1. if c == 'zero' else 5.)
            for c in ('zero', 'full') for f in ('forest', 'boundary') for features in ('intent', 'both')]


def arrays():
    local, recent, experts, _ = examples_and_scores(True)
    extra = [{**e, 'cohort': 'matched540'} for e in read(COLLECTION / 'training_data.json')]
    examples = local + recent + extra
    names, raw, actions = encoded(examples, experts)
    cached, source_hashes = judgments(examples)
    flags = {e['case']: semantics.project(e['program'], cached[e['case']]) for e in examples}
    added = list(semantics.SPECS)
    matrix = np.concatenate([raw, np.asarray([[int(flags[e['case']][name]) for name in added] for e in examples], dtype=np.float32)], axis=1)
    return local, recent, extra, experts, names + added, matrix, actions, flags, source_hashes


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    local, recent, extra, experts, names, X, actions, flags, source_hashes = arrays()
    examples = local + recent + extra
    assert len(local) == 99 and len(recent) == 276 and len(examples) == 915
    out.mkdir(parents=True)
    protocol = {'version': VERSION, 'configs': CONFIGS, 'feature_contract': semantics.CONTRACT_REF,
                'scored_cases': 276, 'source_groups': 84, 'protected_cases': 99, 'protected_slots': 144,
                'folds': 'Unchanged v58 primary five source-group folds; exclude all new siblings of a held source.',
                'features': 'Old Boolean semantics plus closed primary authorized-operation cues and regular-explanation mentions/polarity. No raw text vectors, IDs, object/color-name flags, targets or image fingerprints.',
                'missing': 'Missing bound evidence keeps the same regular fallback, even if its explanation is available.',
                'selection': 'Actual original99 retention in all folds/full fit, then overall primary accuracy, macro-F1, routed arm, fewer added feature families and fitting rows, lexical name/arm.',
                'support_thresholds': THRESHOLDS, 'new_model_calls': 0, 'reserved_sources_used': 0,
                'scope': 'Cached development screen, not final validation or serving change.'}
    save_json(out / 'protocol.json', protocol)
    save_json(out / 'feature_contract.json', {'version': semantics.VERSION, 'intents': semantics.INTENTS, 'cues': semantics.CUES,
                                             'specs': semantics.SPECS, 'contract_ref': semantics.CONTRACT_REF})
    save_json(out / 'projected_features.json', flags)
    results, records, folds = {}, [], []
    y = np.asarray([e['reference'] for e in examples])
    for config in CONFIGS:
        name = '_'.join((config['family'], config['coverage'], config['features']))
        allowed = [i for i, n in enumerate(names) if not n.startswith(('intent_', 'rationale_')) or
                   (config['features'] != 'control' and n.startswith('intent_')) or
                   (config['features'] == 'both' and n.startswith('rationale_'))]
        base_names, base = [names[i] for i in allowed], X[:, allowed]
        weights = np.ones(len(examples))
        weights[:99] = config['original_weight']
        rows, local_counts = [], []
        for fold, (train, held) in enumerate(fixed_splits(local, recent, extra, config['coverage'])):
            columns = feature_columns(base_names, base, train, 'dedup_noexpert')
            matrix = base[:, columns]
            model = model_for(config).fit(matrix[train], y[train], sample_weight=weights[train])
            originals = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(probabilities(model, matrix[:99], config['family']), local))]
            local_counts.append({arm: sum(r[arm] == e['reference'] for r, e in zip(originals, local)) for arm in ARMS})
            for i, p in zip(held, probabilities(model, matrix[held], config['family'])):
                e = examples[i]
                rows.append({k: e[k] for k in ('case', 'source_group', 'cohort', 'reference', 'regular')} |
                            decisions(p, e, actions[i]) | {'candidate': name, 'fold': fold})
            folds.append({'candidate': name, 'fold': fold, 'train_cases': [examples[i]['case'] for i in train],
                          'held_cases': [examples[i]['case'] for i in held],
                          'training_sources': sorted({examples[i]['source_group'] for i in train}),
                          'held_sources': sorted({examples[i]['source_group'] for i in held}),
                          'selected_features': [base_names[i] for i in columns], 'original_correct': local_counts[-1]})
        full_train = list(range(375 if config['coverage'] == 'zero' else 915))
        columns = feature_columns(base_names, base, full_train, 'dedup_noexpert')
        model = model_for(config).fit(base[full_train][:, columns], y[full_train], sample_weight=weights[full_train])
        full_local = [decisions(p, e, actions[i]) for i, (p, e) in enumerate(zip(probabilities(model, base[:99, columns], config['family']), local))]
        retention = {arm: {'fold_original_correct': [r[arm] for r in local_counts],
                           'full_fit_original_correct': sum(r[arm] == e['reference'] for r, e in zip(full_local, local))} for arm in ARMS}
        for value in retention.values():
            value['retains_training'] = min(value['fold_original_correct'] + [value['full_fit_original_correct']]) == 99
        entry = {'config': config, 'retention': retention, 'metrics': {}}
        for cohort in ['all'] + sorted({e['cohort'] for e in recent}):
            rs = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            entry['metrics'][cohort] = {arm: accuracy(rs, arm) for arm in ('regular',) + ARMS}
            entry['metrics'][cohort]['coverage'] = {str(t): sum(r['accept_' + str(t)] for r in rs) for t in THRESHOLDS}
        if config['features'] == 'control':
            previous = {r['case']: r for r in read(ROOT / 'logs/exps/261021-matched-policy-v58/predictions.json')
                        if r['candidate'] == config['family'] + '_zero_w1.0'}
            assert all(r[arm] == previous[r['case']][arm] for r in rows for arm in ARMS)
        results[name] = entry
        records.extend(rows)
        save_json(out / 'results.json', {'candidates': results, 'target_verified': False, 'new_model_calls': 0})
        print({'candidate': name, 'correct': {arm: entry['metrics']['all'][arm]['correct'] for arm in ARMS},
               'retains_training': {arm: v['retains_training'] for arm, v in retention.items()}}, flush=True)
    eligible = [(name, arm, e) for name, e in results.items() for arm in ARMS if e['retention'][arm]['retains_training']]
    def rank(item):
        name, arm, e = item
        m, c = e['metrics']['all'][arm], e['config']
        return (-m['correct'], -m['macro_f1'], arm != 'routed', {'control': 0, 'intent': 1, 'both': 2}[c['features']], c['coverage'] != 'zero', name, arm)
    name, arm, selected = sorted(eligible, key=rank)[0]
    save_json(out / 'selection.json', {'candidate': name, 'arm': arm, 'metrics': selected['metrics']['all'][arm],
              'retention': selected['retention'][arm], 'development_target_exceeded': selected['metrics']['all'][arm]['correct'] >= 235,
              'target_verified': False, 'fresh_validation_performed': False, 'new_model_calls': 0})
    save_json(out / 'predictions.json', records)
    save_json(out / 'folds.json', folds)
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'features_ref': digest(X.tolist()), 'target_ref': digest(y.tolist()),
              'names': names, 'source_hashes': source_hashes, 'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in
              (__file__, semantics.__file__, ROOT / 'run/calitree_cached_judgments_v60.py', ROOT / 'run/calitree_matched_policy_v58.py')}})
    (out / 'run.log').write_text('Ten fixed finer-intent/explanation comparisons; controls reproduce v58; every held-source sibling excluded; original99 actual decisions checked in all folds and full fits.\n')
    (out / 'llm-histories.log').write_text('Zero model calls; cached regular judgments only.\n')
    print(read(out / 'selection.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
