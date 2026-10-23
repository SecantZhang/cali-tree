"""Diagnose bank-2 losses and fit/replay disagreement coverage on cached data.

All 116 recent cases are development data for this revision. Source-held-out
replays exclude the held source from the added guard and use the corresponding
already source-disjoint parent policy. No model calls or tree refits.
"""
import argparse
from pathlib import Path

from critical.core.calibration import disagreement_coverage_v36 as risk
from critical.core.decision.artifacts import digest, save_json
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint
from run.calitree_guarded_generalization_v32 import load_pilot, context
from run.calitree_fallback_routing_v34 import old_examples
from run.collect_calitree_aurora_pilot_v29r1 import metrics

V35 = ROOT / 'logs/exps/261020-regular-aware-v35'
FORWARD = ROOT / 'logs/exps/261020-guarded-forward-v32-r1'


def inputs():
    predictions = {r['case']: r for r in read(FORWARD / 'supplemental_v35/full_predictions.json')}
    forward = [{**e, **predictions[e['case']], 'cohort': 'forward36'} for e in read(FORWARD / 'inputs.json')]
    pilot = [{**e, 'cohort': 'pilot80'} for e in load_pilot()]
    assert len(pilot) == 80 and len(forward) == 36
    assert len({e['source_group'] for e in pilot + forward}) == 52
    assert len({e['case'] for e in pilot + forward}) == 116
    return pilot + forward


def parent_path(bank, group=None):
    if group is not None:
        groups = sorted({e['source_group'] for e in load_pilot()})
        if group in groups:
            return V35 / f'fold{groups.index(group):02}/split{bank}/gate.json'
    return V35 / f'full/split{bank}/gate.json'


def measure(gate, e):
    if e['features'] is None:
        return {'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
    return gate.resolve(e['program'], e['features'], e['regular'], corrections=False)


def make_record(e, before, after):
    return {'case': e['case'], 'source_group': e['source_group'], 'cohort': e['cohort'],
            'reference': e['reference'], 'regular': e['regular'], 'routes': {'v35': before, 'v36': after},
            'v35': before['prediction'] if before['covered'] else e['regular'],
            'v36': after['prediction'] if after['covered'] else e['regular']}


def summary(rows):
    return {cohort: {arm: metrics([r for r in rows if cohort == 'all' or r['cohort'] == cohort], arm)
                    for arm in ('regular', 'v35', 'v36')} for cohort in ('all', 'pilot80', 'forward36')}


def retain(bank, base, gate, examples):
    retained = 0
    for e in examples:
        before = measure(base, e)
        after = measure(gate, e)
        if before['covered'] and before['prediction'] == e['reference']:
            assert after['covered'] and after['prediction'] == before['prediction']
            retained += 1
    rows, _, _, _, _, _ = context(bank)
    by_case = {e['case']: e for e in old_examples(bank)}
    for r in rows:
        e = by_case[r['case']]
        decision = measure(gate, e)
        assert decision['covered'] and decision['prediction'] == r['reference']
    return {'local_retained': len(rows), 'correct_routes_retained': retained}


def bank2_diagnosis(examples, base):
    result = []
    for e in examples:
        if e['cohort'] != 'forward36':
            continue
        before = measure(base, e)
        if before['covered'] and before['prediction'] != e['reference']:
            result.append({'case': e['case'], 'instruction': e['program']['instruction'],
                           'reference': e['reference'], 'regular': e['regular'], 'tree': before['prediction'],
                           'harmful_override': e['regular'] == e['reference'], 'route': before})
    return result


def run(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    out.mkdir(parents=True)
    examples = inputs()
    groups = sorted({e['source_group'] for e in examples})
    olds = {b: old_examples(b) for b in (1, 2, 3)}
    assert all(not set(groups) & {e['source_group'] for e in old} for old in olds.values())
    protocol = {'version': risk.VERSION, 'max_clauses': 4, 'new_model_calls': 0, 'tree_refits': 0,
                'calibration': 'Both the 80-case pilot and 36-case forward set are now development data. No fresh validation claimed.',
                'guard': 'For each tree/regular disagreement pair, retain every correct tree decision and learn <=4 clauses of <=2 declared literals to reject harmful overrides.',
                'source_replay': '52 held-source folds. Pilot folds use the original source-excluded v35 parent; forward folds use the parent fitted before any forward labels. Added guard excludes the held source in both cohorts.',
                'mode': 'Verification only. No new correction regions or expert labels.'}
    save_json(out / 'protocol.json', protocol)
    full_rows, fold_rows, membership, refs = [], [], [], {}
    prepared_cache = {}

    def prepared(bank, path):
        key = (bank, str(path))
        if key not in prepared_cache:
            base = risk.aware.RegularAwareGate.restore(read(path))
            old = risk.prepare(base, olds[bank])
            protected = [e for e in old if e['prediction'] == e['reference']]
            prepared_cache[key] = (base, protected, risk.prepare(base, examples))
        return prepared_cache[key]

    for bank in (1, 2, 3):
        base, protected, calibration = prepared(bank, parent_path(bank))
        gate = risk.fit(base, protected, calibration)
        save_json(out / f'full/split{bank}/gate.json', gate.export())
        check = retain(bank, base, gate, olds[bank] + examples)
        save_json(out / f'full/split{bank}/retention.json', check)
        refs[str(bank)] = gate.artifact['artifact_ref']
        for e in examples:
            full_rows.append({**make_record(e, measure(base, e), measure(gate, e)), 'bank': bank})
        if bank == 2:
            save_json(out / 'bank2_wrong_acceptances.json', bank2_diagnosis(examples, base))
    for fold, group in enumerate(groups):
        held = [e for e in examples if e['source_group'] == group]
        for bank in (1, 2, 3):
            path = parent_path(bank, group)
            base, protected, all_calibration = prepared(bank, path)
            calibration = [e for e in all_calibration if e['source_group'] != group]
            assert all(e['source_group'] != group for e in protected + calibration)
            gate = risk.fit(base, protected, calibration)
            save_json(out / f'fold{fold:02}/split{bank}/support.json', gate.support)
            check = retain(bank, base, gate, olds[bank])
            membership.append({'fold': fold, 'bank': bank, 'held_source': group, 'held_cases': [e['case'] for e in held],
                               'training_sources': sorted(set(groups) - {group}), 'parent_path': str(path),
                               'parent_sha256': fingerprint(path), 'support_ref': gate.support['artifact_ref'], **check})
            for e in held:
                fold_rows.append({**make_record(e, measure(base, e), measure(gate, e)), 'bank': bank})
        if (fold + 1) % 4 == 0 or fold + 1 == len(groups):
            print({'source_folds_completed': fold + 1, 'total': len(groups)}, flush=True)
    result = {'version': risk.VERSION, 'full_development': {}, 'source_held_out': {}, 'new_model_calls': 0,
              'notes': ['Full development scores include fitting on these labels.', 'Source-held-out scores are exploratory after design review; not fresh unseen validation.']}
    for bank in (1, 2, 3):
        result['full_development'][str(bank)] = summary([r for r in full_rows if r['bank'] == bank])
        result['source_held_out'][str(bank)] = summary([r for r in fold_rows if r['bank'] == bank])
    save_json(out / 'development_predictions.json', full_rows)
    save_json(out / 'source_held_out_predictions.json', fold_rows)
    save_json(out / 'folds.json', membership)
    save_json(out / 'results.json', result)
    save_json(out / 'freeze.json', {'gates': refs, 'protocol_ref': digest(protocol), 'training_sources': groups})
    files = [Path(__file__).resolve(), Path(risk.__file__).resolve(), Path(risk.aware.__file__).resolve()]
    save_json(out / 'manifest.json', {'protocol_ref': digest(protocol), 'code_hashes': {str(p): fingerprint(p) for p in files},
              'source_hashes': {str(p): fingerprint(p) for p in (FORWARD / 'completion_seal.json', V35 / 'freeze.json')}})
    (out / 'run.log').write_text('52-source disagreement-support replay; all local and prior correct routes retained. No model calls.\n')
    (out / 'llm-histories.log').write_text('Zero model calls; cached evidence and regular judgments only.\n')
    for b in (1, 2, 3):
        for kind in ('full_development', 'source_held_out'):
            print(b, kind, {c: {a: m['correct'] for a, m in v.items()} for c, v in result[kind][str(b)].items()}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())
