"""Offline replay, source-exclusion and local-retention audit of v32-v35.

The pilot was inspected before policy design. Source cross-fitting verifies the
procedure, not a claim of untouched evaluation. No model clients are created.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.calibration import regular_aware_gate_v35 as aware
from critical.core.decision.artifacts import digest, save_json
from run.calitree_aurora_pilot_v29 import ROOT, read, fingerprint, exact
from run.calitree_guarded_generalization_v32 import load_pilot, context
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_regular_aware_v35 import build

V32 = ROOT / 'logs/exps/261020-guarded-generalization-v32-r1'
V34 = ROOT / 'logs/exps/261020-fallback-routing-v34'
V35 = ROOT / 'logs/exps/261020-regular-aware-v35'
FORWARD = ROOT / 'logs/exps/261020-guarded-forward-v32-r1'


def manifest_check(directory):
    manifest = read(directory / 'manifest.json')
    assert digest(read(directory / 'protocol.json')) == manifest['protocol_ref']
    for p, h in manifest['code_hashes'].items():
        assert fingerprint(p) == h, p
    return manifest


def check_merges(raw, final, report, rows, programs):
    merging = aware.fixed.merging
    bank = merging.definitions(raw)
    probes = merging.prepared(raw, [{'program': programs[r['source_group']], 'features': r['features']} for r in rows])
    for event in report['accepted']:
        p = event['parent']
        parent = {'prediction': p['prediction'], 'term': frozenset((c['feature'], c['value']) for c in p['conditions']),
                  'tasks': set(p['scope_refs']), 'experts': set(p['expert_refs'])}
        children = [bank[k] for k in event['children']]
        assert aware.fixed.preserve_obligations(children, parent)['passed']
        _, _, parent_sources = merging.support(parent, rows, programs, probes)
        for child in children:
            _, _, sources = merging.support(child, rows, programs, probes)
            assert sources <= parent_sources
        proposal = {k: v for k, v in bank.items() if k not in event['children']}
        proposal['parent'] = parent
        packed = merging.pack(raw, proposal, rows, programs, probes)
        assert packed.artifact['artifact_ref'] == event['gate_ref']
        bank = merging.definitions(packed)
    assert bank == merging.definitions(final.base)
    return len(report['accepted'])


def audit(out):
    out.mkdir(parents=True, exist_ok=True)
    for directory in (V32, V34, V35):
        manifest_check(directory)
    pilot = load_pilot()
    groups = sorted({e['source_group'] for e in pilot})
    contexts = {bank: context(bank) for bank in (1, 2, 3)}
    old = {bank: old_examples(bank) for bank in (1, 2, 3)}
    assert all(not {e['source_group'] for e in old[bank]} & set(groups) for bank in old)
    stored = {r['case']: r for r in read(V35 / 'crossfit_predictions.json')}
    utility_stored = {r['case']: r for r in read(V34 / 'crossfit_predictions.json')}
    fold_rows = read(V32 / 'results.json')['folds']
    totals = Counter()
    records = []
    for fold, group in enumerate(groups):
        training = [e for e in pilot if e['source_group'] != group]
        held = [e for e in pilot if e['source_group'] == group]
        assert len(training) == 75 and len(held) == 5
        for bank in (1, 2, 3):
            membership = next(e for e in fold_rows if e['fold'] == fold and e['bank'] == bank)
            assert membership['held_source'] == group
            assert membership['training_sources'] == sorted({e['source_group'] for e in training})
            assert membership['held_cases'] == [e['case'] for e in held]
            base = aware.fixed.VerifiedRegionGate.restore(read(V32 / f'fold{fold:02}/split{bank}/guarded_merge.json'))
            gate = aware.RegularAwareGate.restore(read(V35 / f'fold{fold:02}/split{bank}/gate.json'))
            # Refit independently from the frozen raw inputs and compare artifacts.
            refitted = build(bank, base, training)
            assert refitted.export() == gate.export()
            utility = aware.utility.SemanticFallbackRouter.restore(read(V34 / f'fold{fold:02}/split{bank}/router.json'))
            assert utility.export() == aware.utility.fit(base, old[bank] + training).export()
            rows, programs, raw, _, _, _ = contexts[bank]
            merge_report = read(V32 / f'fold{fold:02}/split{bank}/merge_fit.json')
            totals['proved_merges'] += check_merges(raw, base, merge_report, rows, programs)
            old_by_case = {e['case']: e for e in old[bank]}
            for row in rows:
                e = old_by_case[row['case']]
                route = gate.resolve(e['program'], e['features'], e['regular'])
                assert route['covered'] and route['prediction'] == row['reference']
                totals['local_routes_checked'] += 1
            for e in old[bank]:
                before = raw.select(e['program'], e['features'])
                if before['covered']:
                    route = gate.resolve(e['program'], e['features'], e['regular'])
                    assert route['covered'] and route['prediction'] == before['prediction'] == e['reference']
                    totals['old_correct_routes_checked'] += 1
            for e in held:
                for name, corrections in (('regular_aware', False), ('regular_aware_correction', True)):
                    route = gate.resolve(e['program'], e['features'], e['regular'], corrections=corrections) if e['features'] is not None else {
                        'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
                    arm = f'{name}_split{bank}'
                    assert route == stored[e['case']]['routes'][arm]
                    prediction = route['prediction'] if route['covered'] else e['regular']
                    assert prediction == stored[e['case']][arm]
                    totals[arm] += prediction == e['reference']
                    totals['predictions_replayed'] += 1
                utility_route = utility.resolve(e['program'], e['features'], e['regular']) if e['features'] is not None else {
                    'covered': False, 'prediction': -1, 'reason': 'missing_or_invalid_evidence', 'matches': []}
                assert utility_route == utility_stored[e['case']]['routes'][f'utility_split{bank}']
            records.append({'fold': fold, 'held_source': group, 'bank': bank, 'training_cases': len(training),
                            'local_accuracy_and_coverage_preserved': True, 'exact_refit': True})
        print({'audited_folds': fold + 1, 'total': len(groups)}, flush=True)
    for bank in (1, 2, 3):
        name = f'regular_aware_correction_split{bank}'
        assert totals[name] == read(V35 / 'results.json')['crossfit'][name]['correct']
        gate = aware.RegularAwareGate.restore(read(V35 / f'full/split{bank}/gate.json'))
        base = aware.fixed.VerifiedRegionGate.restore(read(V32 / f'full/split{bank}/guarded_merge.json'))
        assert gate.export() == build(bank, base, pilot).export()
    report = {'passed': True, 'folds': records, 'counts': dict(totals), 'all_siblings_excluded_from_fitting': True,
              'old_and_pilot_sources_disjoint': True, 'new_model_calls': 0, 'evaluation_is_exploratory': True}
    save_json(out / 'verification.json', report)
    (out / 'run.log').write_text('48 source/bank folds refitted; frozen predictions, local routes and merge proofs replayed.\n')
    (out / 'llm-histories.log').write_text('Zero model calls.\n')
    save_json(out / 'manifest.json', {'code_hashes': {str(Path(__file__).resolve()): fingerprint(__file__)},
              'parent_freeze_hashes': {str(d / 'freeze.json'): fingerprint(d / 'freeze.json') for d in (V32, V34, V35)}})
    print({k: v for k, v in report.items() if k != 'folds'}, flush=True)


def freeze_forward():
    """Supplement the existing plan without changing its original predictions."""
    from run.collect_calitree_guarded_forward_v32 import verify
    verify(FORWARD)
    inputs = read(FORWARD / 'inputs.json')
    new_fit = set(read(V35 / 'freeze.json')['training_source_groups'])
    for bank in (1, 2, 3):
        new_fit.update(e['source_group'] for e in old_examples(bank))
    assert not new_fit & {e['source_group'] for e in inputs}
    models = {}
    for bank in (1, 2, 3):
        artifact = read(V35 / f'full/split{bank}/gate.json')
        aware.RegularAwareGate.restore(artifact)
        exact(FORWARD / f'supplemental_v35/split{bank}.json', artifact)
        models[str(bank)] = artifact['artifact_ref']
    sources = (aware.__file__, aware.utility.__file__, aware.utility.warrant.__file__, aware.fixed.__file__,
               ROOT / 'run/calitree_regular_aware_v35.py', Path(__file__).resolve())
    plan = {'version': aware.VERSION, 'gates': models, 'source_freeze_sha256': fingerprint(V35 / 'freeze.json'),
            'code_hashes': {str(Path(p).resolve()): fingerprint(p) for p in sources},
            'forward_inputs_sha256': fingerprint(FORWARD / 'inputs.json'), 'source_disjoint_from_all_new_fitting': True,
            'policy_fixed_before_new_regular_collection': not (FORWARD / 'ledger').exists(),
            'additional_requests': 0, 'new_model_calls': 0, 'legacy_research_exposure': True}
    assert plan['policy_fixed_before_new_regular_collection']
    exact(FORWARD / 'supplemental_v35/freeze.json', plan)
    print({'supplemental_forward_models_frozen': models, 'new_model_calls': 0}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--freeze-forward', action='store_true')
    args = parser.parse_args()
    if args.output_dir:
        audit(args.output_dir.resolve())
    if args.freeze_forward:
        freeze_forward()
    if not args.output_dir and not args.freeze_forward:
        parser.error('Choose --output-dir or --freeze-forward')
