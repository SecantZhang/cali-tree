"""Router-free M5--M7 experiments on the unchanged 48 AURORA training cases."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import CONTRACT_REF, validate_record
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.union_groups_v10 import original, split_balanced, semantic, validate_partition, AXES, WEIGHTS
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import UnionFits, PROFILES
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import learn, LIMITS, rank

ROOT = Path(__file__).resolve().parents[1]
M2 = ROOT / 'logs/exps/261014-m2-portable-semantic-v8'
PREVIOUS = ROOT / 'logs/exps/261015-semantic-hierarchy-m3-m7-v9.2'
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
VERSION = 'router-free-merge-study-v10'
RUNS = {'original4_postreview': ('original', 'postreview'),
        'original4_constrained': ('original', 'constrained'),
        'split8_constrained': ('split_balanced', 'constrained'),
        'semantic8_constrained': ('semantic', 'constrained')}


def read(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def exact(path, value):
    value = json.loads(json.dumps(value))
    if Path(path).exists():
        if read(path) != value:
            raise ValueError('Frozen union study artifact changed: ' + str(path))
    else:
        save_json(path, value)


def load_data():
    for rel, expected in read(M2 / 'completion_seal.json')['files'].items():
        if fingerprint(M2 / rel) != expected:
            raise ValueError('M2 prerequisite changed')
    raw = read(PREVIOUS / 'data.json')
    keys = ('case', 'source_group', 'batch', 'reference', 'instruction', 'features')
    data = {part: [{k: r[k] for k in keys} for r in raw[part]] for part in ('train', 'validation')}
    expected = [{k: r[k] for k in keys} for r in read(M2 / 'data.json')['train']]
    if data['train'] != expected:
        raise ValueError('The new experiment changed the M2 evidence or references')
    for part, rows in data.items():
        if len(rows) != (48 if part == 'train' else 12) or len({r['source_group'] for r in rows}) != len(rows):
            raise ValueError('Incomplete source cohort')
        for r in rows:
            validate_record(r['features'])
    sets = [{r['source_group'] for r in data[p]} for p in ('train', 'validation')]
    reserved = {c['group'] for c in read(M0 / 'splits/test.json')['cases']}
    if sets[0] & sets[1] or (sets[0] | sets[1]) & reserved:
        raise ValueError('Source partition leakage')
    return data


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    data = load_data()
    protocol = {'version': VERSION, 'objective': 'Skip M4; learn successful reusable parents on complete descendant unions and iterate toward one 48-case root.',
        'feature_contract_ref': CONTRACT_REF, 'training': 48, 'development': 12, 'runs': RUNS,
        'learner_profiles': PROFILES, 'limits': LIMITS,
        'scope': 'Training-only union fitting; no instruction router, applicability scope, outside-union takeover, or per-case expert selection.',
        'seed_quality': 'Seeds are initialization candidates, not deployed specialists. Low-support or missing evidence stays in the data. Every accepted parent must pass the union gates.',
        'parent_accuracy': 'Strictly above 90% of the full original union, including unresolved cases.',
        'class_gate': 'No zero recall for a reference class represented by at least two union sources.',
        'child_retention': 'On each child fitting cohort, at most max(1, floor(child_size/10)) additional errors.',
        'reusability': 'At least two distinct sources/instructions per terminal rule; closed M2 vocabulary; no case/object/instruction literals, IDs, raw check counts, majorities, or case-signature lookup.',
        'semantic_consistency': 'No explicitly written missing-core-endpoint, wrong-target, no-progress, or incidental-only condition leading to Yes. This is a written-rule check, not a universal truth veto.',
        'search': 'Bottom-up balanced binary training hierarchies over four/eight seeds; at most two distinct policies per union and 1536 evaluated child pairs per run. Scheduler membership masks never enter inference.',
        'warm_starts': 'Only child policies whose complete fitting lineage is inside the parent union. Cold full-grammar alternatives compete using original labels.',
        'grouping': {'original': 'Unchanged four original twelve-case cohorts',
                     'split_balanced': 'Each original twelve split into two six-case cohorts, two per class',
                     'semantic': 'Eight six-case clusters from fixed semantic axes without reference-label access',
                     'axes': AXES, 'weights': WEIGHTS},
        'selection': 'Complete 48-source roots only; highest full-denominator accuracy, macro-F1, worst-class recall, then lower complexity and stable artifact identity. Separate development labels never select a run.',
        'new_model_calls': 0, 'reserved_test_predictions': 0,
        'research_claim': 'Local fitting and reusable rule language. Merged roots do not establish statistical transfer or model-repeat robustness.'}
    exact(out / 'protocol.json', protocol); exact(out / 'data.json', data)
    methods = {'original': original, 'split_balanced': split_balanced, 'semantic': semantic}
    assignments = {}
    for name, fn in methods.items():
        groups = fn(data['train']); validate_partition(groups, data['train'])
        assignments[name] = groups
    exact(out / 'groups.json', assignments)
    pins = [M2 / 'completion_seal.json', M2 / 'data.json', M2 / 'deployment_policy.json',
            PREVIOUS / 'completion_seal.json', PREVIOUS / 'data.json', M0 / 'completion_seal.json',
            M0 / 'splits/train.json', M0 / 'splits/validation.json', M0 / 'splits/test.json']
    exact(out / 'manifest.json', {'version': VERSION, 'protocol_ref': digest(protocol),
        'data_ref': digest(data), 'groups_ref': digest(assignments),
        'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in pins}})
    print({'stage': 'prepared', 'training_sources': 48, 'missing_observations': 1,
           'groups': {k: [len(g) for g in v] for k, v in assignments.items()}, 'm4_used': False}, flush=True)
    return data, assignments


def train_one(out, name, replay=False):
    if name not in RUNS:
        raise ValueError('Undeclared experiment run')
    data, assignments = prepare(out)
    group_method, engine = RUNS[name]
    fits = UnionFits(out, replay)
    directory = out / 'runs' / name
    def emit(key, value):
        exact(directory / (key + '.json'), value)
    result = learn(data['train'], assignments[group_method], engine, fits, emit)
    exact(directory / 'registry.json', result['registry'])
    exact(directory / 'result.json', result)
    if result['root']:
        exact(directory / 'root_policy.json', result['root']['policy'])
        exact(directory / 'deployment_policy.json', result['root']['runtime'])
    print({'run': name, 'stop': result['stop'], 'selected_merges': result['selected_merge_count'],
           'root_correct': result['root']['metrics']['correct'] if result['root'] else None,
           'proposals': result['proposal_count'], 'new_cold_fits': fits.new_fits}, flush=True)
    return result


def summarize(out):
    data, _ = prepare(out)
    results = {name: read(out / 'runs' / name / 'result.json') for name in RUNS}
    complete = [name for name, r in results.items() if r['root'] is not None]
    if not complete:
        raise ValueError('No complete successful hierarchy yet; continue diagnosis instead of declaring completion')
    chosen = min(complete, key=lambda name: (*rank(results[name]['root']), name))
    root = results[chosen]['root']
    # Freeze the complete root before accessing the separate twelve labels.
    exact(out / 'deployment_policy.json', root['runtime'])
    exact(out / 'selected_training_root.json', {'run': chosen, 'node_id': root['node_id'],
        'source_groups': root['fit_sources'], 'metrics': root['metrics'],
        'selected_merge_order': results[chosen]['selected_merge_order'], 'm4_used': False})
    executor = PortableRuleExecutor(root['runtime'])
    dev = executor.predict_records([r['features'] for r in data['validation']])
    from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
    report = {'version': VERSION, 'selected_run': chosen,
        'training': root['metrics'], 'development': metrics([d['prediction'] for d in dev], [r['reference'] for r in data['validation']]),
        'development_cases': [{'case': r['case'], 'reference': r['reference'], **d} for r, d in zip(data['validation'], dev)],
        'runs': {name: {'stop': r['stop'], 'training': r['root']['metrics'] if r['root'] else None,
                       'complexity': r['root']['complexity'] if r['root'] else None,
                       'seed_groups': len(read(out / 'groups.json')[RUNS[name][0]]),
                       'selected_merges': r['selected_merge_count'], 'candidate_pairs': r['proposal_count'],
                       'accepted_candidate_pairs': r['accepted_proposals']} for name, r in results.items()},
        'selection_used_development': False, 'm4_used': False, 'new_model_calls': 0, 'reserved_test_predictions': 0,
        'limitation': 'All accuracy used to accept merges is local union fitting. Separate development is diagnostic; final fifty untouched.'}
    exact(out / 'results.json', report)
    print({'selected_run': chosen, 'training': root['metrics']['correct'], 'development': report['development']['correct'],
           'm4_used': False, 'new_model_calls': 0}, flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--run', choices=[*RUNS, 'prepare', 'summary', 'all'], default='all')
    p.add_argument('--replay', action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.run == 'prepare':
        prepare(out)
    elif a.run == 'summary':
        summarize(out)
    elif a.run == 'all':
        for name in RUNS:
            train_one(out, name, a.replay)
        summarize(out)
    else:
        train_one(out, a.run, a.replay)


if __name__ == '__main__':
    main()
