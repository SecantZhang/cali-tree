"""Freeze and test a task-gated reference judge on all three local training splits.

Preflight and replay are offline. Live collection makes one regular judgment per
unique case, plus one guided judgment per covered split/case. Uncovered
requests reuse the exact same regular response. No new compilation or tree fit.
"""
import argparse
import json
from pathlib import Path

from critical.core.optimization.prompt.calitree import task_coverage as tc
from critical.core.calibration.local_compression_v18 import correct
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.compiler import media_inputs
from run.calitree_local_compression_v18 import ROOT, read, fingerprint

VERSION = 'paired-task-coverage-local-v19'
IDENTITY = {'provider': 'openai', 'model': 'gpt-6-luna', 'reasoning_effort': 'none', 'temperature': 0}
CAP = 2048


def exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Changed frozen artifact: ' + str(path))
    else:
        save_json(path, value)


def prepare(out, source_root):
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'manifest.json').exists():
        verify(out); return read(out / 'manifest.json')
    evidence_dir = source_root / 'logs/exps/261018-three-sampled-splits-luna-compiler-v3'
    evidence_manifest = read(evidence_dir / 'manifest.json')
    meta = {c['case']: c for c in evidence_manifest['cases']}
    cases = {}; splits = []; jobs = {}; source_paths = {evidence_dir / 'manifest.json'}
    regular = (tc.TEMPLATES / 'regular.txt').read_text()
    for i in (1, 2, 3):
        folder = source_root / f'logs/exps/261018-local-compression-v18-r1/split{i}'
        paths = [folder / name for name in ('training_data.json', 'result.json', 'seeds.json')]
        source_paths.update(paths)
        rows, result, seeds = map(read, paths)
        programs = {}
        for row in rows:
            path = evidence_dir / 'extraction/cases' / (row['case'] + '.json'); source_paths.add(path)
            program = read(path)['compilation']['program']
            programs[row['source_group']] = program
            m = meta[row['case']]
            c = {'case': row['case'], 'source_group': row['source_group'], 'instruction': row['instruction'],
                 'reference': row['reference'], 'evidence': m['evidence'],
                 'image_hashes': {k: fingerprint(p) for k, p in m['evidence'].items()}}
            if row['case'] in cases and cases[row['case']] != c:
                raise ValueError('Shared case changed across splits')
            cases[row['case']] = c
        models = [result['registry'][k] for k in result['forest']]
        gate = tc.build(models, rows, programs)
        exact(out / f'split{i}/gate.json', gate.export())
        exact(out / f'split{i}/training_data.json', rows)
        exact(out / f'split{i}/programs.json', programs)
        judge = tc.TaskCoveredJudge(None, gate, regular_prompt=regular)
        slots = []
        for row in rows:
            baseline = judge.request(row['instruction'])
            guided = judge.request(row['instruction'], programs[row['source_group']])
            refs = []
            for request in (baseline, guided):
                # Only call-relevant contents determine reuse; gate diagnostics
                # and training metadata never enter model requests.
                spec = {k: request[k] for k in ('stage', 'payload', 'template', 'schema')}
                key = digest([row['case'], spec]); refs.append(key)
                jobs.setdefault(key, {'case': row['case'], 'request': spec})
            tree = next(m for m in models if row['source_group'] in m['fit_sources'])
            cached_prediction = tc.PortableRuleExecutor(tree['runtime']).predict_records([row['features']])[0]['prediction']
            slots.append({'case': row['case'], 'batch': row['batch'], 'baseline_job': refs[0], 'hybrid_job': refs[1],
                          'route': guided['route'], 'cached_tree_prediction': cached_prediction})
        exact(out / f'split{i}/slots.json', slots)
        splits.append({'split': i, 'slots': slots, 'original_children': [
            {'sources': s['fit_sources'], 'correct': correct(s, [r for r in rows if r['source_group'] in s['fit_sources']])}
            for s in seeds]})
    protocol = {'version': VERSION, 'identity': IDENTITY, 'cases': len(cases), 'splits': 3,
                'local_slots': sum(len(s['slots']) for s in splits), 'max_calls': len(jobs),
                'max_completion_tokens_per_call': CAP, 'max_completion_tokens': len(jobs)*CAP,
                'covered_slots': sum(slot['route']['covered'] for s in splits for slot in s['slots']),
                'compiler': 'Reuse frozen instruction-only compiler-v3 programs; zero compiler calls.',
                'regular_prompt': 'Same flat image-edit judge rubric, now matched Luna settings in both arms.',
                'design': 'One fresh baseline per unique training case. One guided response per distinct covered request. Exact regular-response reuse for uncovered requests.',
                'scope': 'Local resubstitution diagnostic; all rule support comes from these training cases. No generalization claim.',
                'comparison': 'Hybrid versus fresh regular judge and saved deterministic forest; per original child batch, no labels in requests.',
                'final_set_access': False, 'retries': 0, 'fitting_or_relabeling': False}
    code = [Path(__file__).resolve(), Path(tc.__file__).resolve(), ROOT / 'critical/core/calibration/local_compression_v18.py']
    code += list(tc.TEMPLATES.glob('*.txt'))
    code += list((ROOT / 'critical/core/decision').glob('*.py'))
    code += list((ROOT / 'critical/core/calibration/semantic_hierarchy').glob('*.py'))
    code += [ROOT / r for r in ('critical/lm_engine/lm_gpt/engine.py', 'critical/lm_engine/openai_compat.py', 'critical/lm_engine/provider_api.py')]
    manifest = {'version': VERSION, 'protocol_ref': digest(protocol), 'source_root': str(source_root),
                'source_hashes': {str(p): fingerprint(p) for p in sorted(source_paths)},
                'code_hashes': {str(p.relative_to(ROOT)): fingerprint(p) for p in code},
                'cases': cases, 'splits': splits, 'jobs': jobs}
    manifest['artifact_ref'] = digest(manifest)
    exact(out / 'protocol.json', protocol); exact(out / 'manifest.json', manifest)
    exact(out / 'estimate.json', {k: protocol[k] for k in ('cases', 'local_slots', 'covered_slots', 'max_calls', 'max_completion_tokens')})
    (out / 'run.log').write_text('Preflight completed; no model calls.\n')
    (out / 'llm-histories.log').write_text('No calls during preflight. Live histories are recorded under ledger/.\n')
    verify(out)
    return manifest


def verify(out):
    m = read(out / 'manifest.json'); protocol = read(out / 'protocol.json')
    assert digest({k: v for k, v in m.items() if k != 'artifact_ref'}) == m['artifact_ref']
    assert digest(protocol) == m['protocol_ref']
    assert protocol['identity'] == IDENTITY and protocol['max_calls'] == len(m['jobs'])
    for name, expected in m['source_hashes'].items():
        assert fingerprint(name) == expected, name
    for name, expected in m['code_hashes'].items():
        assert fingerprint(ROOT / name) == expected, name
    for c in m['cases'].values():
        for k, p in c['evidence'].items():
            assert fingerprint(p) == c['image_hashes'][k]
    seen = set()
    for s in m['splits']:
        folder = out / f"split{s['split']}"
        gate = tc.TaskCoverageGate(read(folder / 'gate.json'))
        rows = read(folder / 'training_data.json'); programs = read(folder / 'programs.json')
        source = Path(m['source_root']) / f"logs/exps/261018-local-compression-v18-r1/split{s['split']}"
        result = read(source / 'result.json')
        assert rows == read(source / 'training_data.json')
        assert gate.export() == tc.build([result['registry'][k] for k in result['forest']], rows, programs).export()
        assert s['slots'] == read(folder / 'slots.json')
        by_case = {r['case']: r for r in rows}
        judge = tc.TaskCoveredJudge(None, gate)
        for slot in s['slots']:
            c = m['cases'][slot['case']]; row = by_case[c['case']]
            assert row['reference'] == c['reference'] and row['source_group'] == c['source_group']
            tree = next(result['registry'][k] for k in result['forest'] if row['source_group'] in result['registry'][k]['fit_sources'])
            actual = tc.PortableRuleExecutor(tree['runtime']).predict_records([row['features']])[0]['prediction']
            assert slot['cached_tree_prediction'] == actual and slot['batch'] == row['batch']
            for arm, p in (('baseline', None), ('hybrid', programs[c['source_group']])):
                req = judge.request(c['instruction'], p)
                spec = {k: req[k] for k in ('stage', 'payload', 'template', 'schema')}
                key = digest([c['case'], spec]); seen.add(key)
                assert slot[arm+'_job'] == key and m['jobs'][key] == {'case': c['case'], 'request': spec}
                if arm == 'hybrid':
                    assert req['route'] == slot['route']
            if not slot['route']['covered']:
                assert slot['baseline_job'] == slot['hybrid_job']
    assert seen == set(m['jobs'])
    # Separately replay conditional recommendations against cached training
    # features. This checks rule fidelity, not the new LLM judge's accuracy.
    replayed = 0
    for s in m['splits']:
        rows = {r['case']: r for r in read(out / f"split{s['split']}/training_data.json")}
        for slot in s['slots']:
            if not slot['route']['covered']:
                continue
            row = rows[slot['case']]
            for rule in slot['route']['reference']['rules']:
                if row['features'] is not None and row['features']['features']['meaning_available'] and all(
                        row['features']['features'][c['feature']] == c['value'] for c in rule['conditions']):
                    assert tc.LABELS[row['reference']] == rule['conclusion_if_all_established']
                    replayed += 1
    exact(out / 'offline_verification.json', {'passed': True, 'slots': sum(len(s['slots']) for s in m['splits']),
                                            'matched_conditional_references_correct': replayed,
                                            'llm_accuracy_tested': False, 'new_model_calls': 0})
    return m


def collect(out, live):
    if not live:
        raise ValueError('Paid inference requires explicit --live')
    m = verify(out); protocol = read(out / 'protocol.json')
    from critical import config
    from critical.lm_engine import load_creds, get_engine, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    require_live(True)
    config.PROJECT_ROOT = Path(m['source_root'])
    config.CREDENTIALS_FILE = Path(m['source_root']) / '.env'
    creds = load_creds(provider='openai', engine='gpt')
    if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
        raise ValueError('Official OpenAI endpoint required')
    def factory(cap):
        return get_engine('gpt', creds=creds, model=IDENTITY['model'], temperature=0,
                          max_tokens=cap, timeout=180, max_http_attempts=1,
                          history=LLMHistoryWriter(out / 'ledger/llm-histories.log'))
    calls = DurableCalls(out / 'ledger', factory, identity=IDENTITY, max_calls=protocol['max_calls'],
                         max_completion_tokens=protocol['max_completion_tokens'],
                         scope_limits={'search': 4, 'final': 0})
    for index, (key, job) in enumerate(sorted(m['jobs'].items()), 1):
        path = out / 'responses' / (key + '.json')
        if path.exists():
            continue
        c = m['cases'][job['case']]; req = job['request']
        try:
            value, ref = calls.call(req['stage'], req['payload'], req['schema'], template=req['template'],
                                     media=media_inputs(c['evidence']), case_id=c['case'], slot='once', max_tokens=CAP)
            if set(value) != {'label', 'rationale'} or value['label'] not in (*tc.LABELS, 'unresolved') or not isinstance(value['rationale'], str) or not value['rationale'].strip():
                raise ValueError('Invalid judge response')
            result = {'judgment': value, 'execution_ref': ref, 'error': None}
        except (ValueError, RuntimeError) as error:
            result = {'judgment': None, 'execution_ref': None, 'error': str(error)}
        exact(path, result)
        print({'completed': index, 'total': len(m['jobs']), 'case': c['case'], 'stage': req['stage'], 'error': result['error']}, flush=True)
        if calls.budget['stopped']:
            raise RuntimeError('Provider stopped; failed slots retained')
    report(out)


def report(out):
    m = verify(out); results = []
    for s in m['splits']:
        cases = []
        for slot in s['slots']:
            c = m['cases'][slot['case']]; predictions = {}
            for arm in ('baseline', 'hybrid'):
                response_path = out / 'responses' / (slot[arm+'_job'] + '.json')
                if not response_path.exists():
                    raise ValueError('Evaluation is incomplete; accuracy cannot be reported')
                response = read(response_path)
                if response['judgment'] is not None:
                    job = read(out / 'ledger/jobs' / (response['execution_ref'] + '.json'))
                    assert job['parsed'] == response['judgment']
                    spec = m['jobs'][slot[arm+'_job']]['request']
                    assert job['payload'] == spec['payload'] and job['stage'] == spec['stage'] and job['case_id'] == c['case']
                    assert job['outcome'] == 'completed'
                label = response['judgment']['label'] if response['judgment'] else 'unresolved'
                predictions[arm] = tc.LABELS.index(label) if label in tc.LABELS else -1
            cases.append({'case': c['case'], 'batch': slot['batch'], 'reference': c['reference'],
                          'covered': slot['route']['covered'], 'cached_tree': slot['cached_tree_prediction'], **predictions})
        def stats(cohort):
            return {'total': len(cohort), 'covered': sum(r['covered'] for r in cohort),
                    **{arm+'_correct': sum(r[arm] == r['reference'] for r in cohort) for arm in ('baseline', 'hybrid', 'cached_tree')},
                    'wins': [r['case'] for r in cohort if r['hybrid'] == r['reference'] and r['baseline'] != r['reference']],
                    'losses': [r['case'] for r in cohort if r['baseline'] == r['reference'] and r['hybrid'] != r['reference']]}
        batches = {b: stats([r for r in cases if r['batch'] == b]) for b in sorted({r['batch'] for r in cases})}
        results.append({'split': s['split'], 'overall': stats(cases), 'batches': batches, 'cases': cases,
                        'preserves_each_child_vs_regular': all(v['hybrid_correct'] >= v['baseline_correct'] for v in batches.values()),
                        'preserves_each_child_vs_cached_tree': all(v['hybrid_correct'] >= v['cached_tree_correct'] for v in batches.values())})
    summary = {'version': VERSION, 'splits': results, 'scope': 'Local training accuracy, one draw per distinct request; no held-out claim.',
               'calls': read(out / 'ledger/budget.json'), 'automatic_promotion': False}
    exact(out / 'results.json', summary)
    print(json.dumps([{k: v for k, v in s.items() if k not in ('cases', 'batches')} for s in results], indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve()
    if args.report:
        report(out)
    elif args.live:
        collect(out, True)
    else:
        if args.source_root is None:
            parser.error('--source-root is required for preflight')
        prepare(out, args.source_root.resolve())
        print(json.dumps(read(out / 'estimate.json'), indent=2))
