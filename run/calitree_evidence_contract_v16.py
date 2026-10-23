"""Paired training-only evidence-contract diagnostic; preflight by default.

Twelve sources, two fresh prompt arms, one observation and one interpretation per
arm/source. Existing compilers and references are frozen. No final-set access,
refitting, relabeling, resampling or automatic prompt promotion.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from critical.core.decision.artifacts import digest
from critical.core.decision import calls as call_module
from critical.core.decision.calls import DurableCalls
from critical.core.decision.bound_evidence_v2 import BoundVisualObserver, derive_record, image_identity, TEMPLATES
from critical.core.decision.semantic_interpretation_v5 import PROMPT, make_input, schema, validate
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from run import calitree_three_splits as base

ROOT = base.ROOT
TRAINED = ROOT / 'logs/exps/261018-supported-child-compression-v14'
EVIDENCE = ROOT / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
ADDITIONS = ROOT / 'critical/core/prompts/templates/evidence_contract_v16'
VERSION = 'paired-training-evidence-contract-v16'
FORCED = ('N045', 'N071', 'N122', 'N076', 'N085')
ARMS = ('original', 'clarified')


def prepare(out):
    base.validate_settings()
    pool = {}
    sources = []
    for i in (1, 2, 3):
        path = TRAINED / f'split{i}/training_data.json'; sources.append(path)
        for row in base.read(path):
            if row['case'] in pool:
                previous = pool[row['case']]
                if any(previous[k] != row[k] for k in ('source_group', 'instruction', 'reference', 'features')):
                    raise ValueError('Shared training case changed across cohorts')
            pool[row['case']] = row
    chosen = [pool[k] for k in FORCED]; used = {r['source_group'] for r in chosen}
    if len(used) != len(chosen):
        raise ValueError('Diagnostic anchors must have distinct sources')
    for label in (0, 1, 2):
        while sum(r['reference'] == label for r in chosen) < 4:
            candidates = [r for r in pool.values() if r['reference'] == label and r['source_group'] not in used]
            row = min(candidates, key=lambda r: digest([VERSION, r['case']]))
            chosen.append(row); used.add(row['source_group'])
    chosen.sort(key=lambda r: r['case'])
    if len(chosen) != 12 or Counter(r['reference'] for r in chosen) != {0: 4, 1: 4, 2: 4}:
        raise ValueError('Changed diagnostic cohort')
    original_manifest = base.read(EVIDENCE / 'manifest.json'); metadata = {r['case']: r for r in original_manifest['cases']}
    cases = []; programs = {}; references = {}
    for row in chosen:
        meta = metadata[row['case']]; path = EVIDENCE / 'extraction/cases' / (row['case'] + '.json'); sources.append(path)
        old = base.read(path)
        if not old['compilation']:
            raise ValueError('A frozen validated compiler is required')
        programs[row['case']] = old['compilation']['program']; references[row['case']] = row['reference']
        cases.append({'case': row['case'], 'source_group': row['source_group'], 'instruction': row['instruction'],
            'evidence': meta['evidence'], 'image_hashes': {k: base.fingerprint(p) for k, p in meta['evidence'].items()}})
    original_observer = (TEMPLATES / 'observe.txt').read_text()
    prompts = {'original': {'observe': original_observer, 'interpret': PROMPT},
        'clarified': {'observe': original_observer + '\n' + (ADDITIONS / 'observer_addendum.txt').read_text(),
                      'interpret': PROMPT + '\n' + (ADDITIONS / 'interpret_addendum.txt').read_text()}}
    protocol = {'version': VERSION, 'identity': base.IDENTITY, 'sources': 12, 'arms': list(ARMS),
        'selection': 'Five previously diagnosed training conflict sources plus stable-hash class-balanced completion to four/reference class. Failure-selected diagnostic, not generalization estimation.',
        'forced_training_cases': list(FORCED), 'new_calls_max': 48,
        'completion_tokens_max': 24 * (base.CAPS['observe'] + base.INTERPRET_CAP),
        'frozen_compiler': True, 'fresh_baseline': True, 'reference_labels_in_payloads': False,
        'final_set_access': False, 'fitting_or_relabeling': False, 'retries': 0, 'workers': 4,
        'outcome': 'Paired state/anchor/coverage/interpretation changes and retained failures. Manual evidence review needed; no automatic prompt promotion from a small, selected cohort.'}
    code = [Path(__file__).resolve(), Path(call_module.__file__).resolve(), ROOT / 'run/calitree_three_splits.py']
    code += [ROOT / rel for rel in ('critical/core/decision/bound_evidence_v2.py', 'critical/core/decision/bound_evidence.py',
        'critical/core/decision/semantic_interpretation_v5.py', 'critical/core/decision/artifacts.py',
        'critical/core/calibration/semantic_hierarchy/portable_features_v8.py',
        'critical/core/calibration/semantic_hierarchy/interpreted_features_v6.py',
        'critical/core/calibration/semantic_hierarchy/stable_features_v5.py',
        'critical/lm_engine/lm_gpt/engine.py', 'critical/lm_engine/provider_api.py',
        'critical/lm_engine/lm_template/base.py', 'critical/lm_engine/openai_compat.py')]
    code += sorted(ADDITIONS.glob('*.txt')) + [TEMPLATES / 'observe.txt']
    manifest = {'protocol_ref': digest(protocol), 'cases': cases, 'programs_ref': digest(programs), 'prompts_ref': digest(prompts),
        'source_hashes': {str(p.relative_to(ROOT)): base.fingerprint(p) for p in sources},
        'code_hashes': {str(p.relative_to(ROOT)): base.fingerprint(p) for p in code}}
    manifest['artifact_ref'] = digest(manifest)
    for name, value in (('protocol', protocol), ('manifest', manifest), ('programs', programs), ('prompts', prompts), ('references', references)):
        base.exact(out / (name + '.json'), value)
    return manifest


class ObserverCalls:
    def __init__(self, calls, template):
        self.calls, self.template = calls, template

    def call(self, stage, *args, **kwargs):
        if stage != 'bound_visual_observation_v2':
            raise ValueError('Only the observer template may be replaced')
        return self.calls.call(stage, *args, **{**kwargs, 'template': self.template})


def collect(out, live=False):
    if not live:
        raise ValueError('Additional paid diagnostic requires explicit --live approval')
    manifest = prepare(out); programs = base.read(out / 'programs.json'); prompts = base.read(out / 'prompts.json')
    def work(job):
        case, arm = job; path = out / 'cases' / arm / (case['case'] + '.json')
        if path.exists():
            return base.read(path)
        directory = out / 'ledgers' / arm / case['case']
        calls = DurableCalls(directory, base.model_factory(directory, live), identity=base.IDENTITY, max_calls=2,
            max_completion_tokens=base.CAPS['observe'] + base.INTERPRET_CAP, scope_limits={'search': 2, 'final': 0})
        row = {'case': case['case'], 'arm': arm, 'observation': None, 'interpretation': None, 'features': None, 'error': None}
        stage = 'observe'
        try:
            program = programs[case['case']]
            observed = BoundVisualObserver(ObserverCalls(calls, prompts[arm]['observe'])).observe(
                program, case['evidence'], case_id=case['case'], max_tokens=base.CAPS['observe'])
            pair = image_identity(case['evidence'])[1]
            derive_record(program, observed['observation'], pair)
            row['observation'] = observed; stage = 'interpret'
            payload = make_input(program, observed['observation'], pair)
            value, ref = calls.call('instruction_relative_interpretation', payload, schema(payload),
                template=prompts[arm]['interpret'], slot='once', max_tokens=base.INTERPRET_CAP, case_id=case['case'])
            validate(payload, value)
            row['interpretation'] = {'value': value, 'execution_ref': ref}
            row['features'] = project(program, observed['observation'], pair, value)
        except (RuntimeError, ValueError, KeyError, TypeError) as error:
            row['error'] = {'stage': stage, 'type': type(error).__name__, 'message': str(error)}
        base.exact(path, row)
        print({'case': case['case'], 'arm': arm, 'observed': row['observation'] is not None,
               'interpreted': row['interpretation'] is not None, 'error': row['error']}, flush=True)
        return row
    jobs = [(case, arm) for case in manifest['cases'] for arm in ARMS]
    jobs.sort(key=lambda job: digest([VERSION, job[0]['case'], job[1]]))
    first = work(jobs[0])
    attempted = [base.read(p) for p in (out / 'ledgers' / first['arm'] / first['case'] / 'jobs').glob('*.json')]
    if not attempted or all(j['outcome'] != 'completed' for j in attempted):
        raise RuntimeError('Provider probe did not complete; batch not dispatched and slot retained')
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(work, jobs))
    base.exact(out / 'observations.json', values); prepare(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve()
    if args.live:
        collect(out, True)
    else:
        prepare(out); print(base.read(out / 'protocol.json'))
