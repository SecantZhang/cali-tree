"""Rerun the same three fixed Luna samples with a constrained v3 compiler.

Fresh upstream records for every exact input, one bounded compiler repair on
validation failure, no transport/observation/interpretation retries. All learner
and merge gates/selection settings are imported unchanged from the prior study.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest
from critical.core.decision.calls import DurableCalls
from critical.core.decision.bound_compiler_v3 import BoundInstructionCompilerV3, VERSION as COMPILER_VERSION, TEMPLATE, schema_for, checked_program, diagnostic
from critical.core.decision.bound_evidence_v2 import BoundVisualObserver, image_identity, derive_record, diagnostic_readout
from critical.core.decision.semantic_interpretation_v5 import make_input
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.union_merges_v10 import LIMITS
from critical.core.calibration.semantic_hierarchy.union_learning_v10 import PROFILES
from critical.core.calibration.semantic_hierarchy.union_reuse_v11 import REPAIR
from run import calitree_three_splits as base
from run.calitree_bound_evidence_v2 import usage

ROOT, IDENTITY, CAPS = base.ROOT, base.IDENTITY, base.CAPS
SOURCE = ROOT / 'logs/exps/261018-three-sampled-splits-v11-luna-v2'
VERSION = 'three-splits-luna-compiler-v3-20261018'


def prepare(out):
    if (out / 'manifest.json').exists():
        manifest = base.prepare(out)
        assert manifest['compiler_revision'] == COMPILER_VERSION
        return manifest
    out.mkdir(parents=True, exist_ok=True)
    previous = base.read(SOURCE / 'manifest.json'); protocol = deepcopy(base.read(SOURCE / 'protocol.json'))
    old_seal = base.read(SOURCE / 'completion_seal.json')
    for name, sha in old_seal['files'].items():
        assert base.fingerprint(SOURCE / name) == sha
    assert protocol['profiles'] == PROFILES and protocol['limits'] == LIMITS and protocol['repair'] == REPAIR
    for name, ref in previous['splits'].items():
        split = base.read(SOURCE / 'splits' / (name + '.json'))
        assert digest(split) == ref
        base.exact(out / 'splits' / (name + '.json'), split)
    protocol.update(experiment_revision=VERSION, compiler_revision=COMPILER_VERSION,
        source_sample_run=str(SOURCE.relative_to(ROOT)), collection_reuse_from=None,
        compiler_contract='Dynamic full-instruction quote enums; bounded lowercase IDs; role-specific polarity; self-contained questions and empty dependencies. Original v2 validator/binding and feature contract unchanged.',
        compiler_repair='At most one text-only repair after compiler validation failure. Payload is instruction, original draft and error only; no images, reference labels or fitted policy feedback.',
        new_evidence='One fresh compiler/observer/meaning pass on every one of the same 135 exact inputs. No previous successful/failed record is silently substituted. A compiler validation failure permits the single declared repair; other stages have one attempt.',
        failure_policy='Reject invalid repaired programs. Preserve failures/unresolved sources in denominators, no resampling and no gate relaxation.',
        max_new_calls=4 * len(previous['cases']),
        max_completion_tokens=len(previous['cases']) * (2 * CAPS['compile'] + CAPS['observe'] + base.INTERPRET_CAP),
        gate_changes=False, selection_changes=False)
    base.exact(out / 'protocol.json', protocol)
    manifest = deepcopy(previous)
    manifest.update(protocol_ref=digest(protocol), compiler_revision=COMPILER_VERSION,
                    max_calls=3 * len(previous['cases']))
    # Old input evidence and splits remain pinned, while new executable sources
    # and compiler prompt are snapshotted before any new response is observed.
    files = [ROOT / rel for rel in previous['code_hashes']]
    files += [Path(__file__).resolve(), ROOT / 'critical/core/decision/bound_compiler_v3.py', TEMPLATE,
              ROOT / 'run/verify_calitree_three_splits.py']
    manifest['code_hashes'] = {str(p.relative_to(ROOT)): base.fingerprint(p) for p in dict.fromkeys(files)}
    manifest['source_hashes'].update({str((SOURCE / name).relative_to(ROOT)): base.fingerprint(SOURCE / name)
        for name in ('manifest.json', 'completion_seal.json', 'protocol.json', 'results.json')})
    for rel in manifest['code_hashes']:
        target = out / 'source_snapshot' / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    base.exact(out / 'manifest.json', manifest); base.exact(out / 'seal.json', {'manifest_ref': digest(manifest)})
    estimate = deepcopy(base.read(SOURCE / 'estimate.json'))
    estimate.update(max_new_calls=protocol['max_new_calls'], max_completion_tokens=protocol['max_completion_tokens'],
        new_compile_calls_max=2 * len(previous['cases']), new_image_calls_max=len(previous['cases']),
        new_interpretation_calls_max=len(previous['cases']), compiler_revision=COMPILER_VERSION, reused_model_calls=0)
    base.exact(out / 'estimate.json', estimate)
    base.exact(out / 'same_split_verification.json', {'all_180_slots_identical': True,
        'split_refs': previous['splits'], 'same_reference_labels': True, 'same_images_and_instructions': True,
        'merge_limits_ref': digest(LIMITS), 'fit_profiles_ref': digest(PROFILES), 'reuse_refinement_ref': digest(REPAIR),
        'gate_changes': False, 'original_run': str(SOURCE.relative_to(ROOT))})
    shutil.copyfile(SOURCE / 'model_change.json', out / 'model_change.json')
    base.verify(out, manifest); return manifest


def collect_physical(out, manifest, live):
    def work(case):
        target = out / 'extraction/cases' / (case['case'] + '.json')
        if target.exists():
            return base.read(target)
        row = {'case': case['case'], 'compilation': None, 'observation': None, 'record': None,
            'error': None, 'diagnostic': {'prediction': -1, 'label': 'Unresolved', 'reason': 'missing_evidence'}}
        for stage in ('compile', 'observe'):
            directory = out / 'extraction/ledgers' / case['case'] / stage
            count = 2 if stage == 'compile' else 1
            calls = DurableCalls(directory, base.model_factory(directory, live), identity=IDENTITY,
                max_calls=count, max_completion_tokens=count * CAPS[stage], scope_limits={'search': count, 'final': 0})
            try:
                if stage == 'compile':
                    row['compilation'] = BoundInstructionCompilerV3(calls).compile(case['instruction'], case_id=case['id'], max_tokens=CAPS[stage])
                else:
                    program = row['compilation']['program']
                    row['observation'] = BoundVisualObserver(calls).observe(program, case['evidence'], case_id=case['id'], max_tokens=CAPS[stage])
                    row['record'] = derive_record(program, row['observation']['observation'], image_identity(case['evidence'])[1])
                    row['diagnostic'] = diagnostic_readout(row['record'])
            except (RuntimeError, ValueError, KeyError, TypeError) as error:
                row['error'] = {'stage': stage, 'code': getattr(error, 'code', type(error).__name__), 'message': str(error)}
                break
        base.exact(target, row)
        print({'case': case['case'], 'compiled': row['compilation'] is not None, 'observed': row['record'] is not None,
            'compiler_repair_used': bool((row['compilation'] or {}).get('repair_execution_ref')),
            'error': row['error']}, flush=True)
        return row
    # Probe the provider before dispatch. A completed response that fails local
    # compilation is retained and does not count as a provider outage.
    if live:
        first = work(manifest['cases'][0])
        jobs = [base.read(p) for p in (out / 'extraction/ledgers' / first['case'] / 'compile/jobs').glob('*.json')]
        if not jobs or all(j['outcome'] != 'completed' for j in jobs):
            raise RuntimeError('Provider probe failed; batch not dispatched. Inspect retained first slot.')
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        rows = list(pool.map(work, manifest['cases']))
    base.exact(out / 'extraction/observations.json', rows)
    return rows


def audit_compiler(out, manifest, observations):
    checked = repairs = 0
    for case, row in zip(manifest['cases'], observations):
        directory = out / 'extraction/ledgers' / case['case'] / 'compile'
        jobs = {j['stage']: j for j in (base.read(p) for p in (directory / 'jobs').glob('*.json'))}
        assert set(jobs) <= {'bound_instruction_v3', 'bound_instruction_v3_repair'}
        initial = jobs['bound_instruction_v3']
        assert initial['payload'] == {'instruction': case['instruction'], 'max_checks': 16}
        assert initial['media_identity'] == []
        if 'bound_instruction_v3_repair' in jobs:
            repaired = jobs['bound_instruction_v3_repair']; repairs += 1
            assert initial['outcome'] == 'completed'
            try:
                checked_program(case['instruction'], initial['parsed'])
            except Exception as error:
                expected_error = diagnostic(error)
            else:
                raise AssertionError('A valid compiler draft was unnecessarily repaired')
            assert repaired['payload'] == {'instruction': case['instruction'], 'max_checks': 16,
                'draft': initial['parsed'], 'validation_error': expected_error}
            assert repaired['media_identity'] == []
        if row['compilation']:
            accepted = next(j for j in jobs.values() if j['execution_ref'] == row['compilation']['execution_ref'])
            assert checked_program(case['instruction'], accepted['parsed']) == row['compilation']['program']
        observer_jobs = [base.read(p) for p in (out / 'extraction/ledgers' / case['case'] / 'observe/jobs').glob('*.json')]
        assert len(observer_jobs) == (1 if row['compilation'] else 0)
        if observer_jobs:
            job = observer_jobs[0]; pair = image_identity(case['evidence'])[1]
            assert job['payload'] == {'program': row['compilation']['program'], 'image_pair_ref': pair}
            assert job['media_identity'] == [{'type': 'text', 'text': 'SOURCE image'},
                {'type': 'image', 'sha256': case['image_hashes']['source_image']}, {'type': 'text', 'text': 'EDITED image'},
                {'type': 'image', 'sha256': case['image_hashes']['edited_image']}]
        checked += len(jobs) + len(observer_jobs)
    return {'passed': True, 'checked_payloads': checked, 'compiler_repairs': repairs,
        'reference_labels_or_policy_feedback_in_payload': False, 'observer_retries': 0, 'reserved_test_calls': 0}


def collect_all(out, manifest, live):
    observations = base.read(out / 'extraction/observations.json') if (out / 'extraction/observations.json').exists() else collect_physical(out, manifest, live)
    audited = audit_compiler(out, manifest, observations)
    by_case = {r['case']: r for r in observations}
    with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
        meanings = list(pool.map(lambda case: base.interpret_one(out, case, by_case[case['case']], live), manifest['cases']))
    base.exact(out / 'interpretations.json', meanings); by_meaning = {r['case']: r for r in meanings}
    records = {}
    for case in manifest['cases']:
        obs = by_case[case['case']]
        feature = project(obs['compilation']['program'], obs['observation']['observation'], image_identity(case['evidence'])[1],
                          by_meaning[case['case']]['interpretation']) if obs['record'] else None
        records[case['case']] = {'case': case['case'], 'source_group': case['group'], 'instruction': case['instruction'],
            'reference': base.LABELS.index(case['reference']), 'features': feature}
    base.exact(out / 'portable_records.json', records)
    physical_usage = usage(out / 'extraction')
    jobs = [base.read(p) for p in out.glob('interpretation_ledgers/*/jobs/*.json')]
    for case in manifest['cases']:
        obs = by_case[case['case']]; found = [j for j in jobs if j['case_id'] == case['case']]
        if obs['record']:
            assert len(found) == 1 and found[0]['payload'] == make_input(obs['compilation']['program'], obs['observation']['observation'], image_identity(case['evidence'])[1])
        else:
            assert not found
    summary = {'physical': physical_usage, 'physical_payload_audit': audited,
        'semantic': {'attempts': len(jobs), 'valid': sum(r['interpretation'] is not None for r in meanings),
            'input_tokens': sum((j.get('response') or {}).get('promptTokens', 0) or 0 for j in jobs),
            'completion_tokens': sum((j.get('response') or {}).get('completionTokens', 0) or 0 for j in jobs)},
        'unique_inputs': len(records), 'unique_sources': manifest['unique_sources'],
        'missing_portable_records': sum(r['features'] is None for r in records.values()),
        'unresolved_records': sum(r['features'] is None or not r['features']['features']['meaning_available'] for r in records.values()),
        'attempts': sum(v['attempts'] for v in physical_usage.values()) + len(jobs),
        'max_calls': 4 * len(records), 'reference_labels_in_payload': False, 'reserved_test_calls': 0}
    assert summary['attempts'] <= summary['max_calls']
    base.exact(out / 'collection_results.json', summary); base.verify(out, manifest)
    print({'collection_complete': True, 'attempts': summary['attempts'], 'compiler_repairs': audited['compiler_repairs'],
        'valid_physical': sum(bool(r['record']) for r in observations), 'unresolved': summary['unresolved_records']}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('preflight', 'collect', 'train', 'summary', 'all'), default='preflight')
    parser.add_argument('--live', action='store_true'); parser.add_argument('--replay', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve(); manifest = prepare(out)
    if args.mode == 'preflight':
        print(base.read(out / 'estimate.json')); return
    if args.mode in ('collect', 'all'):
        if not (args.live or args.replay):
            parser.error('Collection requires --live or --replay')
        collect_all(out, manifest, args.live)
    if args.mode in ('train', 'all'):
        for name in ('split1', 'split2', 'split3'):
            base.fit_one(out, name, args.replay)
    if args.mode in ('summary', 'all'):
        base.summarize(out)


if __name__ == '__main__':
    main()
