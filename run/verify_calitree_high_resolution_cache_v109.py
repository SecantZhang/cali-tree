"""Audit the separate v108 profile against the frozen original review cache."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_semantic_rubric_v70 import ROOT, read
from run.verify_calitree_local_review_cache_v98 import audit as cache_audit


def audit(previous, previous_audit, cache, out, require_complete=False):
    verified = read(previous_audit/'verification.json'); previous_manifest = read(previous_audit/'manifest.json')
    assert verified['passed'] and verified['complete'] and not verified['snapshot_only']
    assert file_hash(previous/'manifest.json') == previous_manifest['cache_manifest_sha256']
    for path, sha in previous_manifest['source_hashes'].items():
        assert file_hash(path) == sha
    old_manifest = read(previous/'manifest.json'); old_profile = read(previous/'identity.json'); old_jobs = read(previous/'jobs.json'); old_membership = read(previous/'memberships.json')
    assert digest(old_profile) == old_manifest['identity_ref'] and digest(old_jobs) == old_manifest['jobs_ref'] and digest(old_membership) == old_manifest['memberships_ref']
    expected = deepcopy(old_profile); expected.update(max_pixels_per_image=1024*32*32, max_new_tokens=512,
        prior_probe='New v108 high-resolution512-output profile; all v96 successes/failures retained unchanged. No response repair or retry.')
    jobs = read(cache/'jobs.json'); assert len(jobs) == len(old_jobs) == 224
    for before, after in zip(old_jobs, jobs):
        transformed = {k: v for k, v in before.items() if k != 'request_ref'}; transformed['identity_ref'] = digest(expected); transformed['request_ref'] = digest(transformed)
        assert transformed == after
    assert read(cache/'memberships.json') == old_membership
    assert read(cache/'protocol.json')['previous_manifest_sha256'] == file_hash(previous/'manifest.json')
    for response in (cache/'responses').glob('*.json'):
        assert 'cache_origin' not in read(response), 'Different image/decode profiles cannot reuse responses'
    cache_audit(cache, out, require_complete, expected_profile=expected)
    dest = out/'source_snapshot/run'/Path(__file__).name; shutil.copyfile(__file__, dest)
    verification = read(out/'verification.json'); verification.update(profile='v108_high_resolution', previous_cache_unchanged=True, profile_changes=['max_pixels_per_image', 'max_new_tokens', 'prior_probe'])
    save_json(out/'verification.json', verification)
    manifest = read(out/'manifest.json'); manifest.update(wrapper_sha256=file_hash(__file__), previous_audit_manifest_sha256=file_hash(previous_audit/'manifest.json'))
    save_json(out/'manifest.json', manifest); print(verification, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--previous-cache', type=Path, required=True); p.add_argument('--previous-audit', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--require-complete', action='store_true')
    a=p.parse_args(); audit(a.previous_cache.resolve(), a.previous_audit.resolve(), a.cache.resolve(), a.output_dir.resolve(), a.require_complete)
