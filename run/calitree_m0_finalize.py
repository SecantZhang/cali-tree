"""Seal selection folds/budgets and independently check the M0 reservation.

The addendum leaves the original reservation seal immutable. This command never
reads test images with a model, emits test instructions, or fits a policy.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

from run.calitree_m0 import QUOTAS, LABELS, verify
from run.calitree_single_call import ROOT, read, fingerprint
from critical.core.decision.artifacts import save_json


def exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Changed finalized M0 artifact: ' + str(path))
    else:
        save_json(path, value)


def selection_protocol(output):
    train = read(output / 'splits/train.json')['cases']
    folds = []
    for name in ('G1', 'G2', 'G3', 'G4'):
        held = [c for c in train if c['batch'] == name]
        fit = [c for c in train if c['batch'] != name]
        folds.append({'fold': name, 'fit_ids': [c['id'] for c in fit],
                      'validation_ids': [c['id'] for c in held],
                      'fit_sources': [c['group'] for c in fit],
                      'validation_sources': [c['group'] for c in held]})
    return {'version': 'semantic-hierarchy-m0-selection-v1', 'base_seal_sha256': fingerprint(output / 'seal.json'),
            'selection_folds': folds,
            'selection_roles': {'training_48': 'Four source-grouped folds; 36 fit / 12 validation per fold.',
                                'development_12': 'Already-observed supplementary diagnostics; not sole evidence for eight-per-label merge gates.',
                                'final_50': 'Reserved; never used for selection, routing, merge proposals, or extraction-prompt repair.'},
            'cross_validation_invariant': 'For each fold, regenerate local candidates, similarity proposals, parent fitting, and learned routing from that fold\'s fit sources only. Do not reuse a child policy trained on the held-out fold.',
            'representation_limitation': 'All historical 60 development cases informed design. These folds support development selection, not a globally untouched accuracy claim.',
            'sampling_scope': 'New study partitions drawn from materialized AURORA metadata, not constrained to the older seed-42 task split. Original 144 exclusions plus current 60 development sources remain excluded from the final reservation.',
            'budgets': {'m0_model_calls': 0,
                        'planned_two_stage_development_extraction_max': 120,
                        'development_flat_calls_max': 60,
                        'planned_two_stage_final_extraction_max': 100,
                        'final_flat_calls_max': 50,
                        'combined_new_model_call_ceiling': 330,
                        'max_completion_tokens_per_call': 16384,
                        'combined_completion_token_ceiling': 5406720,
                        'active_cases_max': 8,
                        'max_unique_parent_proposals': 24,
                        'max_cross_validation_plus_final_refit_builds': 5,
                        'max_parent_fit_evaluations': 120,
                        'parent_or_router_llm_calls': 0},
            'budget_scope': 'Prospective ceilings for a single validated two-stage extraction version and all four arms; cached matches reduce usage. This is not live-call authorization. Schema revisions require a new budget revision. The current four-stage v16 path is not silently substituted.',
            'exposure_caveat': 'Historical references are conservative context evidence. Unresolved legacy aliases remain recorded; the one test case without a mapped reference is not certified globally unseen.'}


def independent_check(output, selection):
    base = read(output / 'seal.json')
    for rel, h in base['files'].items():
        assert sha256((output / rel).read_bytes()).hexdigest() == h, rel
    partitions = {k: read(output / 'splits' / (k + '.json'))['cases'] for k in ('train', 'validation', 'test')}
    identities = {}; all_ids = set(); image_count = 0
    for name, rows in partitions.items():
        assert len(rows) == {'train': 48, 'validation': 12, 'test': 50}[name]
        identities[name] = set()
        for c in rows:
            assert c['id'] not in all_ids; all_ids.add(c['id'])
            for role, path in c['evidence'].items():
                data = Path(path).read_bytes()
                assert sha256(data).hexdigest() == c['image_hashes'][role]
                with Image.open(path) as im:
                    im.verify()
                image_count += 1
            with Image.open(c['evidence']['source_image']) as im:
                rgb = im.convert('RGB')
                group = sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
            assert group == c['group'] and group not in identities[name]
            identities[name].add(group)
            reference = 'no' if c['human_score'] < .5 else 'partial' if c['human_score'] < 1.5 else 'yes'
            assert reference == c['reference']
    assert not identities['train'] & identities['validation']
    assert not identities['train'] & identities['test']
    assert not identities['validation'] & identities['test']
    assert Counter(c['reference'] for c in partitions['test']) == QUOTAS
    train = {c['id']: c for c in partitions['train']}; held_all = []
    for f in selection['selection_folds']:
        assert len(f['fit_ids']) == 36 and len(f['validation_ids']) == 12
        assert set(f['fit_ids']).isdisjoint(f['validation_ids'])
        assert set(f['fit_ids']) | set(f['validation_ids']) == set(train)
        assert set(f['fit_sources']).isdisjoint(f['validation_sources'])
        assert Counter(train[i]['reference'] for i in f['validation_ids']) == dict.fromkeys(LABELS, 4)
        held_all.extend(f['validation_ids'])
    assert Counter(held_all) == Counter({i: 1 for i in train})
    test = partitions['test']; inputs = read(output / 'test_inputs.json')['cases']
    for c, r in zip(test, inputs):
        assert r == {'case': c['case'], 'input': {'instruction': c['instruction'], 'evidence': c['evidence']}}
    assert len(inputs) == 50
    budgets = selection['budgets']
    assert sum(budgets[k] for k in ('planned_two_stage_development_extraction_max', 'development_flat_calls_max',
                                   'planned_two_stage_final_extraction_max', 'final_flat_calls_max')) == 330
    assert budgets['combined_completion_token_ceiling'] == 330 * 16384
    assert selection['base_seal_sha256'] == fingerprint(output / 'seal.json')
    assert not (output / 'predictions.json').exists()
    assert not list(output.glob('ledgers/**/jobs/*.json'))
    return {'passed': True, 'partition_sizes': {k: len(v) for k, v in partitions.items()},
            'unique_sources_across_partitions': len(set.union(*identities.values())),
            'image_files_checked': image_count, 'final_label_counts': dict(Counter(c['reference'] for c in test)),
            'final_task_category_counts': dict(Counter(c['task'] for c in test)),
            'final_historical_reference_count': sum(c['historical_status'] == 'historically_referenced' for c in test),
            'selection_folds': 4, 'selection_reference_counts': dict(Counter(c['reference'] for c in train.values())),
            'current_study_final_predictions': 0, 'm0_model_calls': 0,
            'reservation_scope': 'study_relative_with_historical_exposure_disclosed',
            'strict_globally_untouched_claim': False}


def main(output, check=False):
    verify(output)
    proposed = selection_protocol(output)
    path = output / 'selection_protocol.json'
    if check:
        if read(path) != proposed:
            raise ValueError('Selection protocol no longer matches its source partitions')
    else:
        exact(path, proposed)
    result = independent_check(output, proposed)
    exact(output / 'completion_audit.json', result)
    seal = {'version': 'semantic-hierarchy-m0-completion-v1',
            'base_seal_sha256': fingerprint(output / 'seal.json'),
            'selection_protocol_sha256': fingerprint(path),
            'completion_audit_sha256': fingerprint(output / 'completion_audit.json'),
            'finalizer_sha256': fingerprint(Path(__file__))}
    if check:
        if read(output / 'completion_seal.json') != seal:
            raise ValueError('M0 completion seal changed')
    else:
        exact(output / 'completion_seal.json', seal)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    main(args.output_dir.resolve(), args.check)
