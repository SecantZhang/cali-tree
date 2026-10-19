"""Exact check-identity/order/duplication probes with cached meanings fixed."""
import argparse
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import MAX_CHECKS
from critical.core.decision.semantic_interpretation_v5 import make_input
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.calibration.semantic_hierarchy.hierarchy_runtime_v9 import HierarchyExecutor
from critical.core.calibration.semantic_hierarchy.hierarchy_scopes_v9 import project as scope_project
from run.calitree_semantic_hierarchy import read, M0, M1_TRAIN, M1_DEV, MEANING_TRAIN, MEANING_DEV, M1_VERSION
from tests.unit.calitree.test_stable_evidence_v5 import rename_and_reverse, duplicate


def audit(out):
    executor = HierarchyExecutor(read(out / 'hierarchy/frozen_bundle.json'))
    parents = read(out / 'hierarchy/history.json')['steps']
    policies = {s['parent']['runtime']['artifact_ref']: PortableRuleExecutor(s['parent']['runtime']) for s in parents}
    observed, probes, decisions = 0, [], 0
    for partition, physical, meaning in [('train', M1_TRAIN, MEANING_TRAIN), ('validation', M1_DEV, MEANING_DEV)]:
        originals = {r['case']: r for r in read(physical / 'observations.json')}
        interpretations = {r['case']: r['interpretation'] for r in read(meaning / 'interpretations.json')}
        for case in read(M0 / 'splits' / (partition + '.json'))['cases']:
            raw = originals[case['case']]
            if raw['observation'] is None:
                continue
            observed += 1
            program, observation = raw['compilation']['program'], raw['observation']['observation']
            interpretation = interpretations[case['case']]
            pair = digest([M1_VERSION, 'source_first', case['image_hashes']['source_image'], case['image_hashes']['edited_image']])
            before = project(program, observation, pair, interpretation)
            scope = scope_project(program)
            base = executor.predict_records([before], [scope])
            assert executor.predict_bound(program, observation, pair, interpretation) == base[0]
            parent_predictions = {k: m.predict_records([before]) for k, m in policies.items()}
            variants = [('rename_and_reverse', None, *rename_and_reverse(program, observation))]
            if len(program['checks']) < MAX_CHECKS:
                variants.extend(('duplicate', c['id'], *duplicate(program, observation, c['id'])) for c in program['checks'])
            for kind, check, p, o in variants:
                value = deepcopy(interpretation)
                if kind == 'rename_and_reverse':
                    checks = {c['id']: 'c' + str(i) for i, c in enumerate(program['checks'])}
                    requirements = {r['id']: 'r' + str(i) for i, r in enumerate(program['requirements'])}
                    value['requirements'] = {requirements[k]: {**v, 'support_check_ids': [checks[c] for c in v['support_check_ids']]}
                                             for k, v in value['requirements'].items()}
                value['evidence_ref'] = make_input(p, o, pair)['evidence_ref']
                after = project(p, o, pair, value)
                assert after == before, (case['case'], kind, check, 'features')
                assert scope_project(p) == scope, (case['case'], kind, 'instruction_scope')
                assert executor.predict_records([after], [scope_project(p)]) == base
                for key, model in policies.items():
                    assert model.predict_records([after]) == parent_predictions[key]
                decisions += 1 + len(policies)
                probes.append({'case': case['case'], 'partition': partition, 'variant': kind, 'check': check})
    result = {'passed': True, 'observed_sources': observed, 'equivalent_check_variants': len(probes),
              'unique_parent_policies': len(policies), 'prediction_and_trace_comparisons': decisions,
              'feature_changes': 0, 'scope_changes': 0, 'decision_changes': 0, 'trace_changes': 0,
              'scope': 'Exact bound-check duplication and local identifier/order transformations. Cached semantic categories stay fixed; binding references and cited IDs are consistently remapped. No paraphrase or repeated-model robustness claim.',
              'new_model_calls': 0, 'final_test_predictions': 0, 'details': probes}
    path = out / 'hierarchy/invariance_audit.json'
    if path.exists():
        assert read(path) == result
    else:
        save_json(path, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    result = audit(p.parse_args().output_dir.resolve())
    print({k: v for k, v in result.items() if k != 'details'})
