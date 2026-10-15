"""M1: two-stage bound evidence on the twelve observed development cases only."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.bound_evidence import (
    VERSION as EVIDENCE_VERSION, TEMPLATES, COMPILER_SCHEMA, BoundInstructionCompiler,
    BoundVisualObserver, derive_record, diagnostic_readout, image_identity,
)
from critical.core.decision.calls import DurableCalls
from critical.core.calibration.evidence_rules_v4 import classification_metrics
from run.calitree_single_call import ROOT, IDENTITY, fingerprint, read

VERSION = 'm1-bound-evidence-development12-v1'
M0 = ROOT / 'logs/exps/261014-semantic-hierarchy-m0-fifty-v1'
LEGACY = ROOT / 'logs/exps/261014-frozen-semantic-transfer12-v1'
CAPS = {'compile': 8192, 'observe': 16384}
LABELS = ('no', 'partial', 'yes')


def allowed_cases():
    cases = read(M0 / 'splits/validation.json')['cases']
    forbidden = {c['group'] for c in read(M0 / 'splits/test.json')['cases']}
    if len(cases) != 12 or len({c['group'] for c in cases}) != 12 or {c['group'] for c in cases} & forbidden:
        raise ValueError('M1 must use only the fixed development cohort')
    if Counter(c['reference'] for c in cases) != dict.fromkeys(LABELS, 4):
        raise ValueError('Changed development labels')
    return cases


def inference_input(case):
    return {'instruction': case['instruction'], 'evidence': dict(case['evidence'])}


def exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Changed saved artifact: ' + str(path))
    else:
        save_json(path, value)


def fixed_feature_readout(f):
    """The same diagnostic label policy for old/new role-feature projections."""
    def bound(upper):
        def desired(key, positive=True):
            v = f[key]
            if v == 'not_applicable':
                return not positive
            if v == 'unknown':
                return upper
            return (v == 'true') if positive else (v == 'false')
        complete = desired('all_requirements_satisfied')
        preserved = desired('collateral_disappearance', False) and desired('collateral_deformation', False)
        positive = desired('any_required_witness') or desired('linked_intermediate_witness')
        return 2 if complete and preserved else 1 if positive else 0
    low, high = bound(False), bound(True)
    return low if low == high else -1


def legacy_features(f):
    mapping = {'all_requirements_satisfied': 'all_bound_postconditions_established',
               'any_required_witness': 'a_required_positive_witness_visible',
               'linked_intermediate_witness': 'instruction_related_intermediate_witness',
               'collateral_disappearance': 'unrequested_disappearance_observed',
               'collateral_deformation': 'unrequested_deformation_observed'}
    return {k: f[v] for k, v in mapping.items()}


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    cases = allowed_cases()
    files = [Path(__file__).resolve(), ROOT / 'critical/core/decision/bound_evidence.py',
             ROOT / 'critical/core/decision/calls.py', ROOT / 'critical/core/decision/compiler.py',
             ROOT / 'critical/core/decision/artifacts.py', ROOT / 'run/calitree_single_call.py',
             TEMPLATES / 'compile.txt', TEMPLATES / 'observe.txt']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); code[rel] = fingerprint(p)
    pinned = [M0 / 'seal.json', M0 / 'completion_seal.json', M0 / 'splits/validation.json',
              M0 / 'splits/test.json', LEGACY / 'observations.json', LEGACY / 'results.json']
    m = {'version': VERSION, 'evidence_version': EVIDENCE_VERSION, 'cases': cases,
         'judge_identity': IDENTITY, 'workers': 8, 'caps': CAPS, 'max_calls': 24,
         'image_presentations_per_case': 1, 'attempts_per_stage': 1, 'presentation': 'source_first',
         'reserved_test_evaluated': False, 'code_hashes': code,
         'pinned_files': {str(p): fingerprint(p) for p in pinned},
         'compiler_schema_ref': digest(COMPILER_SCHEMA),
         'scope': 'M1 development representation audit, not fitted calibration or held-out transfer. Two-stage refactor evaluated separately from merging.',
         'required_failure_families': {'body_pose': ['H02'], 'collateral_disappearance': ['H05'],
                                      'compound_action': ['H08'], 'style_progress': ['H04', 'H10'],
                                      'collateral_deformation': ['H11']},
         'diagnostics': 'Compare old/new role features under the same fixed uncalibrated readout. Dataset labels score diagnostics only; image audit is assistant review, not human fact annotations.',
         'completion': 'Versioned schemas/prompts, hash and pair rejection, uncertainty/absence safeguards, physical regression fixtures, live development records, visual audit with disputes, exact replay, and preserved final reservation.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'max_calls': 24, 'instruction_only_calls': 12, 'image_calls': 12,
              'max_completion_tokens': 12 * sum(CAPS.values()), 'reserved_test_calls': 0,
              'm0_development_extraction_ceiling': 120, 'this_version_slots': 24})
    # Check that the exact payload images are public release assets. Do not send
    # local labels, old model answers, or any reserved-final images to the API.
    release = read(ROOT / 'data/aurora/bench/manifest.json')
    checked = []
    for c in cases:
        for role, path in c['evidence'].items():
            rel = str(Path(path).relative_to(ROOT / 'data/aurora/bench'))
            if fingerprint(path) != release['files'][rel]['sha256']:
                raise ValueError('Development asset differs from public release')
            checked.append({'case': c['case'], 'role': role, 'release_path': rel, 'sha256': fingerprint(path)})
    save_json(output / 'public_data_provenance.json', {'repository': 'https://github.com/McGill-NLP/AURORA#human-ratings',
              'images_google_drive_id': release['images_google_drive_id'], 'images': checked,
              'destination': 'https://api.openai.com/v1', 'payload': 'Public instructions and image pairs plus compiled physical questions; no reference labels, previous outputs, or final-test cases.'})
    verify(output, m); return m


def verify(output, m):
    if (m['version'] != VERSION or m['evidence_version'] != EVIDENCE_VERSION or m['judge_identity'] != IDENTITY
            or m['caps'] != CAPS or m['cases'] != allowed_cases() or digest(m) != read(output / 'seal.json')['manifest_ref']
            or m['compiler_schema_ref'] != digest(COMPILER_SCHEMA)):
        raise ValueError('Changed M1 protocol')
    for path, ref in m['pinned_files'].items():
        if fingerprint(path) != ref:
            raise ValueError('Pinned source changed: ' + path)
    for rel, ref in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != ref or fingerprint(output / 'source_snapshot' / rel) != ref:
            raise ValueError('Frozen M1 implementation changed: ' + rel)
    for c in m['cases']:
        for k, p in c['evidence'].items():
            if fingerprint(p) != c['image_hashes'][k]:
                raise ValueError('Image changed')
    if (M0 / 'predictions.json').exists() or list(M0.glob('ledgers/**/jobs/*.json')):
        raise ValueError('The M0 final reservation has been evaluated')


def collect(output, m, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'; creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI endpoint only')
    def work(c):
        x = inference_input(c)
        row = {'case': c['case'], 'compilation': None, 'observation': None, 'record': None, 'error': None,
               'diagnostic': {'prediction': -1, 'label': 'Unresolved', 'reason': 'missing_evidence'}}
        for stage in ('compile', 'observe'):
            directory = output / 'ledgers' / c['case'] / stage
            if not live and not list((directory / 'jobs').glob('*.json')):
                raise ValueError('Missing replay slot ' + str(directory))
            def factory(cap):
                if not live:
                    raise AssertionError('Replay attempted an API call')
                return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort=IDENTITY['reasoning_effort'],
                                  temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                                  history=LLMHistoryWriter(directory / 'llm-histories.log'))
            calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                                 max_completion_tokens=CAPS[stage], scope_limits={'search': 1, 'final': 1})
            try:
                if stage == 'compile':
                    row['compilation'] = BoundInstructionCompiler(calls).compile(x['instruction'], case_id=c['id'], max_tokens=CAPS[stage])
                else:
                    p = row['compilation']['program']
                    row['observation'] = BoundVisualObserver(calls).observe(p, x['evidence'], case_id=c['id'], max_tokens=CAPS[stage])
                    v = row['observation']['observation']; pair_ref = image_identity(x['evidence'])[1]
                    row['record'] = derive_record(p, v, pair_ref); row['diagnostic'] = diagnostic_readout(row['record'])
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                row['error'] = {'stage': stage, 'code': getattr(exc, 'code', type(exc).__name__), 'message': str(exc)}
                jobs = list((directory / 'jobs').glob('*.json'))
                if jobs and (job := read(jobs[0]))['outcome'] != 'completed':
                    row['error'] = {'stage': stage, 'code': job['outcome'], 'message': job.get('error') or job['outcome']}
                break
        exact(output / 'cases' / (c['case'] + '.json'), row)
        print({'case': c['case'], 'compiled': row['compilation'] is not None, 'observed': row['observation'] is not None,
               'diagnostic': row['diagnostic']['label'], 'error': row['error']}, flush=True)
        return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool:
        return list(pool.map(work, m['cases']))


def audit_payloads(output, m, rows):
    checked = 0
    for c, row in zip(m['cases'], rows):
        for stage in ('compile', 'observe'):
            paths = list((output / 'ledgers' / c['case'] / stage / 'jobs').glob('*.json'))
            if not paths:
                if stage == 'observe' and row['compilation'] is None:
                    continue
                raise AssertionError('Missing accounted stage')
            if len(paths) != 1:
                raise AssertionError('Repeated stage')
            job = read(paths[0]); checked += 1
            if stage == 'compile':
                if job['payload'] != {'instruction': c['instruction'], 'max_checks': 16} or job['media_identity']:
                    raise AssertionError('Instruction compiler received unexpected inputs')
            else:
                pair = image_identity(c['evidence'])[1]
                if job['payload'] != {'program': row['compilation']['program'], 'image_pair_ref': pair}:
                    raise AssertionError('Observer did not receive the exact bound program')
                expected = [{'type': 'text', 'text': 'SOURCE image'}, {'type': 'image', 'sha256': c['image_hashes']['source_image']},
                            {'type': 'text', 'text': 'EDITED image'}, {'type': 'image', 'sha256': c['image_hashes']['edited_image']}]
                if job['media_identity'] != expected:
                    raise AssertionError('Changed ordered image pair')
                if row['observation'] is not None and job['parsed'] != row['observation']['observation']:
                    raise AssertionError('Raw and saved observations disagree')
    return {'passed': True, 'checked_payloads': checked, 'reserved_test_calls': 0,
            'reference_labels_or_old_outputs_in_payload': False, 'one_image_presentation_per_case': True}


def evaluate(m, rows):
    old = {r['case']: r for r in read(LEGACY / 'observations.json')}
    targets = [LABELS.index(c['reference']) for c in m['cases']]
    before = [fixed_feature_readout(legacy_features(old[c['case']]['record']['facts'])) for c in m['cases']]
    after = [fixed_feature_readout(r['record']['features']) if r['record'] else -1 for r in rows]
    exact_bound = [r['diagnostic']['prediction'] for r in rows]
    return {'legacy_common_readout': classification_metrics(before, targets)[0],
            'bound_common_readout': classification_metrics(after, targets)[0],
            'bound_exact_diagnostic': classification_metrics(exact_bound, targets)[0],
            'cases': [{'case': c['case'], 'instruction': c['instruction'], 'reference': c['reference'],
                       'legacy_common_prediction': before[i], 'bound_common_prediction': after[i],
                       'bound_exact_prediction': exact_bound[i]} for i, c in enumerate(m['cases'])],
            'limitation': 'Same fixed readout on projected features; representation and observation generation changed. Neither arm is a newly optimized policy. Twelve development cases do not establish transfer.'}


def usage(output):
    result = {}
    for stage in CAPS:
        jobs = [read(p) for p in (output / 'ledgers').glob('*/' + stage + '/jobs/*.json')]
        responses = [j['response'] for j in jobs if j.get('response')]
        result[stage] = {'attempts': len(jobs), 'outcomes': dict(Counter(j['outcome'] for j in jobs)),
                         'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
                         'completion_tokens': sum(r.get('completionTokens', 0) for r in responses),
                         'returned_models': sorted({r.get('model', 'unknown') for r in responses})}
    return result


def report(output, result):
    e = result['evaluation']
    lines = ['# M1 bound-evidence development audit', '',
             'Two stages: instruction-only compilation, then one SOURCE-first visual observation of those exact checks. Same Sol/high profile. These twelve cases are development material; the fifty-case reservation is unevaluated.', '',
             'The label results below use a fixed, uncalibrated diagnostic policy. They are not M2 calibration accuracy or a final-test result.', '',
             '| Representation / readout | Correct /12 | No recall | Partial recall | Yes recall | Unresolved |',
             '|---|---:|---:|---:|---:|---:|']
    for k in ('legacy_common_readout', 'bound_common_readout', 'bound_exact_diagnostic'):
        r = e[k]; rates = ' | '.join(f"{r['per_class'][label]['recall']:.0%}" for label in LABELS)
        lines.append(f"| {k} | {r['correct']}/12 | {rates} | {r['unresolved']} |")
    lines += ['', e['limitation'], '', '## Raw execution', '',
              f"Valid compiled programs: {result['compiled']}/12. Valid observed records: {result['observed']}/12.",
              f"Whitelisted payloads audited: {result['audit']['checked_payloads']}. Reserved-test calls: zero.", '',
              '## Visual review', '', 'Image-level review and disputed interpretations are recorded separately in `visual_audit.json` and `visual_audit.md`. Model-produced states are not human annotations.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    modes = p.add_mutually_exclusive_group(required=True)
    for name in ('preflight', 'live', 'replay'):
        modes.add_argument('--' + name, action='store_true')
    a = p.parse_args(); output = a.output_dir.resolve(); m = prepare(output)
    if a.preflight:
        print(read(output / 'estimate.json')); return
    rows = collect(output, m, a.live); verify(output, m)
    exact(output / 'observations.json', rows)
    result = {'version': VERSION, 'model': IDENTITY, 'manifest_ref': digest(m), 'evaluation': evaluate(m, rows),
              'compiled': sum(r['compilation'] is not None for r in rows), 'observed': sum(r['record'] is not None for r in rows),
              'audit': audit_payloads(output, m, rows), 'usage': usage(output)}
    exact(output / 'results.json', result); exact(output / 'payload_audit.json', result['audit']); report(output, result)
    if a.replay:
        exact(output / 'replay.json', {'exact_replay': True, 'new_model_calls': 0, 'results_sha256': fingerprint(output / 'results.json')})
    else:
        (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/*/llm-histories.log'))))
    print({k: result[k] for k in ('compiled', 'observed', 'audit', 'usage')})
    print({k: v for k, v in result['evaluation'].items() if k != 'cases'})


if __name__ == '__main__':
    main()
