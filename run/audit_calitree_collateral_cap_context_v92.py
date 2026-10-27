"""Counterfactually remove one grading cap without changing observed evidence."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.calibration import rubric_evidence_v73 as rubric
from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_rubric_v70 import ROOT, FROZEN, read, fingerprint


def audit(out):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    out.mkdir(parents=True)
    protocol = {'type': 'counterfactual grading-condition diagnostic',
                'rule': 'Ignore only material_unrequested_change in the Yes cap; retain same-requirement outcome/endpoint/identity/coherence constraints and collateral uncertainty.',
                'method': 'Compute strict readiness from the original evidence. In an explicitly hypothetical deep copy only, map material collateral to none, then evaluate the same logical warrant. Do not save or use the hypothetical as observed evidence.',
                'fitting': False, 'new_api_calls': 0, 'new_pilot_responses_used': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Read-only material-collateral cap diagnostic started.\n')
    (out/'llm-histories.log').write_text('Zero calls, fitting, uploads or new v75 response reads. All counterfactuals concern a grading condition, not new observed facts.\n')
    references = {r['case']: r for r in read(FROZEN/'fitting_replay.json')}; rows = []; counts = Counter()
    inputs = read(FROZEN/'replay_inputs_without_references.json'); original_ref = digest(inputs)
    for i, r in enumerate(inputs):
        if r['observation'] is None or r['interpretation'] is None:
            continue
        pair = r['observation']['image_pair_ref']
        strict = rubric.project(r['program'], r['observation'], pair, r['interpretation'])
        hypothetical = deepcopy(r['interpretation'])
        for row in hypothetical['requirements'].values():
            if row['collateral_materiality'] == 'material_unrequested_change':
                row['collateral_materiality'] = 'none'
        relaxed = rubric.project(r['program'], r['observation'], pair, hypothetical)
        if relaxed['rubric_yes_ready'] and not strict['rubric_yes_ready']:
            cohort = 'original' if i < 99 else 'primary' if i < 375 else 'matched'
            reference = references[r['case']]['reference']; counts[cohort, reference] += 1
            rows.append({'case': r['case'], 'cohort': cohort, 'reference': reference,
                         'original_interpretation_ref': digest(r['interpretation']),
                         'strict_yes_warrant': False, 'counterfactual_yes_warrant': True})
    assert digest(inputs) == original_ref
    result = {'changed_warrant_cases': len(rows), 'by_cohort': {c: {label: counts[c, k] for k, label in enumerate(('no', 'partial', 'yes'))} for c in ('original', 'primary', 'matched')},
              'not_an_accuracy_result': True, 'rule_not_promoted': True, 'original_evidence_unchanged': True}
    save_json(out/'rows.json', rows); save_json(out/'results.json', result)
    source_hashes = {str(FROZEN/n): fingerprint(FROZEN/n) for n in ('replay_inputs_without_references.json', 'fitting_replay.json')}
    code_hashes = {str(p): fingerprint(p) for p in (Path(__file__), Path(rubric.__file__))}
    for p in (Path(__file__), Path(rubric.__file__)):
        destination = out/'source_snapshot'/p.relative_to(ROOT); destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, destination)
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'source_sha256': source_hashes, 'code_sha256': code_hashes})
    (out/'run.log').write_text('Completed counterfactual warrant audit; original evidence unchanged. Global cap removal would admit four non-Yes originals. No policy or inference change.\n')
    print(result, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    audit(p.parse_args().output_dir.resolve())
