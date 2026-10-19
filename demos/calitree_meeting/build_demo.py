"""Export a credential-free, offline advisor demo from existing development artifacts.

Run from the repository root: .venv/bin/python demos/calitree_meeting/build_demo.py
No calls, fitting, final-test records, or mutations of experiment artifacts.
"""
from pathlib import Path
import base64
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project, synthetic_record
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import PortableSemanticTree, LIMITS
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.decision.bound_evidence_v2 import derive_record, diagnostic_readout
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load as load_union
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import gate as union_gate, proposal as union_proposal


def read(relative):
    return json.loads((ROOT / relative).read_text())


def six_case_reference():
    """Run the real M2 fitter on the six invented feature records, entirely offline."""
    mapping = {'endpoint': 'meaning_progress_requested_endpoint_all',
               'progress': 'meaning_progress_toward_requested_goal_any',
               'material': 'meaning_collateral_materiality_material_unrequested_change_any'}
    states = [(True, True), (False, True), (False, False)] * 2
    records = [synthetic_record(meaning_available=True, **{mapping['endpoint']: e,
               mapping['progress']: p, mapping['material']: False}) for e, p in states]
    targets = [2, 1, 0] * 2
    sources = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']
    reverse = {v: k for k, v in mapping.items()}
    def strip(node):
        if node['type'] == 'leaf':
            return {'prediction': node['prediction']}
        return {'feature': reverse[node['feature']], 'true': strip(node['true']), 'false': strip(node['false'])}
    profiles = {}
    for depth in (1, 2, 3):
        limits = {**LIMITS, 'max_depth': depth, 'group_depth': min(2, depth),
                  'split_candidates': 3, 'max_search_states': 256}
        model = PortableSemanticTree(limits=limits).fit(records, targets, source_groups=sources,
                                                       source_batches=['A'] * 3 + ['B'] * 3)
        profiles[str(depth)] = {'tree': strip(model.metadata()['tree']),
                               'predictions': model.predict(records),
                               'nodes': model.metadata()['search']['nodes']}
    data = {'scope': 'Actual Python M2 bounded search on six synthetic records; not image accuracy.',
            'min_support': 2, 'predicate_mapping': mapping, 'profiles': profiles}
    (OUT / 'six-case-reference.js').write_text('window.CALITREE_SIX_REFERENCE=' + json.dumps(data) + ';\n')


def export_merging(data):
    """Validate and compact the selected v11 history; never fit or score final cases."""
    folder = 'logs/exps/261015-union-reuse-v11'
    selected = read(folder + '/selected_training_root.json')
    study = read(folder + '/results.json')
    rows = read(folder + '/data.json')
    run = read(folder + '/runs/semantic8_reuse/result.json')
    hierarchy = read(folder + '/selected_hierarchy.json')
    table = read(folder + '/selected_merge_table.json')
    judge = load_union(ROOT / 'examples/calitree_union_reuse_v11')
    runtime = judge.export()['policy']
    assert selected['node_id'] == hierarchy['root'] == table[-1]['node_id']
    root = run['registry'][selected['node_id']]
    assert runtime == root['runtime'] == read(folder + '/deployment_policy.json')
    assert not study['m4_used'] and not study['selection_used_development']
    assert len(table) == 7 and len(hierarchy['nodes']) == 15
    by_source = {r['source_group']: r for r in rows['train']}
    expected = {r['case']: r for r in study['training_cases']}
    training = judge.predict_records([r['features'] for r in rows['train']])
    for row, prediction in zip(rows['train'], training):
        assert all(expected[row['case']][k] == v for k, v in prediction.items())
    validation = {r['case']: r for r in rows['validation']}
    expected_dev = {r['case']: r for r in study['development_cases']}
    for c in data['cases']:
        assert c['source_group'] == validation[c['case']]['source_group']
        assert c['features'] == validation[c['case']]['features']
        c['m2_prediction'] = c['prediction']
        c['prediction'] = judge.predict_records([c['features']])[0]
        assert all(expected_dev[c['case']][k] == v for k, v in c['prediction'].items())
    step_by_id = {s['node_id']: s['step'] for s in table}
    nodes = {}
    executors = {node_id: PortableRuleExecutor(run['registry'][node_id]['runtime'])
                 for node_id in hierarchy['nodes']}
    used_features = {'meaning_available'}
    def rule_records(tree, cohort, path='r', conditions=()):
        if 'feature' in tree:
            feature = tree['feature']
            used_features.add(feature)
            return (rule_records(tree['true'], [r for r in cohort if r['features'] and r['features']['features'][feature]],
                                 path + 'T', conditions + ((feature, True),)) +
                    rule_records(tree['false'], [r for r in cohort if r['features'] and not r['features']['features'][feature]],
                                 path + 'F', conditions + ((feature, False),)))
        assert tree['support'] == len(cohort)
        assert tree['counts'] == [sum(r['reference'] == label for r in cohort) for label in range(3)]
        return [{'path': path, 'conditions': [{'feature': f, 'value': v} for f, v in conditions],
                 'prediction': tree['prediction'], 'support': tree['support'], 'counts': tree['counts'],
                 'cases': [r['case'] for r in cohort],
                 'distinct_instructions': len({r['instruction'].strip().lower() for r in cohort}),
                 'source_groups': tree['source_groups'], 'source_batches': sorted({r['batch'] for r in cohort})}]
    for node_id in hierarchy['nodes']:
        n = run['registry'][node_id]
        nodes[node_id] = {k: n[k] for k in ('node_id', 'children', 'metrics', 'complexity', 'height', 'fit_sources', 'runtime')}
        nodes[node_id]['name'] = 'P' + str(step_by_id[node_id]) if n['children'] else 'S' + str(n['mask'].bit_length())
        nodes[node_id]['mode'] = n.get('reuse', {}).get('kind', 'seed_fit')
        nodes[node_id]['reuse'] = n.get('reuse', {})
        nodes[node_id]['leaf_support'] = n['leaf_support']
        nodes[node_id]['initialization'] = n['initialization']
        nodes[node_id]['search'] = n['policy']['search']
        nodes[node_id]['limits'] = n['policy']['limits']
        nodes[node_id]['rules'] = rule_records(n['policy']['tree'], [by_source[k] for k in n['fit_sources']])
        assert len(nodes[node_id]['rules']) == n['complexity']['rules']
        assert all(rule['support'] == support['sources'] and rule['distinct_instructions'] == support['instructions']
                   for rule, support in zip(nodes[node_id]['rules'], n['leaf_support']))
        nodes[node_id]['source_artifact'] = folder + '/runs/semantic8_reuse/result.json#registry/' + node_id
    for step in table:
        n = run['registry'][step['node_id']]
        children = [run['registry'][k] for k in n['children']]
        union = [by_source[k] for k in n['fit_sources']]
        assert set(n['fit_sources']) == set().union(*(set(c['fit_sources']) for c in children))
        assert union_gate(n, children, union) == step['decision']
        q = next(q for q in run['proposals'] if q.get('parent') == n['node_id'])
        assert union_proposal(*children, by_source) == q['diagnostic']
        step['diagnostic'] = q['diagnostic']
        step['children'] = n['children']
        step['proposal_index'] = q['index']
        step['evaluations'] = q['evaluations']
        step['fit_refs'] = q['fit_refs']
        comparisons = []
        for row in union:
            owner = next(c for c in children if row['source_group'] in c['fit_sources'])
            before = executors[owner['node_id']].predict_records([row['features']])[0]
            after = executors[n['node_id']].predict_records([row['features']])[0]
            was_correct, now_correct = before['prediction'] == row['reference'], after['prediction'] == row['reference']
            status = ('corrected' if now_correct and not was_correct else 'regressed' if was_correct and not now_correct
                      else 'changed' if before['prediction'] != after['prediction'] else 'unchanged')
            comparisons.append({'case': row['case'], 'owner': owner['node_id'], 'reference': row['reference'],
                                'before': before, 'after': after, 'status': status,
                                'children': {c['node_id']: executors[c['node_id']].predict_records([row['features']])[0]
                                             for c in children}})
        for retention in step['decision']['child_retention']:
            subset = [r for r in comparisons if r['owner'] == retention['child']]
            assert sum(r['before']['prediction'] == r['reference'] for r in subset) == retention['before']['correct']
            assert sum(r['after']['prediction'] == r['reference'] for r in subset) == retention['after']['correct']
            assert len(subset) == retention['before']['total'] == retention['after']['total']
        step['comparisons'] = comparisons
    warnings = []
    for row, prediction in zip(rows['train'], training):
        if row['features'] is None or prediction['prediction'] != 2:
            continue
        flags = [k for k in ('meaning_endpoint_gap_core_endpoint_missing_all',
                             'meaning_progress_incidental_change_only_all', 'meaning_progress_none_all')
                 if row['features']['features'][k]]
        if flags:
            assert not set(flags) & {t['feature'] for t in prediction['trace']}
            warnings.append({'case': row['case'], 'instruction': row['instruction'],
                             'reference': row['reference'], 'prediction': prediction['prediction'],
                             'cached_flags': flags, 'prediction_trace': prediction['trace']})
    cold = read('logs/exps/261015-union-merging-v10/results.json')
    cold_runtime = read('logs/exps/261015-union-merging-v10/deployment_policy.json')
    cold_executor = PortableRuleExecutor(cold_runtime)
    for partition, metric in (('train', cold['training']), ('validation', cold['development'])):
        ps = cold_executor.predict_records([r['features'] for r in rows[partition]])
        assert sum(p['prediction'] == r['reference'] for r, p in zip(rows[partition], ps)) == metric['correct']
    def leaf_count(tree):
        return 1 if 'feature' not in tree else leaf_count(tree['true']) + leaf_count(tree['false'])
    rejected = [{'index': q['index'], 'sources': len(q['sources']), 'diagnostic': q['diagnostic'],
                 'evaluations': q['evaluations']} for q in run['proposals'] if q['status'] == 'rejected']
    data['m2']['policy'] = data['policy']
    data['m2']['training_metrics'] = data['training_metrics']
    data['policy'] = runtime
    data['training_metrics'] = study['training']
    observation_source = 'logs/exps/261014-m2-m4-bound-training48-v1/observations.json'
    interpretation_source = 'logs/exps/261014-m2-semantic-interpretation-train48-v5/interpretations.json'
    observations = {r['case']: r for r in read(observation_source)}
    interpretations = {r['case']: r for r in read(interpretation_source)}
    training_examples = []
    for r in rows['train']:
        observed, interpreted = observations[r['case']], interpretations[r['case']]
        training_examples.append({'case': r['case'], 'source_group': r['source_group'], 'batch': r['batch'],
            'instruction': r['instruction'], 'reference': r['reference'], 'evidence_available': r['features'] is not None,
            'features': {k: r['features']['features'][k] for k in sorted(used_features)} if r['features'] else None,
            'program': (observed.get('compilation') or {}).get('program'), 'record': observed.get('record'),
            'interpretation': interpreted.get('interpretation'), 'error': observed.get('error') or interpreted.get('error'),
            'evidence_source': observation_source, 'interpretation_source': interpretation_source})
    data['merge'] = {'version': study['version'], 'root': selected['node_id'], 'nodes': nodes,
        'steps': table, 'training': study['training'], 'development': study['development'],
        'runs': study['runs'], 'protocol': read(folder + '/protocol.json'),
        'verification': read(folder + '/verification.json'), 'audit': read(folder + '/audit.json'),
        'package_manifest': read('examples/calitree_union_reuse_v11/manifest.json'),
        'semantic_warnings': warnings, 'rejected': rejected,
        'training_examples': training_examples,
        'candidate_pair_count': run['proposal_count'], 'accepted_candidate_count': run['accepted_proposals'],
        'fresh_refit_control': {'training': cold['training'], 'development': cold['development'],
                               'rules': leaf_count(cold_runtime['tree'])},
        'selection_used_development': False, 'm4_used': False}
    sources = [observation_source, interpretation_source, folder + '/data.json', folder + '/runs/semantic8_reuse/result.json']
    sources += [folder + '/' + name for name in ('selected_training_root.json', 'results.json', 'selected_hierarchy.json',
        'selected_merge_table.json', 'deployment_policy.json', 'verification.json', 'audit.json', 'protocol.json')]
    sources += ['docs/calitree_router_free_union_merging.md', 'docs/calitree_m3_m7_semantic_hierarchy.md',
                'examples/calitree_union_reuse_v11/manifest.json', 'examples/calitree_union_reuse_v11/judge.json']
    sources += ['critical/core/calibration/semantic_hierarchy/' + name for name in
                ('union_merges_v10.py', 'union_groups_v10.py', 'union_reuse_v11.py', 'union_runtime_v11.py')]
    for source in sources:
        data['provenance'].append(source)
        data['source_hashes'][source] = hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
    data['scope'] = 'Frozen v11 merged root on twelve historically exposed development sources; M2 retained as comparison. No new API calls or final-case records.'


def export(include_six=True):
    if include_six:
        six_case_reference()
    evidence_path = 'logs/exps/261014-m1-bound-evidence-development12-v2'
    policy_path = 'logs/exps/261014-m2-portable-semantic-v8'
    meaning_path = 'logs/exps/261014-m2-semantic-interpretation-dev12-v5'
    manifest = read(evidence_path + '/manifest.json')
    raw = {r['case']: r for r in read(evidence_path + '/observations.json')}
    meanings = {r['case']: r for r in read(meaning_path + '/interpretations.json')}
    artifact = read(policy_path + '/deployment_policy.json')
    runtime = PortableRuleExecutor(artifact)
    train = read(policy_path + '/data.json')['train']
    training_sources = {r['source_group'] for r in train}
    cases = []
    (OUT / 'media').mkdir(exist_ok=True)
    for c in manifest['cases']:
        assert c['group'] not in training_sources
        r = raw[c['case']]
        program = r['compilation']['program']
        observation = r['observation']['observation']
        record = derive_record(program, observation, r['record']['image_pair_ref'])
        assert record == r['record']
        assert diagnostic_readout(record) == r['diagnostic']
        interpretation = meanings[c['case']]['interpretation']
        features = project(program, observation, record['image_pair_ref'], interpretation)
        prediction = runtime.predict_records([features])[0]
        images = {}
        for role, path in c['evidence'].items():
            source = Path(path)
            # Existing local public benchmark assets only; no downloads.
            assert hashlib.sha256(source.read_bytes()).hexdigest() == c['image_hashes'][role]
            target = OUT / 'media' / f'{c["case"]}-{role}{source.suffix}'
            shutil.copyfile(source, target)
            images[role] = str(target.relative_to(OUT))
        cases.append(dict(case=c['case'], instruction=c['instruction'], reference=c['reference'],
                          human_score=c['human_score'], source_group=c['group'], images=images,
                          image_hashes=c['image_hashes'], program=program, record=record,
                          interpretation=interpretation, features=features, prediction=prediction,
                          diagnostic=r['diagnostic']))
    assert len(cases) == 12 and len({c['source_group'] for c in cases}) == 12
    assert all(sum(c['reference'] == label for c in cases) == 4 for label in ('no', 'partial', 'yes'))
    reviewed = read(policy_path + '/reviewed_result.json')
    replay = runtime.predict_records([r['features'] for r in train])
    assert [p['prediction'] for p in replay] == [p['prediction'] for p in reviewed['cases']]
    historical = read('logs/exps/261014-instruction-semantic-distillation-v16/results.json')
    groups = []
    for name, group in historical['groups'].items():
        arm = group['teacher_distilled']
        groups.append({'name': name, 'metrics': arm['metrics'],
                       'policy': {k: arm['policy'][k] for k in ('yes', 'partial')},
                       'limits': arm['policy']['limits']})
    data = dict(version='advisor-demo-2026-10-15', cases=cases, policy=artifact,
                training_metrics=reviewed['metrics'], candidates=read(policy_path + '/results.json')['candidate_metrics'],
                selected_profile=read(policy_path + '/results.json')['selected_profile'],
                local_groups=groups,
                training_batch_counts={g: sum(r['batch'] == g for r in train) for g in ('G1','G2','G3','G4')},
                provenance=[evidence_path + '/manifest.json', evidence_path + '/observations.json',
                            meaning_path + '/interpretations.json', policy_path + '/deployment_policy.json',
                            policy_path + '/reviewed_result.json', policy_path + '/results.json',
                            'docs/calitree_structure.md', 'docs/calitree_hierarchical_semantic_calibration_roadmap.md',
                            'docs/calitree_m2_portable_semantic_v8.md', 'docs/calitree_local_evidence_calibration.md',
                            'docs/calitree_batch_evidence_calibration.md',
                            'logs/exps/261014-instruction-semantic-distillation-v16/results.json',
                            'logs/exps/261014-frozen-semantic-transfer12-v1/report.md'],
                scope='12 historically exposed development sources; offline v8 replay for this demo. No new model calls, fitting, or reserved-final predictions.')
    data['source_hashes'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in data['provenance']}
    audit_files = ['portability_audit.json', 'equivalent_check_audit.json', 'source_invariance_audit.json',
                   'semantic_review.json', 'preservation_and_tests.json', 'rule_support_examples.json']
    data['m2'] = {name.removesuffix('.json'): read(policy_path + '/' + name) for name in audit_files}
    data['m2']['implementation_ref'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    data['m2']['completion_scope'] = 'Reusable semantic rules and strictly above 90% local agreement; statistical transfer remains separate.'
    for name in audit_files:
        source = policy_path + '/' + name
        data['provenance'].append(source)
        data['source_hashes'][source] = hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
    export_merging(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    (OUT / 'data.js').write_text('window.CALITREE_DATA = ' + payload + ';\n')
    # A single portable file works by double-click, even without a server.
    standalone = json.loads(payload)
    for c in standalone['cases']:
        for role, path in c['images'].items():
            mime = 'image/jpeg' if Path(path).suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
            c['images'][role] = 'data:' + mime + ';base64,' + base64.b64encode((OUT / path).read_bytes()).decode()
    html = (OUT / 'index.html').read_text()
    html = html.replace('<link rel="stylesheet" href="style.css">', '<style>' + (OUT / 'style.css').read_text() + '</style>')
    html = html.replace('<script src="data.js"></script>', '<script>window.CALITREE_DATA=' + json.dumps(standalone, ensure_ascii=False).replace('</', '<\\/') + ';</script>')
    html = html.replace('<script src="app.js"></script>', '<script>' + (OUT / 'app.js').read_text() + '</script>')
    html = embed_tree_assets(html)
    html = html.replace('<script src="merge-view.js"></script>', '<script>' + (OUT / 'merge-view.js').read_text() + '</script>')
    html = html.replace('<script src="merge-inspector.js"></script>', '<script>' + (OUT / 'merge-inspector.js').read_text() + '</script>')
    html = html.replace('<script src="merge-rounds.js"></script>', '<script>' + (OUT / 'merge-rounds.js').read_text() + '</script>')
    (OUT / 'calitree-demo.html').write_text(html)
    if include_six:
        six = (OUT / 'six-case-index.html').read_text()
        six = six.replace('<link rel="stylesheet" href="six-case.css">', '<style>' + (OUT / 'six-case.css').read_text() + '</style>')
        six = six.replace('<script src="six-case.js"></script>', '<script>' + (OUT / 'six-case.js').read_text() + '</script>')
        six = embed_tree_assets(six)
        for name in ('six-search.js', 'six-case-reference.js'):
            six = six.replace(f'<script src="{name}"></script>', '<script>' + (OUT / name).read_text() + '</script>')
        (OUT / 'six-case-demo.html').write_text(six)
    correct = sum(c['prediction']['prediction'] == ('no','partial','yes').index(c['reference']) for c in cases)
    print(json.dumps({'cases': len(cases), 'checks': sum(len(c['program']['checks']) for c in cases),
                      'merged_demo_correct': correct, 'merged_training_correct': data['training_metrics']['correct'],
                      'm2_training_correct': reviewed['metrics']['correct'], 'selected_merges': len(data['merge']['steps']),
                      'new_model_calls': 0, 'final_test_records_read': 0,
                      'standalone': str(OUT / 'calitree-demo.html')}))


def embed_tree_assets(html):
    return html.replace('<link rel="stylesheet" href="rule-tree.css">', '<style>' + (OUT / 'rule-tree.css').read_text() + '</style>').replace(
        '<script src="rule-tree.js"></script>', '<script>' + (OUT / 'rule-tree.js').read_text() + '</script>')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-only', action='store_true', help='Preserve the separate six-case teaching version.')
    export(include_six=not parser.parse_args().full_only)
