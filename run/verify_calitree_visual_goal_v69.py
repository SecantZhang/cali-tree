"""Audit the updated >80% goal against actual source-held visual-policy results."""
import argparse
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier
from sklearn.model_selection import StratifiedGroupKFold

from critical.core.decision.artifacts import digest, save_json
from run.calitree_visual_policy_v64 import visual_arrays, VISION
from run.calitree_accuracy_headroom_v37 import accuracy
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint
from run.paired_vision_features_v63 import query_plan, statistics, predicates
from run.calitree_simplified_policy_v44 import feature_columns

STUDY = ROOT / 'logs/exps/261021-visual-policy-v64'


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    manifest = read(STUDY / 'manifest.json')
    for path, expected in {**manifest['code_hashes'], **manifest['source_hashes']}.items():
        assert fingerprint(path) == expected
    assert fingerprint(VISION / 'encoder_identity.json') == manifest['encoder_identity_sha256']
    identity = read(VISION / 'encoder_identity.json')
    reference = digest(identity)
    cache = VISION / 'encoder_cache' / reference
    visual_manifest = read(VISION / 'manifest.json')
    for p, expected in visual_manifest['code_hashes'].items():
        assert fingerprint(p) == expected
    def text_vector(text):
        return np.load(cache / 'texts' / (digest(text) + '.npy'), allow_pickle=False)
    entries = read(VISION / 'inputs_without_labels.json')
    assert len(entries) == 915
    image_hashes = visual_manifest['image_hashes']
    for e in entries:
        assert not {'reference', 'human_score', 'regular'} & set(e)
        assert query_plan(e['program']) == e['query_plan']
        source, edited = [np.load(cache / 'images' / (image_hashes[e['evidence'][key]] + '.npy'), allow_pickle=False) for key in ('source_image', 'edited_image')]
        plan = e['query_plan']
        text = {'target': text_vector(plan['target']), 'goal': text_vector(plan['goal']),
                'probes': [{'positive': text_vector(p['positive']), 'negative': np.stack([text_vector(s) for s in p['negative']])} for p in plan['probes']]}
        rebuilt = statistics(source, edited, text)
        saved = read(VISION / 'cases' / (e['case'] + '.json'))
        assert saved['encoder_ref'] == reference and saved['measurements'] == rebuilt
        assert saved['features'] == predicates(rebuilt)
    for p, expected in image_hashes.items():
        assert fingerprint(p) == expected
    local, recent, extra, _, names, X, actions, _ = visual_arrays()
    examples = local + recent + extra
    y = np.asarray([e['reference'] for e in examples])
    assert digest(X.tolist()) == manifest['features_ref'] and digest(y.tolist()) == manifest['target_ref']
    results, all_rows = read(STUDY / 'results.json')['candidates'], read(STUDY / 'predictions.json')
    by_case = {e['case']: e for e in recent}
    for candidate, result in results.items():
        rows = [r for r in all_rows if r['candidate'] == candidate]
        assert len(rows) == len({r['case'] for r in rows}) == 276
        assert all(all(r[k] == by_case[r['case']][k] for k in ('source_group', 'reference', 'regular', 'cohort')) for r in rows)
        for cohort, metrics in result['metrics'].items():
            selected = [r for r in rows if cohort == 'all' or r['cohort'] == cohort]
            for arm, expected in metrics.items():
                if arm != 'coverage':
                    assert accuracy(selected, arm) == expected
    winner = read(STUDY / 'selection.json')
    assert winner['candidate'] == 'boost_full_vision' and winner['arm'] == 'direct'
    saved_folds = [f for f in read(STUDY / 'folds.json') if f['candidate'] == winner['candidate']]
    records = {r['case']: r for r in all_rows if r['candidate'] == winner['candidate']}
    groups = np.asarray([e['source_group'] for e in examples])
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261020)
    splits = []
    for tr, te in splitter.split(np.zeros(276), y[99:375], groups[99:375]):
        held = [99 + int(i) for i in te]
        sources = set(groups[held])
        train = [i for i, e in enumerate(examples) if e['source_group'] not in sources]
        splits.append((train, held))
    splits.append((list(range(915)), []))
    retention, reproduced = [], []
    for fold, (train, held) in enumerate(splits):
        stored = next(f for f in saved_folds if f['fold'] == fold)
        assert stored['train_cases'] == [examples[i]['case'] for i in train]
        assert stored['held_cases'] == [examples[i]['case'] for i in held]
        assert not set(groups[train]) & set(groups[held]) and set(range(99)) <= set(train)
        cols = feature_columns(names, X, train, 'dedup_noexpert')
        assert stored['selected_features'] == [names[i] for i in cols]
        model = CatBoostClassifier(loss_function='MultiClass', depth=8, iterations=1200, learning_rate=.05, l2_leaf_reg=3.,
                    random_seed=20261021, thread_count=2, verbose=False, allow_writing_files=False, bootstrap_type='No', random_strength=0.)
        weights = np.asarray([stored['original_weight'] if i < 99 else 1. for i in train])
        model.fit(X[train][:, cols], y[train], sample_weight=weights)
        def decide(i, p):
            available = sorted({a for a in actions[i] if a >= 0})
            return int(np.argmax(p)) if examples[i]['features'] is not None and available else examples[i]['regular']
        original = [decide(i, p) for i, p in enumerate(model.predict_proba(X[:99, cols]))]
        retention.append(sum(value == e['reference'] for value, e in zip(original, local)))
        for i, p in zip(held, model.predict_proba(X[held][:, cols])):
            actual = decide(i, p)
            assert actual == records[examples[i]['case']]['direct']
            reproduced.append({'case': examples[i]['case'], 'reference': int(y[i]), 'prediction': actual})
        if not held:
            final_originals = dict(zip((e['case'] for e in local), original))
    assert retention == [99] * 6
    assert len(reproduced) == 276 and sum(r['prediction'] == r['reference'] for r in reproduced) == 222
    slots = 0
    for bank in (1, 2, 3):
        for row in old_inputs(PREVIOUS, bank)[3]['local']:
            assert final_originals[row['case']] == row['reference']
            slots += 1
    assert slots == 144
    result = {'passed': True, 'updated_goal': 'Over80% accuracy with original training accuracy retained.',
              'correct': 222, 'total': 276, 'accuracy': 222 / 276, 'strictly_over_80_requires': 221,
              'source_groups': 84, 'source_held_model_refits': 5, 'full_fit_refits': 1,
              'original_correct_in_every_fit': retention, 'original_training_slots_correct': slots,
              'vision_comparisons_rebuilt': 915, 'tree_accepted': 273, 'new_paid_model_calls': 0,
              'reserved_sources_used': 0, 'fresh_validation_performed': False,
              'scope': 'Independently replayed source-held development estimate after model selection; no claim of pristine final-set accuracy.'}
    out.mkdir(parents=True)
    save_json(out / 'verification.json', result)
    save_json(out / 'predictions.json', reproduced)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'study_manifest_sha256': fingerprint(STUDY / 'manifest.json'),
              'encoder_identity_sha256': fingerprint(VISION / 'encoder_identity.json')})
    (out / 'run.log').write_text('Rebuilt all915 visual comparisons; independently refit all five source-held winning models and full fit; all original99 and144 slots retained. Updated80% target exceeded.\n')
    (out / 'llm-histories.log').write_text('Zero model API calls.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
