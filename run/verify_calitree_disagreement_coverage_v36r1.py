"""Independently refit/replay v36 guards and retain bank-2 rule provenance."""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache
from critical.core.optimization.prompt.calitree.verified_semantic_judge import VerifiedSemanticJudge
from run.calitree_disagreement_coverage_v36r1 import inputs, parent_path, measure, retain, risk, FORWARD, V35, protected_variants
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_aurora_pilot_v29 import ROOT, IDENTITY, read, fingerprint
from run.verify_calitree_regular_aware_runtime_v35 import FlatStub, FailedEvidence
from run.calitree_guarded_generalization_v32 import context
from run.verify_calitree_guarded_forward_completion import count_metrics


def audit(out):
    manifest = read(out / 'manifest.json')
    assert manifest['protocol_ref'] == digest(read(out / 'protocol.json'))
    for p, expected in {**manifest['code_hashes'], **manifest['source_hashes']}.items():
        assert fingerprint(p) == expected, p
    examples = inputs()
    by_case = {e['case']: e for e in examples}
    olds = {b: old_examples(b) for b in (1, 2, 3)}
    memo = {}
    def prepared(bank, path):
        key = (bank, str(path))
        if key not in memo:
            base = risk.aware.RegularAwareGate.restore(read(path))
            protected = protected_variants(base, olds[bank])
            memo[key] = (base, protected, risk.prepare(base, examples))
        return memo[key]
    rows = read(out / 'source_held_out_predictions.json')
    full = read(out / 'development_predictions.json')
    folds = read(out / 'folds.json')
    held_count = 0
    for f in folds:
        bank, group = f['bank'], f['held_source']
        path = parent_path(bank, group)
        assert str(path) == f['parent_path'] and fingerprint(path) == f['parent_sha256']
        assert group not in f['training_sources']
        assert set(f['training_sources']) == {e['source_group'] for e in examples} - {group}
        base, protected, calibration = prepared(bank, path)
        training = [e for e in calibration if e['source_group'] != group]
        assert not {group} & {e['source_group'] for e in protected + training}
        gate = risk.fit(base, protected, training)
        assert gate.support == read(out / f"fold{f['fold']:02}/split{bank}/support.json")
        for e in examples:
            if e['source_group'] != group:
                continue
            recorded = next(r for r in rows if r['bank'] == bank and r['case'] == e['case'])
            assert recorded['routes']['v35'] == measure(base, e)
            assert recorded['routes']['v36'] == measure(gate, e)
            held_count += 1
    local, old_retained, label_variants = 0, 0, 0
    gates = {}
    for bank in (1, 2, 3):
        gate = risk.DisagreementCoverageGate.restore(read(out / f'full/split{bank}/gate.json'))
        base, protected, calibration = prepared(bank, parent_path(bank))
        assert gate.export() == risk.fit(base, protected, calibration).export()
        check = retain(bank, base, gate, olds[bank])
        local += check['local_retained']
        old_retained += check['correct_routes_retained']
        gates[bank] = gate
        for prior in olds[bank]:
            for label in (-1, 0, 1, 2):
                variant = {**prior, 'regular': label}
                before, after = measure(base, variant), measure(gate, variant)
                if before['covered'] and before['prediction'] == prior['reference']:
                    assert after['covered'] and after['prediction'] == before['prediction']
                    label_variants += 1
        for e in examples:
            record = next(r for r in full if r['bank'] == bank and r['case'] == e['case'])
            assert record['routes']['v36'] == measure(gate, e)
    result = read(out / 'results.json')
    for name, data in (('full_development', full), ('source_held_out', rows)):
        for bank in (1, 2, 3):
            for cohort in ('all', 'pilot80', 'forward36'):
                selected = [r for r in data if r['bank'] == bank and (cohort == 'all' or r['cohort'] == cohort)]
                for arm in ('regular', 'v35', 'v36'):
                    assert count_metrics(selected, arm) == result[name][str(bank)][cohort][arm]

    # Replay all frozen forward regular answers through the real serving class.
    cache = BoundEvidenceCache(IDENTITY)
    forward = [e for e in examples if e['cohort'] == 'forward36']
    for e in forward:
        if e['features'] is not None:
            raw = read(SOURCE / f"extraction/cases/{e['case']}.json")
            meaning = read(SOURCE / f"interpretations/{e['case']}.json")['interpretation']
            cache.add(e['instruction'], e['evidence'], e['program'], raw['observation']['observation'], meaning)
    runtime = 0
    labels = ('no', 'partial', 'yes')
    for bank, gate in gates.items():
        for e in forward:
            for regular in (-1, 0, 1, 2):
                calls = FlatStub(labels[regular] if regular >= 0 else 'unresolved')
                kwargs = {'extractor': FailedEvidence()} if e['features'] is None else {}
                judge = VerifiedSemanticJudge(calls, gate, evidence_cache=cache, identity=IDENTITY, **kwargs)
                actual = judge.judge(e['instruction'], e['evidence'], case_id=e['case'])
                selection = gate.resolve(e['program'], e['features'], regular) if e['features'] is not None else {'covered': False}
                prediction = selection['prediction'] if selection['covered'] else regular
                assert actual['judgment']['label'] == (labels[prediction] if prediction >= 0 else 'unresolved')
                assert len(calls.requests) == 1
                runtime += 1

    # The leaf is not disposable: its two fitting examples are Partial, and
    # several locally correct inputs outside that original batch also use it.
    e = by_case['N102']
    base, _, _ = prepared(2, parent_path(2))
    selection = measure(base, e)
    match = selection['matches'][0]
    source = ROOT / 'logs/exps/261019-pairwise-merge-v24-r1/split2/development.json'
    model = next(m for m in read(source)['models'] if m['runtime']['artifact_ref'] == match['expert_ref'])
    node = model['policy']['tree']
    for c in match['trace']:
        assert node['feature'] == c['feature']
        node = node['true' if c['value'] else 'false']
    assert node['prediction'] == 1 and node['support'] == 2 and node['source_batches'] == {'G3': 2}
    raw_votes = {ref: executor.predict_records([e['features']])[0] for ref, executor in risk.aware.utility.warrant.experts(base.base).items()}
    local_rows, _, _, _, _, _ = context(2)
    matches = [r for r in local_rows if all(r['features']['features'][c['feature']] == c['value'] for c in match['trace'])]
    save_json(out / 'bank2_harmful_leaf_provenance.json', {'source': str(source), 'sha256': fingerprint(source),
              'expert_ref': match['expert_ref'], 'rule_ref': match['rule_ref'], 'path': match['trace'], 'leaf': node,
              'raw_expert_votes': raw_votes,
              'all_local_matches': [{'case': r['case'], 'reference': r['reference'], 'instruction': r['instruction']} for r in matches],
              'review_note': 'Target car is removed; bus markings and details also change. The evidence reports collateral damage, while the human reference and regular judge allow Yes. Materiality/rubric disagreement, not an invented disappearance.',
              'images': e['evidence'], 'image_hashes': e['image_hashes']})
    report = {'passed': True, 'source_bank_folds_refitted': len(folds), 'held_predictions_replayed': held_count,
              'local_routes_retained': local, 'previous_correct_routes_retained': old_retained,
              'prior_correct_judge_label_variants_retained': label_variants, 'wrapper_scenarios': runtime, 'metric_tables_recounted': 18, 'new_model_calls': 0,
              'forward_set_is_now_development_data': True}
    save_json(out / 'verification.json', report)
    save_json(out / 'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'completion_seal.json'},
              'auditor_sha256': fingerprint(__file__)})
    print(report, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.output_dir.resolve())
