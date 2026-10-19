"""Bound-check invariance of the single frozen union judge; no model calls."""
import argparse
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence_v2 import VERSION, MAX_CHECKS
from critical.core.decision.semantic_interpretation_v5 import make_input
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.union_runtime_v11 import load
from run.calitree_union_merge import ROOT, M0, read
from tests.unit.calitree.test_stable_evidence_v5 import rename_and_reverse, duplicate


def audit(out):
    judge = load(ROOT / 'examples/calitree_union_reuse_v11')
    observed, probes = 0, []
    for partition, physical, meaning in [
        ('train', '261014-m2-m4-bound-training48-v1', '261014-m2-semantic-interpretation-train48-v5'),
        ('validation', '261014-m1-bound-evidence-development12-v2', '261014-m2-semantic-interpretation-dev12-v5')]:
        observations = {r['case']: r for r in read(ROOT / 'logs/exps' / physical / 'observations.json')}
        interpretations = {r['case']: r['interpretation'] for r in read(ROOT / 'logs/exps' / meaning / 'interpretations.json')}
        for case in read(M0 / 'splits' / (partition + '.json'))['cases']:
            raw = observations[case['case']]
            if raw['observation'] is None:
                continue
            observed += 1
            p, o = raw['compilation']['program'], raw['observation']['observation']
            value = interpretations[case['case']]
            pair = digest([VERSION, 'source_first', case['image_hashes']['source_image'], case['image_hashes']['edited_image']])
            before = project(p, o, pair, value)
            prediction = judge.predict_records([before])[0]
            assert judge.predict_bound(p, o, pair, value) == prediction
            variants = [('rename_and_reverse', None, *rename_and_reverse(p, o))]
            if len(p['checks']) < MAX_CHECKS:
                variants.extend(('duplicate', c['id'], *duplicate(p, o, c['id'])) for c in p['checks'])
            for kind, check, pp, oo in variants:
                changed = deepcopy(value)
                if kind == 'rename_and_reverse':
                    checks = {c['id']: 'c' + str(i) for i, c in enumerate(p['checks'])}
                    requirements = {r['id']: 'r' + str(i) for i, r in enumerate(p['requirements'])}
                    changed['requirements'] = {requirements[k]: {**v, 'support_check_ids': [checks[c] for c in v['support_check_ids']]}
                                               for k, v in changed['requirements'].items()}
                changed['evidence_ref'] = make_input(pp, oo, pair)['evidence_ref']
                after = project(pp, oo, pair, changed)
                assert before == after
                assert judge.predict_bound(pp, oo, pair, changed) == prediction
                probes.append({'case': case['case'], 'partition': partition, 'kind': kind, 'check': check})
    result = {'passed': True, 'observed_sources': observed, 'equivalent_check_variants': len(probes),
              'feature_changes': 0, 'prediction_changes': 0, 'trace_changes': 0,
              'router_used': False, 'new_model_calls': 0, 'reserved_test_predictions': 0,
              'scope': 'Exact check duplicate/identifier/order changes with semantic categories fixed and bindings remapped. No LLM repeat or natural-language paraphrase claim.',
              'probes': probes}
    path = out / 'invariance_audit.json'
    if path.exists():
        assert read(path) == result
    else:
        save_json(path, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    result = audit(p.parse_args().output_dir.resolve())
    print({k: v for k, v in result.items() if k != 'probes'})
