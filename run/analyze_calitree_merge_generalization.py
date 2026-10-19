"""Read-only diagnosis of saved merge generalization; no calls or fitting.

Evaluation scores of alternative policies are post-hoc diagnostics. They must
not be used to retroactively choose a winner or report a new unbiased test score.
"""
import argparse
from collections import Counter
from pathlib import Path
import json

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import FEATURES
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_tree_v8 import metrics
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import gate, predicates
from run.calitree_three_splits import read, fingerprint, ROOT

LABELS = ('No', 'Partial', 'Yes')
POSITIVE_ENDPOINTS = ('meaning_progress_requested_endpoint_all', 'meaning_endpoint_gap_none_all', 'outcome_all_true_all')


def route(tree, features):
    path = 'r'; trace = []
    if features is None:
        return None, []
    while 'feature' in tree:
        key = tree['feature']; value = features['features'][key]
        trace.append({'feature': key, 'value': value})
        tree = tree['true' if value else 'false']; path += 'T' if value else 'F'
    return path, trace


def leaves(tree, rows, conditions=(), path='r'):
    if 'feature' not in tree:
        return [{'path': path, 'conditions': [{'feature': k, 'value': v} for k, v in conditions],
            'prediction': tree['prediction'], 'sources': len(rows),
            'instructions': len({r['instruction'] for r in rows}),
            'counts': [sum(r['reference'] == i for r in rows) for i in range(3)],
            'cases': [{'case': r['case'], 'instruction': r['instruction'], 'reference': r['reference']} for r in rows]}]
    key = tree['feature']; result = []
    for value in (True, False):
        result += leaves(tree['true' if value else 'false'],
            [r for r in rows if r['features'] is not None and r['features']['features'][key] == value],
            conditions + ((key, value),), path + ('T' if value else 'F'))
    return result


def score(node, rows):
    ps = PortableRuleExecutor(node['runtime']).predict_records([r['features'] for r in rows])
    return metrics([p['prediction'] for p in ps], [r['reference'] for r in rows]), ps


def analyze(source, out):
    out.mkdir(parents=True, exist_ok=True)
    seal = read(source / 'completion_seal.json')
    assert all(fingerprint(source / name) == expected for name, expected in seal['files'].items())
    records = read(source / 'portable_records.json'); manifest = read(source / 'manifest.json')
    metadata = {r['case']: r for r in manifest['cases']}
    physical = {r['case']: r for r in read(source / 'extraction/observations.json')}
    meanings = {r['case']: r for r in read(source / 'interpretations.json')}
    pooled = read(source / 'results.json'); output = []
    for i in (1, 2, 3):
        folder = source / f'split{i}'; results = read(folder / 'results.json')
        train = read(folder / 'training_data.json'); evaluation = [records[r['case']] for r in results['arms']['merged']['cases']]
        runs = {name: read(folder / name / 'result.json') for name in ('original4_reuse', 'split8_reuse', 'semantic8_reuse')}
        selection = results['selection']; selected_run = runs[selection['selected_run']]
        parent = selected_run['registry'][selection['node_id']]
        children = [selected_run['registry'][key] for key in parent['children']]
        parent_metric, predictions = score(parent, evaluation)
        assert parent_metric == results['arms']['merged']['metrics']
        leaf_records = leaves(parent['runtime']['tree'], train)
        for leaf in leaf_records:
            leaf['evaluation_cases'] = [r['case'] for r in evaluation if route(parent['runtime']['tree'], r['features'])[0] == leaf['path']]
        alternatives = []
        for name, run in runs.items():
            for key in run['root_candidates']:
                node = run['registry'][key]; test_metric, _ = score(node, evaluation)
                decision = gate(node, children, train)
                alternatives.append({'run': name, 'node_id': key, 'selected': key == selection['node_id'] and name == selection['selected_run'],
                    'runtime_ref': node['runtime']['artifact_ref'], 'mode': node['reuse']['kind'],
                    'training': node['metrics'], 'evaluation': test_metric, 'complexity': node['complexity'],
                    'passes_gate_against_selected_children': decision['status'] == 'accepted', 'gate_reasons': decision['reasons']})
        controls = [read(path)['result'] for path in (folder / 'direct_control/fits').glob('*.json')]
        frozen = read(folder / 'frozen_policies.json')
        direct = next(n for n in controls if n and n['runtime'] == frozen['direct'])
        decision = gate(direct, children, train)
        child_results = []
        for node in children:
            metric, ps = score(node, evaluation)
            child_results.append({'node_id': node['node_id'], 'training': node['metrics'], 'evaluation': metric,
                'complexity': node['complexity'], 'predictions': ps})
        examples = []
        for row, prediction, direct_row in zip(evaluation, predictions, results['arms']['direct']['cases']):
            assert row['case'] == direct_row['case'] and row['reference'] == direct_row['reference']
            x = row['features']; path, _ = route(parent['runtime']['tree'], x)
            obs = physical[row['case']]['record']; middle = [] if obs is None else [c for c in obs['checks'].values() if c['role'] == 'intermediate']
            examples.append({'case': row['case'], 'instruction': row['instruction'], 'reference': row['reference'],
                'prediction': prediction, 'direct_prediction': direct_row['prediction'], 'leaf': path,
                'leaf_support': next((leaf['sources'] for leaf in leaf_records if leaf['path'] == path), None),
                'intermediate_checks': [{'id': c['id'], 'question': c['question'], 'state': c['state'],
                    'desired_state': c['desired_state'], 'applicability': c['observation']['applicability']} for c in middle],
                'intermediate_family': 'missing_record' if obs is None else 'empty' if not middle else
                    'all_not_applicable' if all(c['state'] == 'not_applicable' for c in middle) else 'present',
                'key_features': {key: x['features'][key] for key in (*POSITIVE_ENDPOINTS, 'intermediate_all_true_all', 'intermediate_all_false_all', 'meaning_endpoint_gap_core_endpoint_missing_all')} if x else None,
                'meaning': meanings[row['case']]['interpretation'],
                'child_predictions': [c['predictions'][len(examples)]['prediction'] for c in child_results]})
        final_decision = gate(parent, children, train)
        key = parent['runtime']['tree']['feature']
        selected_steps = read(folder / 'selected_merge_table.json')
        step_diagnostics = []
        for step in selected_steps:
            node = selected_run['registry'][step['node_id']]
            step_diagnostics.append({'step': step['step'], 'sources': step['sources'], 'training_correct': step['correct'],
                'evaluation_correct_on_same_12_as_probe': score(node, evaluation)[0]['correct'],
                'mode': step['mode'], 'rules': step['rules']})
        result = {'split': i, 'selected_run': selection['selected_run'], 'selected_node': selection['node_id'],
            'training': parent['metrics'], 'evaluation': parent_metric, 'complexity': parent['complexity'], 'mode': parent['reuse']['kind'],
            'allowed_vocabulary': parent['policy']['search'].get('allowed_predicates', []), 'reuse': parent['reuse'],
            'positive_endpoint_predicates_missing_from_final_search': [k for k in POSITIVE_ENDPOINTS if k not in parent['policy']['search'].get('allowed_predicates', [])],
            'root_feature': key, 'root_training_distribution': {str(value): {'total': sum(r['features']['features'][key] == value for r in train),
                'labels': [sum(r['features']['features'][key] == value and r['reference'] == label for r in train) for label in range(3)]} for value in (True, False)},
            'root_evaluation_distribution': dict(Counter(str(r['features']['features'][key]) if r['features'] else 'unresolved' for r in evaluation)),
            'leaf_support_histogram': dict(Counter(leaf['sources'] for leaf in leaf_records)), 'leaves': leaf_records,
            'feature_space': {'declared': len(FEATURES), 'nonconstant_training_columns': sum(0 < sum(r['features']['features'][k] for r in train) < 48 for k in FEATURES)},
            'retained_root_diagnostics': alternatives, 'children_as_unrouted_diagnostic_probes': child_results,
            'final_merge': {'before_correct_on_original_child_cohorts': sum(c['metrics']['correct'] for c in children),
                'after_correct': parent['metrics']['correct'], 'before_rules': sum(c['complexity']['rules'] for c in children),
                'after_rules': parent['complexity']['rules'], 'decision': final_decision},
            'direct': {'training': direct['metrics'], 'evaluation': results['arms']['direct']['metrics'], 'complexity': direct['complexity'],
                'used_predicates': sorted(predicates(direct['runtime']['tree'])), 'passes_same_child_gate': decision['status'] == 'accepted', 'gate_reasons': decision['reasons']},
            'examples': examples, 'selected_step_evaluation_probes': step_diagnostics,
            'run_search_counts': {name: {'pairs': run['proposal_count'], 'stop': run['stop']} for name, run in runs.items()}}
        output.append(result)
    a, b = records['N075']['features']['features'], records['N023']['features']['features']
    comparison = {'training_case': 'N075', 'training_instruction': records['N075']['instruction'], 'training_reference': records['N075']['reference'],
        'evaluation_case': 'N023', 'evaluation_instruction': records['N023']['instruction'], 'evaluation_reference': records['N023']['reference'],
        'different_portable_features': [{'feature': k, 'training': a[k], 'evaluation': b[k]} for k in FEATURES if a[k] != b[k]]}
    result = {'source': str(source.relative_to(ROOT)), 'scope': 'Post-hoc read-only diagnosis; no fitted policies or original scores changed.',
        'splits': output, 'pooled': pooled['pooled_evaluation'], 'paired': pooled['paired_merge_vs_direct'],
        'representation_example': comparison, 'new_model_calls': 0, 'new_fits': 0, 'reserved_test_predictions': 0,
        'method_references': ['https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html',
                              'https://scikit-learn.org/stable/auto_examples/tree/plot_cost_complexity_pruning.html']}
    save_json(out / 'analysis.json', result)
    write_report(result, out)
    assert all(fingerprint(source / name) == expected for name, expected in seal['files'].items())
    save_json(out / 'verification.json', {'passed': True, 'original_completion_seal_unchanged': True,
        'prediction_replay_cases': 36, 'retained_root_alternatives_replayed': sum(len(s['retained_root_diagnostics']) for s in output),
        'all_control_candidates_pass_same_child_gates': all(s['direct']['passes_same_child_gate'] for s in output),
        'new_model_calls': 0, 'new_fits': 0})
    print({'analysis': str(out / 'report.md'), 'source_preserved': True, 'splits': len(output), 'new_model_calls': 0})


def write_report(report, out):
    first = report['splits'][0]
    lines = ['# Why merging did not improve generalization', '',
        'The present gates certify local union fit, support and retention. They do not estimate out-of-sample accuracy. '
        'The strongest observed issues are a reuse-restricted candidate vocabulary, an unconditional preference for reuse categories, '
        'and proxy rules supported by very small training subsets. Upstream interpretation/reference mismatches also remain.', '',
        'This is post-hoc diagnosis of the frozen compiler-v3 study. No policy was refitted, no new model call was made, '
        'and no held-out result was used to revise selection. Alternative-root scores below are diagnostic comparisons, not new unbiased test results.', '',
        '| Split | Merged fit | Merged evaluation | Direct evaluation | Root mode | Rules |', '|---|---:|---:|---:|---|---:|']
    for s in report['splits']:
        lines.append(f"| {s['split']} | {s['training']['correct']}/48 | {s['evaluation']['correct']}/12 | {s['direct']['evaluation']['correct']}/12 | {s['mode']} | {s['complexity']['rules']} |")
    lines += ['', 'Pooled: merged 17/36, direct 18/36. Paired: four cases favor merging, five favor direct fitting, '
        '13 both correct, 14 both wrong. This is a one-case net difference, not evidence that merging universally harms generalization. '
        'Training samples overlap; evaluation sources are distinct and historically exposed.', '',
        '## Split 1: the 3/12 failure', '',
        '### A. Completed endpoints are sent to a weak Partial leaf', '',
        'The first test is `intermediate_all_true_all`: true for 12/48 training sources, but false for all 12 evaluation cases. '
        'The held-out outputs are six No, six Partial, and zero Yes. Reference-class recall is No 2/4, Partial 1/4, Yes 0/4.', '',
        'Three Yes-reference cases (N068, N102, N023) follow the same path:', '',
        '```text', 'all intermediates true? False', 'requested spatial-relation outcome? False',
        'same-instance identity for all requirements? True', 'all intermediates false? False',
        '=> Partial', '```', '',
        'That terminal rule has only two training sources: N085, “Change the background to a field of wildflowers”, '
        'and N075, “let the chair be red”; both have Partial references. Those examples do not establish that every case '
        'without an intermediate and with retained identity deserves Partial.', '',
        '| Case | Request | Cached intermediate family | Cached endpoint | Reference / merged / direct |',
        '|---|---|---|---|---|']
    for name in ('N068', 'N102', 'N023', 'N012', 'N041'):
        c = next(x for x in first['examples'] if x['case'] == name)
        endpoint = 'reached' if c['key_features']['meaning_progress_requested_endpoint_all'] else 'not established'
        lines.append(f"| {name} | {c['instruction']} | {c['intermediate_family']} | {endpoint} | {LABELS[c['reference']]} / {LABELS[c['prediction']['prediction']]} / {LABELS[c['direct_prediction']]} |")
    lines += ['', 'N068 has a completed inversion; the turning-process check is not applicable. N102 (removal) and N023 (recoloring) have no intermediate check. '
        'Under the frozen feature contract, an empty family makes both `_true_all` and `_false_all` false; all-NA also makes those two false, '
        'although the existing `_not_applicable_all` feature can distinguish it. False does not mean a negative physical observation. '
        'The selected tree fails to use that distinction or the available positive endpoint meaning on these paths. '
        'N102 additionally has a cached material-collateral flag, so endpoint completion alone is not a universally sufficient Yes rule.', '',
        '### B. The final vocabulary excludes useful endpoint conditions', '',
        'The parent inherits 17 child predicates and searches three new generic predicates, producing an allowed vocabulary of 20. '
        'The new searches are `meaning_progress_none_all`, `requires_spatial_relation`, and `intermediate_all_false_all`. '
        'It uses 14 predicates, including two new ones. The final search excludes all three positive endpoint predicates: '
        '`meaning_progress_requested_endpoint_all`, `meaning_endpoint_gap_none_all`, and `outcome_all_true_all`. '
        'The direct control does use `meaning_endpoint_gap_none_all`.', '',
        '`ReuseFits.candidates` stops at the first vocabulary budget that passes the original gates. It searches the full grammar only '
        'if reuse/refinement fails. Passing local gates can therefore prevent useful challengers from ever competing for that child pair. '
        'This is a concrete candidate-language restriction, not proof that any one omitted feature would fix generalization.', '',
        '### C. Selection prefers reuse even when alternatives pass the same gates', '',
        '| Saved root / control | Mode | Training | Evaluation | Passes gates against selected root’s children? |',
        '|---|---|---:|---:|---|']
    for a in first['retained_root_diagnostics']:
        lines.append(f"| {a['run']}{' (selected)' if a['selected'] else ''} | {a['mode']} | {a['training']['correct']}/48 | {a['evaluation']['correct']}/12 | {'Yes' if a['passes_gate_against_selected_children'] else 'No'} |")
    lines += ['| Direct fit | full grammar | 44/48 | 6/12 | Yes |', '',
        '`selection_key` ranks child-only above bounded refinement above full-grammar repair before considering accuracy or complexity. '
        'Thus the 44/48 bounded-refinement root beats existing 45/48 full-grammar roots. Those roots score 6/12, and independently pass '
        'the exact same gates against the selected immediate children. The direct control also passes them. '
        'The gates do not force the 3/12 choice. These test scores explain the failure after the fact; using them to pick a new winner would be test leakage.', '',
        '### D. The final merge sacrifices fit without compressing rules', '',
        'The children each fit 23/24, for 46/48 on their own cohorts. The parent fits 44/48, losing one correct answer per child, '
        'both within the unchanged two-case allowance. The rule count stays 19 -> 19, and node count rises 36 -> 37. '
        'This merge does not realize a compression benefit. Its root has depth six; 11/19 leaves have only two training sources. '
        'The direct control is also depth six with 19 rules, so complexity alone does not explain why its evaluation is better.', '',
        'The two immediate children score 5/12 and 3/12 when each is probed on all twelve evaluation cases; the parent scores 3/12. '
        'These are standalone probes, not a deployable routed score, ensemble, or oracle choice. No case that both children classified correctly '
        'is lost by the parent, but useful individual-child decisions are lost. Retention checks protect training-cohort counts, not these new cases.', '',
        '### E. Evidence quality remains separate from merging', '',
        'N012 has a Yes reference, but its cached meaning says the overflow endpoint is missing. The merged No follows those cached '
        'features; this cannot confidently be called a merge-only error without checking the images and annotation. '
        'N124 has a categorical outcome=true even though its evidence and text interpretation say the wrong person is laughing; '
        'the reference is Partial. Valid compiler syntax does not establish observation or interpretation truth.', '',
        'N075 (Partial training reference) and N023 (Yes evaluation reference) both have cached complete endpoints, no endpoint gap, '
        'no material collateral change, and no identity shortfall. Their 894-feature records differ in only four columns: '
        'whether a satisfied preservation check is classified as attribute or presence, with `_any`/`_all` duplicates. '
        'That points to a representation/reference mismatch and compiler-family artifacts, not an argument for learning object-name rules. '
        'There are no exact full-feature training/evaluation collisions in split 1; the existing representation is not proven mathematically incapable of separating all cases.', '',
        '## What the other splits tell us', '',
        'Split 2 also omits the two explicit semantic endpoint predicates from its final allowed search (it retains outcome_all_true_all), but gets balanced 2/4 recall in each class '
        'and ties direct fitting at 6/12. Split 3 uses inherited predicates only and improves 8/12 versus 6/12; its weakness is No recall '
        'at 1/4, including one retained observation transport failure. Reuse sometimes helps; a hard global preference for it is unsupported by these small results.', '',
        'M5 already includes genuine cross-child transfer probes, not just rule overlap. The current M7 loop evaluates all reachable '
        'child pairs per union and only then retains two policies by training rank. All nine runs stay below 1,536 pairs, and the '
        'selected fit searches are not state-budget exhausted. Changing pair-order weights or merely raising compute limits is therefore '
        'a lower-priority hypothesis than changing candidate generation, retention, and root selection.', '',
        '## Improvements with the original gates unchanged', '',
        '1. **Make reuse a tie-breaker, not the first objective.** Filter candidates with the existing gate function. Rank the survivors '
        'using source-grouped, training-only out-of-fold performance, worst-class recall and stability; then complexity; then predicate reuse. '
        'Regenerate grouping, child trees, vocabularies and parent candidates inside each inner training fold. Scoring a tree/vocabulary learned '
        'on all 48 as though its leaves were held out would leak. The model-selection motivation is explained in the '
        '[scikit-learn nested-CV example](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).', '',
        '2. **Always offer a full-grammar challenger.** Keep child-only and bounded-refinement candidates, but also offer the direct '
        'constrained fit for each parent union even when restricted reuse passes. Test every challenger against the same children and original '
        'gate. Do not replace targets with child predictions, import outside-union fitted knowledge, or deploy an unqualified control.', '',
        '3. **Preserve semantic coverage in candidate generation.** Include endpoint-first templates using existing endpoint, progress, '
        'materiality and consistency predicates, even when the immediate children omitted them. Make absent/NA/unknown check families '
        'explicit using existing state predicates, and never make an earlier visible intermediate a necessary condition for a completed endpoint. '
        'Treat this as a candidate/grammar prior, not a new universal acceptance veto or a rule that every cached endpoint must receive Yes.', '',
        '4. **Retain diversity within the beam.** The current two slots are filled by training rank and distinct artifact identity. '
        'Keep behaviorally and semantically different candidates, including more than one passing candidate from a child pair. '
        'Use training-only cross-fitted predictions and predicate-family diversity, not these twelve evaluation predictions, to measure diversity. '
        'A new study can keep the same two-slot budget for a fair comparison before considering a larger beam.', '',
        '5. **Offer pruned candidates and prefer stable support.** Keep the hard two-source/two-instruction floor; softly prefer fewer '
        'rules, shorter paths, broader semantic coverage and stable decisions under source subsampling. Generate pruned alternatives and run '
        'every one through the unchanged union/class/support/consistency/retention gates. '
        '[Cost-complexity pruning](https://scikit-learn.org/stable/auto_examples/tree/plot_cost_complexity_pruning.html) provides the standard '
        'regularization pattern; adapt it to the existing gate rather than assuming scikit-learn’s default tree satisfies CaliTree constraints.', '',
        '6. **Audit unresolved evidence/reference disagreements.** Review cases such as N012, N075, N124 and N041 with their original '
        'images and released means. Improve generic evidence/interpretation coverage or represent uncertainty in a new declared revision. '
        'Do not rewrite references, insert object-specific exceptions, or treat compiler validity as semantic correctness.', '',
        '## Proposed next experiment', '',
        'Freeze cached compiler-v3 evidence and all acceptance gates. First compare the existing selector with an always-challenger '
        'candidate pool and reuse as a soft preference. Then add leakage-safe inner selection and diversity/pruning separately. '
        'Change one component per ablation; compare matched direct fitting and report failures/infeasible folds rather than dropping them. '
        'For a 36-source inner training fold, four 9-source initialization groups are supported by the generic four-seed merger; '
        'the existing eight-by-six grouping and balanced-half helper cannot be reused unchanged at that size. This needs an explicitly '
        'declared inner grouping schedule, with the unchanged gate function and constants, followed by a full 48-source refit and the original gates. '
        'Inner groups/vocabularies must have no access to their validation fold’s labels.', '',
        'The current 36 evaluation sources are now development material. Do not tune settings on them and claim a fresh test. '
        'Freeze the revised procedure before a separately reserved evaluation; the final fifty remain untouched in this diagnosis.', '',
        'Evidence: `analysis.json` includes every split-1 case, exact paths, terminal supports, candidate roots, gate replays, child probes, '
        'all three runs, and the representation comparison. `verification.json` checks preserved source artifacts. No new calls or fits were made.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args(); analyze(args.experiment.resolve(), args.output_dir.resolve())
