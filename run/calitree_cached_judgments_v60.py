"""Read approved cached regular judgments; never accesses reserved cases."""
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_continuous_policy_v43 import EXPANSION
from run.calitree_matched_policy_v58 import COLLECTION


def judgments(examples):
    _, _, _, _, _, _, prior, _ = old_inputs(PREVIOUS, 1)
    manifest = read(prior / 'manifest.json')
    original = {job['case']: key for key, job in manifest['jobs'].items() if job['request']['stage'] == 'flat_judge'}
    result, sources = {}, {}
    for e in examples:
        case = e['case']
        if case.startswith('N'):
            if case in original:
                path = prior / 'responses' / (original[case] + '.json')
            else:
                path = ROOT / 'logs/exps/261020-guarded-forward-v32-r1/regular_responses' / (case + '.json')
            value = read(path)['judgment']
        elif case.startswith('P'):
            path = ROOT / 'logs/exps/261020-aurora-pilot80-v29-run1/collection/cases' / (case + '.json')
            value = read(path)['regular']
        else:
            directory = EXPANSION if case.startswith('T') else COLLECTION if case.startswith('S') else None
            if directory is None:
                raise ValueError('Unknown fitting case family')
            path = directory / 'cases' / (case + '.json')
            value = read(path)['regular_judgment']
        label = ('no', 'partial', 'yes').index(value['label']) if value is not None and value['label'] in ('no', 'partial', 'yes') else -1
        assert label == e['regular'], case
        result[case] = value
        sources[str(path)] = fingerprint(path)
    return result, sources
