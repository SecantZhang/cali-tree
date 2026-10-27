"""Replay the selected default pipeline against the verified v112 cached outputs."""
import argparse
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from critical.config import CALITREE_SELECTION
from critical.core.optimization.prompt.calitree import CaliTreeJudge
from critical.core.calibration.independent_expert_v87 import record_from_job
from critical.core.calibration.local_warranted_rubric_v97 import LABELS
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.calitree_current import cached_predictions

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT/'logs/exps/261021-frozen-visual-policy-v69'
VISION = ROOT/'logs/exps/261021-paired-vision-v63'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

VERIFIED = ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2'
CACHE = ROOT/'logs/exps/261023-local-review-cache-v96-r1'
CACHE_AUDIT = ROOT/'logs/exps/261023-local-review-cache-v98-complete-r1'


def audit(out):
    if out.exists():
        raise ValueError('Fresh selected-pipeline replay directory required')
    def forbidden(*args, **kwargs):
        raise AssertionError('Selected cached replay cannot call a model or encoder')
    judge = CaliTreeJudge(encoder=SimpleNamespace(compute=forbidden))
    assert judge.selected_version == 'v112'
    assert judge.policy.artifact == read(VERIFIED/'policy.json')
    assert judge.policy.artifact['artifact_ref'] == read(VERIFIED/'manifest.json')['policy_ref']
    cache_proof = read(CACHE_AUDIT/'verification.json'); audited = read(CACHE_AUDIT/'manifest.json')
    assert cache_proof['passed'] and cache_proof['complete'] and not cache_proof['snapshot_only']
    assert audited['cache_manifest_sha256'] == file_hash(CACHE/'manifest.json')
    for path, sha in audited['source_hashes'].items():
        assert file_hash(path) == sha, path
    local_records = {job['case']: read(CACHE/'responses'/(job['case']+'.json'))['record'] for job in read(CACHE/'jobs.json')}
    old = {r['case']: r for r in read(VERIFIED/'runtime_predictions.json')}
    by_case = {r['case']: r for r in read(ROOT/'logs/exps/261023-cached-sol-router-v85-r3/expert_provenance.json')}
    hashes = read(VISION/'manifest.json')['image_hashes']
    out.mkdir(parents=True)
    (out/'run.log').write_text('Selected v112 default replay started; cached requests only.\n')
    (out/'llm-histories.log').write_text('Zero API, local-observer or encoder calls; explicit cached stages supplied.\n')
    inputs = read(FROZEN/'replay_inputs_without_references.json'); runtime = []
    for r in inputs:
        pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']],
                       hashes[r['evidence']['edited_image']]])
        expert = None
        if r['case'] in by_case:
            slot = by_case[r['case']]['selected_slot']; contract = judge.policy.base.artifact['expert_contract']
            assert file_hash(slot['job']) == slot['job_sha256']
            expert = record_from_job(r['program'], pair, slot['identity'], read(slot['job']),
                                     contract['schema'], contract['template'])
        measured = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
            'program_ref': r['program']['program_ref'], 'image_pair_ref': pair,
            'encoder_spec_ref': digest(judge.policy.artifact['encoder_spec']),
            'measurements': read(VISION/'cases'/(r['case']+'.json'))['measurements']}
        request = {'instruction': r['program']['instruction'], 'evidence': r['evidence'],
            'program': r['program'], 'observation': r['observation'], 'interpretation': r['interpretation'],
            'regular_judgment': r['judgment'], 'vision_record': measured,
            'expert_record': expert, 'local_record': local_records.get(r['case'])}
        result = cached_predictions([request], judge)[0]
        prediction = LABELS.index(result['judgment']['label']) if result['judgment']['label'] != 'unresolved' else -1
        item = {'case': r['case'], 'prediction': prediction, 'covered': result['route']['covered'], 'source': result['source']}
        assert item == old[r['case']], r['case']
        assert result['pipeline_version'] == 'v112' and result['policy_ref'] == judge.policy.artifact['artifact_ref']
        assert 'local_review_error' not in result['route']
        runtime.append(item)
    assert len(runtime) == len(old) == 915
    original = read(FROZEN/'fitting_replay.json')[:99]
    assert all(runtime[i]['case'] == r['case'] and runtime[i]['prediction'] == r['reference'] for i, r in enumerate(original))
    selected = read(CALITREE_SELECTION)
    report = {'passed': True, 'selected_version': judge.selected_version,
        'policy_ref': judge.policy.artifact['artifact_ref'], 'shared_terms': len(judge.policy.artifact['rubric']['clauses']),
        'bound_cached_requests_replayed': len(runtime), 'all_predictions_coverage_sources_unchanged': True,
        'original_cases_replayed_correct': 99, 'source_held_development_result': selected['evaluation'],
        'new_api_calls': 0, 'new_observer_calls': 0, 'new_encoder_calls': 0, 'refitting': False,
        'scope': 'Default selection and915-case inference-equivalence check; the276-case accuracy is the existing frozen source-held evaluation.'}
    save_json(out/'verification.json', report); save_json(out/'predictions.json', runtime)
    save_json(out/'selection.json', selected)
    sources = [Path(__file__), ROOT/'run/calitree_current.py', ROOT/'critical/config.py',
        ROOT/'critical/core/optimization/prompt/calitree/current.py',
        ROOT/'critical/core/optimization/prompt/calitree/__init__.py', CALITREE_SELECTION]
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources},
        'parent_v112_manifest_sha256': file_hash(VERIFIED/'manifest.json'),
        'local_cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json'),
        'selected_policy_ref': judge.policy.artifact['artifact_ref']})
    (out/'run.log').write_text('Selected v112 default reproduces all915 bound cached predictions, coverage and source routes;99 original cases correct. No fitting or model calls.\n')
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    audit(p.parse_args().output_dir.resolve())
