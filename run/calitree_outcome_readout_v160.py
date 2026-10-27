"""Reuse audited fitting-only observations to test an outcome-primary rubric."""
import argparse
from pathlib import Path
import shutil

from critical.core.decision import outcome_policy_v160 as outcome
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_facet_probe_v150 import ROOT, read
from run.verify_calitree_facet_probe_v151 import classification_metrics


def scalar(v):
    if v['new_requested_content'] == 'none':
        return None if v['all_material_facets'] == 'yes' else 0
    if v['new_requested_content'] == 'some':
        if v['all_material_facets'] == 'no':
            return 1
        if v['all_material_facets'] == 'yes' and v['scope_coverage'] in ('full', 'not_applicable'):
            return 2
    return None


def run(out):
    if out.exists():
        raise ValueError('Fresh outcome-policy readout required')
    paid = ROOT/'logs/exps/261025-paid-facet-probe-v155-r1'
    paid_audit = ROOT/'logs/exps/261025-paid-facet-audit-v158-r3'
    local = ROOT/'logs/exps/261025-explicit-facet-probe-v153-r1'
    local_audit = ROOT/'logs/exps/261025-explicit-facet-audit-v154-r1'
    assert read(paid_audit/'verification.json')['passed'] and read(paid_audit/'verification.json')['complete']
    assert read(local_audit/'verification.json')['passed'] and read(local_audit/'verification.json')['complete']
    references = read(paid/'references_training_only.json'); assert references == read(local/'references.json')
    protocol = {'version': outcome.VERSION, 'contract_ref': outcome.CONTRACT_REF, 'rubric': outcome.RUBRIC,
        'adaptation': 'Policy reconstruction after inspecting protected fitting errors of the strict v150 readout. Not a preregistered result, not source-held pipeline accuracy, and not a retrospective pass of v153/v155 strict admission.',
        'hypothesis': 'Human full-fulfillment examples can have complete requested outcomes despite unrequested source changes. Test outcome completion independently of universal preservation/operation caps.',
        'cases': 24, 'readouts': ['explicit_fields_first', 'explicit_evidence_first', 'luna', 'sol'],
        'failures': 'All24 remain counted. The two authenticated-failure slots are retained; unresolved records are not repaired.',
        'new_policy_collection_screen': {'accepted_min': 23, 'correct_min': 18, 'each_grade_correct_min': 5},
        'new_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    rows = []; accepted = {}
    for case, ref in references.items():
        row = {'case': case, 'reference': ref}
        for arm in protocol['readouts']:
            source = paid if arm in ('luna', 'sol') else local
            r = read(source/'responses'/(case+'-'+arm+'.json'))
            prediction = None
            if r['accepted']:
                accepted[arm] = accepted.get(arm, 0)+1
                prediction = outcome.decide(r['value']); assert prediction == scalar(r['value'])
            row[arm] = prediction if prediction is not None else -1
        rows.append(row)
    metrics = {arm: classification_metrics(rows, arm) for arm in protocol['readouts']}
    rule = protocol['new_policy_collection_screen']
    admission = {arm: accepted.get(arm, 0) >= rule['accepted_min'] and metrics[arm]['correct'] >= rule['correct_min'] and
        min(v['correct'] for v in metrics[arm]['per_class'].values()) >= rule['each_grade_correct_min'] for arm in metrics}
    report = {'metrics': metrics, 'accepted': accepted, 'adapted_collection_screen': admission,
        'scope': protocol['adaptation'], 'new_calls': 0, 'serving_changed': False,
        'original99_pipeline_retention': 'Selected V112 remains unchanged; the new raw tree has not yet been verified on all99 or the276 source-held cases.'}
    save_json(out/'results.json', report); save_json(out/'predictions.json', rows)
    files = [Path(__file__), ROOT/'critical/core/decision/outcome_policy_v160.py']
    for path in files:
        dest = out/'source_snapshot'/path.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': {str(p): file_hash(p) for p in files},
        'paid_audit_manifest_sha256': file_hash(paid_audit/'manifest.json'),
        'local_audit_manifest_sha256': file_hash(local_audit/'manifest.json')})
    (out/'run.log').write_text('Adapted outcome-primary rubric evaluated on cached fitting-only observations, all planned cases counted.\n')
    (out/'llm-histories.log').write_text('No new neural/API calls; native observations reused without repair.\n')
    print({'correct': {a: m['correct'] for a, m in metrics.items()}, 'adapted_collection_screen': admission}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
