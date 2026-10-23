"""Verify the serving default against the predeclared verification-only arm.

Reuses the frozen v35 policies; no refitting or real model calls. All banks and
all regular labels are replayed. Protected local and prior routes are checked.
"""
import argparse
from collections import Counter
from pathlib import Path

from critical.core.decision.artifacts import save_json
from critical.core.optimization.prompt.calitree.bound_evidence_cache import BoundEvidenceCache
from critical.core.optimization.prompt.calitree.evidence_covered_judge import BoundEvidencePipeline
from critical.core.optimization.prompt.calitree.verified_semantic_judge import VerifiedSemanticJudge
from critical.core.optimization.prompt.calitree.task_coverage import LABELS
from run.analyze_calitree_guarded_forward_v35 import policies, route, predict
from run.verify_calitree_regular_aware_runtime_v35 import FlatStub, FailedEvidence
from run.calitree_guarded_forward_v32 import SOURCE
from run.calitree_guarded_generalization_v32 import context
from run.calitree_fallback_routing_v34 import old_examples
from run.calitree_aurora_pilot_v29 import IDENTITY, read, fingerprint


def audit(forward, output):
    if output.exists():
        raise ValueError('Fresh audit directory required')
    gates = policies(forward)
    examples = read(forward / 'inputs.json')
    recorded = {r['case']: r for r in read(forward / 'supplemental_v35/full_predictions.json')}
    cache = BoundEvidenceCache(IDENTITY)
    for e in examples:
        if e['features'] is None:
            continue
        raw = read(SOURCE / f"extraction/cases/{e['case']}.json")
        meaning = read(SOURCE / f"interpretations/{e['case']}.json")['interpretation']
        cache.add(e['instruction'], e['evidence'], e['program'], raw['observation']['observation'], meaning)
    counts = Counter()
    records = []
    for bank, gate in gates.items():
        for e in examples:
            for regular in (-1, 0, 1, 2):
                calls = FlatStub(LABELS[regular] if regular >= 0 else 'unresolved')
                extractor = BoundEvidencePipeline(calls) if e['features'] is not None else FailedEvidence()
                judge = VerifiedSemanticJudge(calls, gate, evidence_cache=cache, identity=IDENTITY, extractor=extractor)
                result = judge.judge(e['instruction'], e['evidence'], case_id=e['case'])
                expected = route(gate, e, regular, corrections=False)
                prediction = predict(expected, regular)
                assert result['judgment']['label'] == (LABELS[prediction] if prediction >= 0 else 'unresolved')
                assert result['route']['covered'] == expected['covered']
                if e['features'] is not None:
                    assert result['route'] == expected and result['evidence_source'] == 'content_cache'
                assert len(calls.requests) == 1
                assert result['regular_execution_ref'] == 'mock-flat'
                assert result['execution_ref'] == (None if expected['covered'] else 'mock-flat')
                if regular == recorded[e['case']]['regular']:
                    assert prediction == recorded[e['case']][f'regular_aware_split{bank}']
                    counts['actual_baseline_predictions_reproduced'] += 1
                counts['hypothetical_wrapper_scenarios'] += 1
                records.append({'bank': bank, 'case': e['case'], 'regular': regular, 'prediction': prediction})
        rows, programs, raw, _, _, _ = context(bank)
        old = old_examples(bank)
        by_case = {e['case']: e for e in old}
        for r in rows:
            e = by_case[r['case']]
            decision = gate.resolve(programs[r['source_group']], r['features'], e['regular'], corrections=False)
            assert decision['covered'] and decision['prediction'] == r['reference']
            counts['local_routes_retained'] += 1
        for e in old:
            before = raw.select(e['program'], e['features'])
            if before['covered']:
                decision = gate.resolve(e['program'], e['features'], e['regular'], corrections=False)
                assert decision['covered'] and decision['prediction'] == before['prediction'] == e['reference']
                counts['previous_correct_routes_retained'] += 1
    output.mkdir(parents=True)
    report = {'passed': True, 'counts': dict(counts), 'serving_default': 'predeclared_verification_only',
              'new_model_calls': 0, 'new_fitting': False, 'all_banks_reported': True,
              'selection_note': 'The default mode was chosen after this comparison; the underlying arm/models were frozen before collection.'}
    save_json(output / 'verification.json', report)
    save_json(output / 'predictions.json', records)
    (output / 'run.log').write_text('Default serving arm matches frozen verification-only predictions; local/previous routes retained.\n')
    (output / 'llm-histories.log').write_text('Zero real model calls. FlatStub used for all 432 scenarios.\n')
    paths = [Path(__file__).resolve(), Path(__file__).resolve().parents[1] / 'critical/core/optimization/prompt/calitree/verified_semantic_judge.py']
    save_json(output / 'completion_seal.json', {'files': {str(p.relative_to(output)): fingerprint(p) for p in sorted(output.iterdir()) if p.is_file()},
              'code_hashes': {str(p): fingerprint(p) for p in paths},
              'policy_freeze_sha256': fingerprint(forward / 'supplemental_v35/freeze.json')})
    print(report, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    audit(args.forward_dir.resolve(), args.output_dir.resolve())
