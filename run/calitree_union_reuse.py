"""Reuse-first M5--M7, with M4 entirely absent from training and inference."""
import argparse
from collections import Counter
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import ReuseFits, VERSION as LEARNER_VERSION, REPAIR
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import PROFILES
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import learn, LIMITS, rank, predict
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from run.calitree_union_merge import ROOT, M0, M2, PREVIOUS, load_data, exact, read, fingerprint

VERSION = 'reuse-first-union-study-v11'
CONTROL = ROOT / 'logs/exps/261015-union-merging-v10'
RUNS = {'original4_reuse': 'original', 'split8_reuse': 'split_balanced', 'semantic8_reuse': 'semantic'}


def prepare(out):
    out.mkdir(parents=True, exist_ok=True); data = load_data()
    groups = read(CONTROL / 'groups.json')
    protocol = {'version': VERSION, 'learner': LEARNER_VERSION, 'runs': RUNS, 'limits': LIMITS,
        'repair': REPAIR, 'profiles': PROFILES, 'feature_contract_ref': read(CONTROL / 'protocol.json')['feature_contract_ref'],
        'm4_used': False, 'training_sources': 48, 'development_sources': 12,
        'union_gate': 'Strictly above 90% of all descendant sources, including failures; no collapsed class with at least two reference sources.',
        'retention': 'At most max(1, floor(child_size/10)) additional errors on each immediate child fitting set.',
        'reusability': 'At least two source cases and two instruction texts per terminal rule; same closed semantic vocabulary and written contradiction checks as M2.',
        'parent_objective': 'Recombine immediate child predicates first; accept their first passing vocabulary budget. Add at most four generic predicates ranked from union residuals before a disclosed full-grammar repair.',
        'targets': 'Original dataset reference labels only. No child-answer imitation, relabeling, duplicate cases, retries, or model calls.',
        'search': 'Balanced binary training hierarchy over four/eight seeds, two distinct retained policies per union. No scope learning, routing, or outside-union evaluation during merge acceptance.',
        'selection': 'Complete 48-source roots only. Prefer a child-only root, then bounded-refinement root, then full-grammar repair; within that category use accuracy, macro-F1, worst-class recall, complexity, and stable identity. No development label used.',
        'controls': 'The preserved v10 runs show fresh full-grammar refitting can consolidate the data. V11 measures actual child-condition reuse separately.',
        'output': 'One frozen portable policy for new-case inference, with training-only merge lineage stored separately.',
        'claims': 'Successful local consolidation and explicit rule reuse; no statistical transfer or model-repeat robustness claim.',
        'new_model_calls': 0, 'reserved_test_predictions': 0}
    exact(out / 'protocol.json', protocol); exact(out / 'data.json', data); exact(out / 'groups.json', groups)
    pins = [CONTROL / 'protocol.json', CONTROL / 'groups.json', M2 / 'completion_seal.json', M2 / 'data.json',
            PREVIOUS / 'completion_seal.json', PREVIOUS / 'data.json', M0 / 'completion_seal.json',
            M0 / 'splits/train.json', M0 / 'splits/validation.json', M0 / 'splits/test.json']
    exact(out / 'manifest.json', {'version': VERSION, 'protocol_ref': digest(protocol), 'data_ref': digest(data),
        'groups_ref': digest(groups), 'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in pins}})
    return data, groups


def train_one(out, name, replay=False):
    if name not in RUNS:
        raise ValueError('Undeclared reuse experiment')
    data, groups = prepare(out); fits = ReuseFits(out, replay)
    directory = out / 'runs' / name
    def emit(key, value):
        exact(directory / (key + '.json'), value)
    result = learn(data['train'], groups[RUNS[name]], 'reuse', fits, emit)
    exact(directory / 'registry.json', result['registry']); exact(directory / 'result.json', result)
    if result['root']:
        exact(directory / 'root_policy.json', result['root']['policy'])
        exact(directory / 'deployment_policy.json', result['root']['runtime'])
    print({'run': name, 'stop': result['stop'], 'selected_merges': result['selected_merge_count'],
           'root_correct': result['root']['metrics']['correct'] if result['root'] else None,
           'root_reuse': result['root'].get('reuse', {}).get('kind') if result['root'] else None,
           'proposals': result['proposal_count'], 'new_fits': fits.new_fits}, flush=True)
    return result


def selection_key(name, result):
    root = result['root']; kind = root.get('reuse', {}).get('kind', 'full_grammar_repair')
    return ({'child_only': 0, 'bounded_refinement': 1, 'full_grammar_repair': 2}[kind], *rank(root), name)


def merge_order(result, root):
    order = []
    def visit(node):
        for c in node['children']:
            visit(result['registry'][c])
        if node['children']:
            order.append(node['node_id'])
    visit(root)
    return order


def summarize(out):
    data, groups = prepare(out)
    results = {name: read(out / 'runs' / name / 'result.json') for name in RUNS}
    complete = [name for name, r in results.items() if r['root']]
    if not complete:
        raise ValueError('No complete accepted reuse hierarchy; goal remains unfinished')
    alternatives = [(name, results[name]['registry'][k]) for name in complete for k in results[name]['root_candidates']]
    chosen, root = min(alternatives, key=lambda pair: (*selection_key(pair[0], {'root': pair[1]}), pair[1]['node_id']))
    order = merge_order(results[chosen], root)
    exact(out / 'deployment_policy.json', root['runtime'])
    exact(out / 'selected_training_root.json', {'run': chosen, 'node_id': root['node_id'], 'training': root['metrics'],
        'source_groups': root['fit_sources'], 'selected_merge_order': order, 'reuse': root['reuse'], 'm4_used': False})
    training_predictions = predict(root, data['train'])
    dev_predictions = predict(root, data['validation'])
    summaries = {}
    for name, result in results.items():
        preferred = min((result['registry'][k] for k in result['root_candidates']),
                        key=lambda n: selection_key(name, {'root': n})) if result['root_candidates'] else None
        selected_order = merge_order(result, preferred) if preferred else []
        nodes = [result['registry'][k] for k in selected_order]
        summaries[name] = {'stop': result['stop'], 'training': result['root']['metrics'] if result['root'] else None,
            'preferred_reuse_root': {'node_id': preferred['node_id'], 'training': preferred['metrics'],
                                    'reuse': preferred['reuse']} if preferred else None,
            'retained_root_candidates': [{'node_id': result['registry'][k]['node_id'],
                'training': result['registry'][k]['metrics'], 'reuse_kind': result['registry'][k]['reuse']['kind']}
                for k in result['root_candidates']],
            'root_reuse': result['root'].get('reuse') if result['root'] else None,
            'complexity': result['root']['complexity'] if result['root'] else None,
            'seed_groups': len(groups[RUNS[name]]), 'selected_merge_count': len(nodes),
            'merge_kinds': dict(Counter(n['reuse']['kind'] for n in nodes)),
            'candidate_pairs': result['proposal_count'], 'accepted_candidates': result['accepted_proposals']}
    report = {'version': VERSION, 'selected_run': chosen, 'training': root['metrics'],
        'training_cases': [{'case': r['case'], 'reference': r['reference'], **p} for r, p in zip(data['train'], training_predictions)],
        'development': metrics([p['prediction'] for p in dev_predictions], [r['reference'] for r in data['validation']]),
        'development_cases': [{'case': r['case'], 'reference': r['reference'], **p} for r, p in zip(data['validation'], dev_predictions)],
        'runs': summaries, 'selection_used_development': False, 'm4_used': False,
        'new_model_calls': 0, 'reserved_test_predictions': 0,
        'caveat': 'Local fitting and explicit child-predicate reuse. Held-out accuracy and repeated-model robustness are not established.'}
    exact(out / 'results.json', report)
    print({'selected_run': chosen, 'training': root['metrics']['correct'], 'development': report['development']['correct'],
           'root_reuse': root['reuse']['kind'], 'm4_used': False, 'new_model_calls': 0}, flush=True)
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
