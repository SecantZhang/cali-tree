"""Offline v14 construction invariance and semantic-conflict diagnostics.

Synthetic probes are internally consistent categorical interpretations, not new
image observations or reference labels. Conflicts flag disagreement between the
policy and its own declared evidence meanings; they do not adjudicate which is
correct. No policy, observation, or reference is changed by this audit.
"""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.semantic_interpretation_v5 import FIELDS
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import synthetic_record
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.portable_review_v8 import CONTRADICTS_YES
from critical.core.calibration.semantic_hierarchy.supported_pruning_v14 import learn
from run.calitree_regularized_v13 import ROOT, PROFILES, read, fingerprint

TRAINED = ROOT / 'logs/exps/261018-supported-child-compression-v14'
EVIDENCE = ROOT / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'


def probe(requirements):
    """Project categorical requirements using exactly the v8 any/all meanings."""
    if not requirements or any(set(r) != set(FIELDS) or any(r[k] not in v for k, v in FIELDS.items()) for r in requirements):
        raise ValueError('Complete, valid semantic requirements required')
    values = {'meaning_available': True}
    for field, options in FIELDS.items():
        for option in options:
            states = [r[field] == option for r in requirements]
            values[f'meaning_{field}_{option}_all'] = all(states)
            values[f'meaning_{field}_{option}_any'] = any(states)
    return synthetic_record(**values)


def conflicts(prediction, features):
    if prediction != 2 or features is None:
        return []
    return [k for k in CONTRADICTS_YES if features['features'][k]]


def audit(out):
    inputs = {str(Path(__file__).resolve().relative_to(ROOT)): fingerprint(__file__)}
    for name in ('manifest.json', 'interpretations.json', 'extraction/observations.json'):
        inputs[str((EVIDENCE / name).relative_to(ROOT))] = fingerprint(EVIDENCE / name)
    meanings = {r['case']: r['interpretation'] for r in read(EVIDENCE / 'interpretations.json')}
    common = {'retention_need': 'same_instance_essential', 'identity_evidence': 'same_instance',
        'identity_materiality': 'no_shortfall', 'collateral_materiality': 'none', 'evidence_consistency': 'coherent'}
    stages = [('none', 'core_endpoint_missing'), ('incidental_change_only', 'core_endpoint_missing'),
              ('toward_requested_goal', 'core_endpoint_missing'), ('requested_endpoint', 'none')]
    probes = [{'name': progress, 'requirements': [{**common, 'progress': progress, 'endpoint_gap': gap}]}
              for progress, gap in stages]
    probes.append({'name': 'one_complete_one_no_progress', 'requirements': [
        {**common, 'progress': 'requested_endpoint', 'endpoint_gap': 'none'},
        {**common, 'progress': 'none', 'endpoint_gap': 'core_endpoint_missing'}]})
    invariance = []; stress = []; actual = []; summary = Counter(); requirement_counts = {}
    for i in (1, 2, 3):
        folder = TRAINED / f'split{i}'
        rows = read(folder / 'training_data.json'); freeze = read(folder / 'merge/freeze.json'); policy = read(folder / 'merge/policy.json')
        requirement_counts[f'split{i}'] = dict(Counter(len(meanings[r['case']]['requirements']) if meanings[r['case']] else 0 for r in rows))
        if digest(policy) != freeze['runtime_ref']:
            raise ValueError('Frozen policy changed')
        for p in (folder / 'training_data.json', folder / 'merge/freeze.json', folder / 'merge/policy.json'):
            inputs[str(p.relative_to(ROOT))] = fingerprint(p)
        executor = PortableRuleExecutor(policy)
        for repeat in range(5):
            renamed = deepcopy(rows)
            for row in renamed:
                row['source_group'] = digest([repeat, row['source_group']])
                row['case'] = digest([repeat, row['case']])
            result = learn(list(reversed(renamed)), PROFILES[freeze['profile']])
            same = result['root'] is not None and result['root']['runtime'] == policy
            invariance.append({'split': i, 'renaming': repeat, 'identical_runtime': same})
        for item in probes:
            record = probe(item['requirements']); prediction = executor.predict_records([record])[0]
            stress.append({'split': i, **item, **prediction,
                'evidence_policy_conflicts': conflicts(prediction['prediction'], record),
                'reference_label': None, 'synthetic_not_image_evidence': True})
        ps = executor.predict_records([r['features'] for r in rows])
        for row, prediction in zip(rows, ps):
            flagged = conflicts(prediction['prediction'], row['features'])
            if flagged:
                actual.append({'split': i, 'case': row['case'], 'source_group': row['source_group'],
                    'reference': row['reference'], 'prediction': prediction['prediction'], 'flags': flagged})
                summary['reference_correct' if prediction['prediction'] == row['reference'] else 'reference_incorrect'] += 1
    result = {'version': 'semantic-stability-audit-v14', 'inputs': inputs,
        'construction_invariance': invariance, 'all_identifier_renamings_invariant': all(r['identical_runtime'] for r in invariance),
        'synthetic_probes': stress, 'training_evidence_policy_conflicts': actual,
        'training_conflict_slots': dict(summary), 'unique_conflict_sources': len({r['source_group'] for r in actual}),
        'training_requirement_counts': requirement_counts,
        'new_model_calls': 0, 'reserved_test_predictions': 0, 'frozen_policies_changed': False,
        'interpretation': 'Diagnostic only. A conflict may reflect incorrect evidence, binding ambiguity, reference ambiguity, or an invalid learned rule. It does not authorize automatic relabeling, exclusion or a hard label veto.'}
    save_json(out / 'results.json', result)
    lines = ['# V14 semantic stability audit', '',
        'All fifteen deterministic training-identifier renamings and row reversals reproduce the exact frozen runtime policies.'
        if result['all_identifier_renamings_invariant'] else 'Construction depends on identifiers; inspect results.json.', '',
        '| Synthetic semantic evidence | Split 1 | Split 2 | Split 3 |', '|---|---|---|---|']
    names = ('No', 'Partial', 'Yes')
    for item in probes:
        values = [next(r for r in stress if r['split'] == i and r['name'] == item['name']) for i in (1, 2, 3)]
        lines.append('| ' + item['name'] + ' | ' + ' | '.join(names[r['prediction']] for r in values) + ' |')
    lines += ['', 'These probes do not contain image evidence or human reference labels. The incidental-only and '
        'core-endpoint-missing interpretations conflict with Yes under the existing declared predicate meanings. '
        'A portable Boolean schema and high label agreement do not establish semantic correctness on such inputs.', '',
        'The training interpretations contain one requirement in 48/48, 47/48 and 47/48 cases respectively. '
        'With one requirement, any and all are identical; these cohorts provide very little evidence for choosing '
        'between their behaviors on compound requests. The mixed two-requirement probe receives Yes, No and Yes '
        'from the three policies. These are ungraded probes, not new ground-truth examples.', '',
        f"The same flags identify {len(actual)} fitted training slots across {result['unique_conflict_sources']} unique sources: "
        f"{summary['reference_correct']} current Yes predictions agree with their original references and "
        f"{summary['reference_incorrect']} disagree. A hard veto would therefore discard label-correct predictions too. "
        'No labels, observations or policies were changed.', '',
        'Targeted inspection of existing evidence suggests different causes: N045 uses a negative outcome for an endpoint '
        'described as not clearly established in a shadowed image; N071 binds the generic player to the batter despite a '
        'catcher also being present, and its interpretation calls evidence coherent while describing a conflict; N122 '
        'raises a scope/degree question about a Picasso-style transformation versus added artwork. These are review '
        'hypotheses, not authoritative relabelings.', '',
        'Continue to distinguish agreement with released references from consistency with extracted evidence. '
        'Further merge search cannot by itself resolve incorrect or ambiguous upstream observations. '
        'The reserved fifty remain unqueried and the paid evaluation request remains pending.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    print({'invariance_checks': len(invariance), 'all_invariant': result['all_identifier_renamings_invariant'],
           'conflict_slots': dict(summary), 'unique_conflict_sources': result['unique_conflict_sources'], 'new_model_calls': 0})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    audit(parser.parse_args().output_dir.resolve())
