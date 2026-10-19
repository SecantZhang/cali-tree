"""Offline, sequential M3--M7 study using the frozen portable M2 evidence."""
import argparse
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION as M1_VERSION
from critical.core.decision.semantic_interpretation_v5 import VERSION as INTERPRETATION_VERSION
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project, CONTRACT_REF
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.hierarchy_scopes_v9 import project as project_scope, CONTRACT_REF as SCOPE_REF
from critical.core.calibration.semantic_hierarchy.hierarchy_protocol_v9 import VERSION, PROFILES, ROUTING, SEARCH, MERGE_GATES, score
from critical.core.calibration.semantic_hierarchy.hierarchy_training_v9 import Fits, build_context, evaluate
from critical.core.calibration.semantic_hierarchy.hierarchy_builder_v9 import build
from critical.core.calibration.semantic_hierarchy.hierarchy_similarity_v9 import seed_bank, propose
from critical.core.calibration.semantic_hierarchy.hierarchy_merge_v9 import predictions, active_complexity
from critical.core.calibration.semantic_hierarchy.shared_parent_v9 import SEARCH_VERSION
from run.calitree_single_call import ROOT, read, fingerprint

M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
M2 = ROOT / 'logs/exps/261014-m2-portable-semantic-v8'
M1_TRAIN = ROOT / 'logs/exps/261014-m2-m4-bound-training48-v1'
M1_DEV = ROOT / 'logs/exps/261014-m1-bound-evidence-development12-v2'
MEANING_TRAIN = ROOT / 'logs/exps/261014-m2-semantic-interpretation-train48-v5'
MEANING_DEV = ROOT / 'logs/exps/261014-m2-semantic-interpretation-dev12-v5'
LABELS = ('no', 'partial', 'yes')
EXTRACTION = {'physical_schema': M1_VERSION, 'predicates_ref': CONTRACT_REF,
              'scope_ref': SCOPE_REF, 'interpretation_schema': INTERPRETATION_VERSION,
              'model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'presentation': 'source_first',
              'attempts_per_stage': 1, 'fresh_case_model_passes': 3,
              'study_mode': 'cached_only_zero_calls'}


def exact(path, value):
    value = json.loads(json.dumps(value))
    if path.exists():
        if read(path) != value:
            raise ValueError('A frozen hierarchy artifact changed: ' + str(path))
    else:
        save_json(path, value)


def verify_m2():
    seal = read(M2 / 'completion_seal.json')
    for rel, expected in seal['files'].items():
        if fingerprint(M2 / rel) != expected:
            raise ValueError('M2 prerequisite seal changed: ' + rel)
    runtime = read(M2 / 'deployment_policy.json')
    rows = read(M2 / 'data.json')['train']
    predictions = PortableRuleExecutor(runtime).predict_records([r['features'] for r in rows])
    m = score(rows, predictions)
    if m['correct'] != 44 or m['total'] != 48 or m['unresolved'] != 1:
        raise ValueError('The reviewed M2 prerequisite no longer replays')
    return {'sealed_files': len(seal['files']), 'metrics': m,
            'deployment_ref': runtime['artifact_ref'], 'completion_seal_sha256': fingerprint(M2 / 'completion_seal.json')}


def load_data():
    data = {}
    for partition, physical, meaning in [('train', M1_TRAIN, MEANING_TRAIN), ('validation', M1_DEV, MEANING_DEV)]:
        cases = read(M0 / 'splits' / (partition + '.json'))['cases']
        observations = {r['case']: r for r in read(physical / 'observations.json')}
        interpretations = {r['case']: r for r in read(meaning / 'interpretations.json')}
        if len(observations) != len(cases) or len(interpretations) != len(cases):
            raise ValueError('Incomplete or duplicate shared extraction inventory')
        rows = []
        for c in cases:
            observation, interpreted = observations[c['case']], interpretations[c['case']]
            program = observation['compilation']['program'] if observation['compilation'] else None
            physical_record = observation['observation']['observation'] if observation['observation'] else None
            if program is not None and program['instruction'] != c['instruction']:
                raise ValueError('Evidence belongs to another instruction')
            pair_ref = digest([M1_VERSION, 'source_first', c['image_hashes']['source_image'], c['image_hashes']['edited_image']])
            features = project(program, physical_record, pair_ref, interpreted['interpretation']) if physical_record is not None else None
            rows.append({'case': c['case'], 'source_group': c['group'],
                         'batch': c.get('batch', 'development12'), 'reference': LABELS.index(c['reference']),
                         'instruction': c['instruction'], 'features': features, 'scope': project_scope(program),
                         'program_ref': program['program_ref'] if program else None,
                         'extraction_error': observation['error'], 'interpretation_error': interpreted['error']})
        data[partition] = rows
    old = {r['case']: r for r in read(M2 / 'data.json')['train']}
    for row in data['train']:
        if any(row[k] != old[row['case']][k] for k in ('source_group', 'reference', 'instruction', 'features')):
            raise ValueError('M3 does not use the exact frozen M2 representation')
    train = {r['source_group'] for r in data['train']}
    development = {r['source_group'] for r in data['validation']}
    reserved = {c['group'] for c in read(M0 / 'splits/test.json')['cases']}
    if (len(train) != 48 or len(development) != 12 or train & development or (train | development) & reserved):
        raise ValueError('M0 source partitions violated')
    return data


def fold_assignment(rows):
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r['batch'], r['reference'])].append(r)
    result = {}
    for key in sorted(buckets):
        for i, r in enumerate(sorted(buckets[key], key=lambda r: r['source_group'])):
            result[r['source_group']] = i % 4
    return result


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    prerequisite = verify_m2()
    data = load_data()
    protocol = {'version': VERSION, 'm2_prerequisite': prerequisite,
        'feature_contract_ref': CONTRACT_REF, 'scope_contract_ref': SCOPE_REF,
        'profiles': PROFILES, 'routing': ROUTING, 'search': SEARCH, 'merge_gates': MERGE_GATES,
        'extraction': EXTRACTION, 'training_sources': 48, 'development_sources': 12,
        'local_fit_preference': 'Retain the reviewed M2 pooled fallback; local/parent rules use the same closed vocabulary and distinct-source support.',
        'folds': 'Four source-disjoint folds, stratified inside each originating batch and reference class. Inner router selection excludes the entire outer fold.',
        'routing_selection': 'Experts are validated outside their fitting sources, with out-of-source pooled comparators. Oracle outcomes are diagnostic only.',
        'routing_revision': 'V9.1 isolated route qualification regressed the combined system. V9.2 preserves that run and adds a jointly evaluated fitting guard before merge work. No final-set access.',
        'merge_selection': 'Aggregate out-of-fold actual routed predictions; all fitting and learned scopes exclude their scored sources. Reuse for proposal selection remains development.',
        'final_fifty': 'Reserved and unevaluated: M8 is outside this M3--M7 objective.',
        'calls': 0, 'attempts': 'Use cached first attempts only; original missing record stays unresolved.',
        'semantic_review': 'Reject/prune explicit contradictory Yes branches without a small-fold accuracy exception; preserve all fit losses.',
        'historical_exposure': 'These sixty sources and representation were already used in development. No fresh-test claim.'}
    exact(out / 'protocol.json', protocol)
    exact(out / 'data.json', data)
    exact(out / 'folds.json', fold_assignment(data['train']))
    sources = [M2 / 'completion_seal.json', M2 / 'deployment_policy.json', M2 / 'data.json',
               M0 / 'completion_seal.json', M0 / 'study_protocol.json', M0 / 'splits/train.json',
               M0 / 'splits/validation.json', M0 / 'splits/test.json',
               M1_TRAIN / 'observations.json', M1_DEV / 'observations.json',
               MEANING_TRAIN / 'interpretations.json', MEANING_DEV / 'interpretations.json']
    manifest = {'version': VERSION, 'protocol_ref': digest(protocol), 'data_ref': digest(data),
                'folds_ref': digest(fold_assignment(data['train'])),
                'source_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in sources}}
    exact(out / 'manifest.json', manifest)
    print({'stage': 'prerequisites', 'm2': '44/48 replay verified', 'sources': [48, 12], 'new_calls': 0}, flush=True)
    return data


def baseline(out, replay=False):
    data = prepare(out)
    rows, dev = data['train'], data['validation']
    fits = Fits(out, replay)
    folds = read(out / 'folds.json')
    contexts, outer = {}, []
    for fold in range(4):
        fitting = [r for r in rows if folds[r['source_group']] != fold]
        validation = [r for r in rows if folds[r['source_group']] == fold]
        context_path = out / 'baseline' / f'fold{fold}_context.json'
        if context_path.exists():
            context = read(context_path)
        else:
            if replay:
                raise ValueError('Missing frozen fold context')
            context = build_context(fitting, fits, EXTRACTION)
            exact(context_path, context)
        if set(context['fit_sources']) & {r['source_group'] for r in validation}:
            raise ValueError('Outer fold reached fitting or routing selection')
        result = evaluate(context, validation)
        exact(out / 'baseline' / f'fold{fold}_result.json', result)
        contexts[fold] = context; outer.extend(result['cases'])
        print({'stage': 'M3/M4', 'fold': fold, 'pooled': result['pooled_metrics']['correct'],
               'routed': result['routed_metrics']['correct'], 'routes': len(context['bundle']['routes'])}, flush=True)
    context_path = out / 'baseline' / 'full_context.json'
    if context_path.exists():
        context = read(context_path)
    else:
        if replay:
            raise ValueError('Missing full baseline context')
        context = build_context(rows, fits, EXTRACTION, pinned_pooled=read(M2 / 'deployment_policy.json'))
        exact(context_path, context)
    training = evaluate(context, rows); development = evaluate(context, dev)
    exact(out / 'baseline' / 'frozen_bundle.json', context['bundle'])
    by_source = {r['source_group']: r for r in outer}
    ordered = [by_source[r['source_group']] for r in rows]
    local = []
    for candidate in context['local_registry']:
        inside = set(candidate['fit_sources'])
        fitting = [r for r in rows if r['source_group'] in inside]
        outside = [r for r in rows if r['source_group'] not in inside]
        executor = PortableRuleExecutor(candidate['runtime'])
        local.append({'node_id': candidate['node_id'], 'profile': candidate['profile'],
            'fit_metrics': score(fitting, executor.predict_records([r['features'] for r in fitting])),
            'outside_fit_metrics': score(outside, executor.predict_records([r['features'] for r in outside])),
            'complexity': candidate['complexity'], 'specialist_eligible': candidate['specialist_eligible'],
            'eligibility_reasons': candidate['eligibility_reasons'], 'duplicate_runtime': candidate['duplicate_runtime']})
    result = {'version': VERSION, 'training': training, 'development': development,
        'pooled_oof': score(rows, [r['pooled_prediction'] for r in ordered]),
        'routed_oof': score(rows, ordered), 'oof_cases': ordered, 'local_candidates': local,
        'routes': context['selected_routes'], 'new_model_calls': 0, 'reserved_test_predictions': 0,
        'gate': {'M3': 'passed_shared_evidence_and_supported_candidates',
                 'M4': 'passed_reproducible_label_blind_routing; effectiveness_reported_separately'},
        'note': 'Local fit and source-excluding development are separate. Actual routing is scored, not oracle selection.'}
    exact(out / 'baseline' / 'results.json', result)
    local_oof = []
    for candidate in context['local_registry']:
        selected = [r for r in rows if r['source_group'] in set(candidate['fit_sources'])]
        cases = []
        for r in selected:
            fold = folds[r['source_group']]
            matching = next(c for c in contexts[fold]['local_registry'] if c['node_id'] == candidate['node_id'])
            if r['source_group'] in matching['fit_sources']:
                raise ValueError('A local OOF candidate saw its scored source')
            decision = PortableRuleExecutor(matching['runtime']).predict_records([r['features']])[0]
            cases.append({'case': r['case'], 'source_group': r['source_group'],
                          'reference': r['reference'], 'fold': fold, **decision})
        local_oof.append({'node_id': candidate['node_id'], 'profile': candidate['profile'],
                          'metrics': score(selected, cases), 'cases': cases})
    exact(out / 'baseline/local_candidate_oof.json', local_oof)
    print({'stage': 'M3/M4 complete', 'pooled_oof': result['pooled_oof']['correct'],
           'routed_oof': result['routed_oof']['correct'], 'active_routes': len(context['bundle']['routes']),
           'development': development['routed_metrics']['correct'], 'new_fits': fits.new_fits}, flush=True)
    return result


def hierarchy(out, replay=False):
    # Re-run the independent prerequisite audit before opening the merge stage.
    from run.audit_calitree_semantic_hierarchy import audit_baseline
    data = prepare(out); prerequisite = audit_baseline(out)
    exact(out / 'baseline/audit.json', prerequisite)
    rows = data['train']; folds = read(out / 'folds.json')
    context = read(out / 'baseline/full_context.json')
    fold_contexts = {f: read(out / 'baseline' / f'fold{f}_context.json') for f in range(4)}
    parent_protocol = {'version': VERSION, 'search_version': SEARCH_VERSION,
        'prerequisite_audit_ref': digest(prerequisite),
        'baseline_bundle_ref': context['bundle']['bundle_ref'],
        'search': SEARCH, 'replacement_gates': MERGE_GATES,
        'parent_profile': PROFILES['pooled'], 'parent_rule_support': 'At least two distinct sources, two instruction texts, and two originating batches per terminal rule; cross-batch constraints participate in search.',
        'warm_starts': 'Both child trees relabeled on the original-label full union, plus common-grammar shared-rule search; no child-vote targets.',
        'candidate_seeds': 'Both promoted and unpromoted eligible M3 candidates may seed a pair. The comparator is the actual frozen M4 system, which can be pooled-only.',
        'scope': 'Union of measurable child instruction scopes, learned separately inside each outer training fold. No exact-signature or case-ID routing.',
        'overlap': 'Parent replaces descendant routes at their earliest priority; a new parent from unpromoted candidates enters first. Other routes remain and the entire path is rescored.',
        'protected_scopes': 'Each child instruction scope and each descendant originating batch; batch is audit metadata only.',
        'local_stability': 'The complete full-fit system must remain strictly above 90% (at least 44/48).',
        'insufficient': 'A missing supported child scope in any outer fold prevents promotion. Small class/scope denominators remain insufficient.',
        'budgets': 'At most 24 parent proposals; maximum hierarchy depth three; at most two initial alternatives per batch. Repeated OOF use is development selection.',
        'new_model_calls': 0, 'reserved_test_predictions': 0}
    exact(out / 'parent_protocol.json', parent_protocol)
    initial_bank = seed_bank(context, rows)
    candidates, rejected = propose(set(initial_bank), initial_bank, rows, set())
    exact(out / 'proposals/initial.json', {'candidates': candidates, 'rejected_pairs': rejected,
        'gate': 'Reusable predicate/role overlap and measured source-excluding behavior; proposals alone do not authorize replacement.'})
    fits = Fits(out, replay)
    def emit(key, value):
        exact(out / 'hierarchy' / (key + '.json'), value)
    result = build(rows, folds, context, fold_contexts, fits, emit)
    # Freeze before touching the twelve supplementary development labels.
    exact(out / 'hierarchy/frozen_bundle.json', result['bundle'])
    exact(out / 'hierarchy/node_registry.json', result['node_registry'])
    exact(out / 'hierarchy/fold_bundles.json', result['fold_bundles'])
    exact(out / 'hierarchy/history.json', {'steps': result['history'], 'states': result['states']})
    lineage_nodes = {k: {'node_id': k, 'children': v['children'], 'fit_sources': v['fit_sources'],
                         'originating_batches': v['originating_batches'], 'policy_ref': v['runtime']['artifact_ref'],
                         'depth': v['depth'], 'candidate_decisions': []}
                     for k, v in result['node_registry'].items()}
    for step in result['history']:
        v = step['parent']; k = v['node_id']
        lineage_nodes.setdefault(k, {'node_id': k, 'children': v['children'], 'fit_sources': v['fit_sources'],
            'originating_batches': v['originating_batches'], 'policy_ref': v['runtime']['artifact_ref'],
            'depth': v['depth'], 'candidate_decisions': []})
        lineage_nodes[k]['candidate_decisions'].append({'proposal': step['index'], 'status': step['decision']['status']})
    exact(out / 'hierarchy/provenance_graph.json', {'nodes': lineage_nodes,
        'deployment_roots': [r['node_id'] for r in result['bundle']['routes']],
        'fallback_ref': result['bundle']['pooled']['artifact_ref'],
        'edges': [{'parent': k, 'child': child} for k, v in sorted(lineage_nodes.items()) for child in v['children']]})
    training = predictions(result['bundle'], rows)
    development = predictions(result['bundle'], data['validation'])
    baseline_result = read(out / 'baseline/results.json')
    summary = {k: v for k, v in result.items() if k not in ('bundle', 'node_registry', 'fold_bundles', 'history', 'states')}
    summary.update({'version': VERSION, 'bundle_ref': result['bundle']['bundle_ref'],
        'training_metrics': score(rows, training), 'development_metrics': score(data['validation'], development),
        'training_cases': [{'case': r['case'], 'reference': r['reference'], **d} for r, d in zip(rows, training)],
        'development_cases': [{'case': r['case'], 'reference': r['reference'], **d} for r, d in zip(data['validation'], development)],
        'comparisons': {'pooled_oof': baseline_result['pooled_oof'], 'routed_oof': baseline_result['routed_oof'],
                        'hierarchy_oof': result['final_oof_metrics'],
                        'pooled_training': baseline_result['training']['pooled_metrics'],
                        'routed_training': baseline_result['training']['routed_metrics'],
                        'hierarchy_training': score(rows, training)},
        'complexity': active_complexity(result['bundle']),
        'search_effort': {'parent_proposals': result['proposal_count'],
                         'cumulative_unique_cached_fits': len(list((out / 'fits').glob('*.json'))),
                         'selection_cohort_reused': True, 'new_model_calls': 0},
        'milestones': {'M3': 'verified_prerequisite', 'M4': 'verified_guarded_actual_routing',
                       'M5': 'measured_and_ranked_candidates', 'M6': 'full_union_candidates_evaluated_under_frozen_gates',
                       'M7': 'bounded_search_stopped_with_restorable_forest_or_pooled_fallback'}})
    exact(out / 'hierarchy/results.json', summary)
    if replay:
        exact(out / 'hierarchy/replay.json', {'exact_replay': True, 'new_fits': fits.new_fits,
            'new_model_calls': 0, 'bundle_sha256': fingerprint(out / 'hierarchy/frozen_bundle.json'),
            'results_sha256': fingerprint(out / 'hierarchy/results.json')})
    print({'stage': 'M3--M7 complete search', 'proposals': result['proposal_count'],
        'decisions': result['acceptance_counts'], 'stop': result['stop_reason'],
        'training': summary['training_metrics']['correct'], 'oof': summary['final_oof_metrics']['correct'],
        'development': summary['development_metrics']['correct'], 'new_fits': fits.new_fits,
        'new_calls': 0, 'reserved_test_predictions': 0}, flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--stage', choices=['prepare', 'baseline', 'hierarchy', 'all'], default='all')
    p.add_argument('--replay', action='store_true')
    a = p.parse_args(); out = a.output_dir.resolve()
    if a.stage == 'prepare':
        prepare(out)
    elif a.stage == 'baseline':
        baseline(out, a.replay)
    elif a.stage == 'hierarchy':
        hierarchy(out, a.replay)
    else:
        baseline(out, a.replay); hierarchy(out, a.replay)


if __name__ == '__main__':
    main()

