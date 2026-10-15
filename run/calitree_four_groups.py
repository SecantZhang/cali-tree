"""Four disjoint balanced twelve-case local fits with the fixed v4 objective."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import json
import shutil

from critical.core.calibration.evidence_rules_v4 import ClassBalancedEvidenceRuleCalibrator, OBJECTIVE, classification_metrics
from critical.core.calibration.evidence_rules_v3 import FEATURES, LABELS, LIMITS, PREDICATES
from critical.core.calibration.registry import CalibrationRegistry
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.rich_evidence import RichEvidenceExtractor, SCHEMA, prompt
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_benchmark36 import infer_arm
from run.calitree_recalibrate import score
from run.calitree_single_call import CAP, IDENTITY, ROOT, fingerprint, read

VERSION = 'four-balanced-twelve-local-v4-v1'
SEED = 20261013
PREVIOUS = ROOT / 'logs/exps/261013-flat-vs-calitree36-v1'
FLAT = ROOT / 'logs/exps/261013-flat-sol-high-balanced12'


def select_batches(candidates, excluded, *, batches=4, per_class=4):
    chosen, used, global_tasks = [], set(excluded), Counter()
    for number in range(1, batches+1):
        local_tasks = Counter()
        for _ in range(per_class):
            for label in LABELS:
                eligible = [r for r in candidates if r['reference'] == label and r['group'] not in used]
                if not eligible: raise ValueError('Insufficient distinct sources for ' + label)
                row = min(eligible, key=lambda r: (local_tasks[r['task']], global_tasks[r['task']],
                                                   digest([VERSION, SEED, number, r['id']])))
                n = sum(r['batch'] == f'G{number}' for r in chosen)+1
                chosen.append({**row, 'batch': f'G{number}', 'case': f'G{number}C{n:02d}'})
                used.add(row['group']); local_tasks[row['task']] += 1; global_tasks[row['task']] += 1
    return chosen


def sample():
    from PIL import Image
    previous = read(PREVIOUS / 'manifest.json')
    excluded = set(previous['excluded_groups']) | {r['group'] for r in previous['cases']}
    test = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['test'])
    candidates, groups = [], {}
    for row in map(json.loads, (ROOT / 'data/aurora/bench/metadata.jsonl').read_text().splitlines()):
        if row['model'] != AURORA_MODELS[0] or row['task_uid'] not in test: continue
        source = ROOT / 'data/aurora/bench' / row['source_path']
        if str(source) not in groups:
            with Image.open(source) as im:
                rgb = im.convert('RGB'); groups[str(source)] = sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        group = groups[str(source)]
        if group in excluded: continue
        images = {'source_image': str(source), 'edited_image': str(ROOT / 'data/aurora/bench' / row['edited_path'])}
        candidates.append({'id': row['item_id'], 'task_uid': row['task_uid'], 'group': group,
                           'instruction': row['instruction'], 'task': row['task'], 'editing_model': row['model'],
                           'reference': score_to_label(row['human_score'])[1], 'human_score': row['human_score'],
                           'evidence': images, 'image_hashes': {k: fingerprint(p) for k, p in images.items()}})
    return select_batches(candidates, excluded), sorted(excluded)


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    cases, excluded = sample()
    if fingerprint(FLAT / 'prompt.txt') != read(FLAT / 'manifest.json')['prompt_sha256']:
        raise ValueError('Changed fixed flat prompt')
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_benchmark36.py', ROOT / 'run/calitree_recalibrate.py',
              ROOT / 'run/calitree_single_call.py', ROOT / 'run/calitree_local_calibration.py']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); code[rel] = fingerprint(p)
    (output / 'flat_prompt.txt').write_text((FLAT / 'prompt.txt').read_text())
    (output / 'rich_prompt.txt').write_text(prompt())
    m = {'version': VERSION, 'seed': SEED, 'cases': cases, 'excluded_groups': excluded,
         'judge_identity': IDENTITY, 'workers': 8, 'max_calls': 96, 'draws_per_arm_per_case': 1,
         'http_attempts_per_slot': 1, 'presentation': 'source_first', 'max_completion_tokens_per_call': CAP,
         'objective': OBJECTIVE, 'limits': LIMITS, 'predicates': PREDICATES, 'features': list(FEATURES),
         'rich_prompt_ref': digest(prompt()), 'rich_schema_ref': digest(SCHEMA),
         'flat_prompt_ref': digest((output / 'flat_prompt.txt').read_text()), 'code_hashes': code,
         'metadata_sha256': fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl'),
         'split_sha256': fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json'),
         'pinned_files': {str(p): fingerprint(p) for p in (PREVIOUS / 'manifest.json', FLAT / 'manifest.json', FLAT / 'prompt.txt')},
         'sampling': 'Four nonoverlapping groups, each four/class; AURORA editor only; official test tasks; exclude listed prior fit sources/reserved holdout and preceding 36; category spreading and hash ties.',
         'fitting': 'Fit v4 independently on each group and score that exact group. No pooled fitting or cross-group feedback.',
         'infeasibility': 'Report failure if no policy satisfies class/support gates; no relaxed gate, resampling or collapsed fallback.',
         'scope': 'Four local fitting replications, not held-out transfer or repeated-model robustness. Historically queried project examples may remain.',
         'authorization': 'Try it on 4 different 12 cases groups.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'new_calls_max': 96, 'flat_calls': 48, 'rich_calls': 48,
              'fitting_api_calls': 0, 'max_completion_tokens': 96*CAP,
              'output_token_cost_ceiling_usd': 96*CAP*10/1_000_000, 'input_cost': 'Additional; actual usage reported.',
              'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-6.1-sol'})
    verify(output, m); return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['objective'] != OBJECTIVE or m['limits'] != LIMITS or m['predicates'] != PREDICATES
            or m['judge_identity'] != IDENTITY or m['rich_prompt_ref'] != digest(prompt())
            or m['rich_schema_ref'] != digest(SCHEMA) or (output / 'rich_prompt.txt').read_text() != prompt()
            or m['flat_prompt_ref'] != digest((output / 'flat_prompt.txt').read_text())):
        raise ValueError('Changed four-group protocol')
    cases = m['cases']; groups = {r['group'] for r in cases}
    if len(cases) != 48 or len(groups) != 48 or groups & set(m['excluded_groups']):
        raise ValueError('Source overlap or changed sample')
    test = set(read(ROOT / 'data/aurora/bench/splits/seed_42.json')['test'])
    for name in ('G1','G2','G3','G4'):
        subset = [r for r in cases if r['batch'] == name]
        if len(subset) != 12 or Counter(r['reference'] for r in subset) != dict.fromkeys(LABELS, 4):
            raise ValueError('Changed group balance')
    for r in cases:
        if r['task_uid'] not in test or r['editing_model'] != AURORA_MODELS[0] or score_to_label(r['human_score'])[1] != r['reference']:
            raise ValueError('Changed reference/source semantics')
        for k, path in r['evidence'].items():
            if fingerprint(path) != r['image_hashes'][k]: raise ValueError('Changed image')
    for p, h in m['pinned_files'].items():
        if fingerprint(p) != h: raise ValueError('Changed original fitting manifest/prompt')
    for rel, h in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != h or fingerprint(output / 'source_snapshot' / rel) != h:
            raise ValueError('Changed frozen source')
    if (fingerprint(ROOT / 'data/aurora/bench/metadata.jsonl') != m['metadata_sha256']
            or fingerprint(ROOT / 'data/aurora/bench/splits/seed_42.json') != m['split_sha256']):
        raise ValueError('Changed dataset metadata')


def collect(output, m, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'; creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']: raise ValueError('Official OpenAI only')
    tasks = []
    for i, c in enumerate(m['cases']):
        tasks += [(c, arm) for arm in (('flat','calitree') if i%2 == 0 else ('calitree','flat'))]
    def work(task):
        case, arm = task; directory = output / 'ledgers' / case['case'] / arm
        if not live and not list((directory / 'jobs').glob('*.json')): raise ValueError('Missing replay slot')
        def factory(cap):
            if not live: raise AssertionError('Replay attempted a model call')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort='high',
                              temperature=None, max_tokens=cap, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=CAP, scope_limits={'search': 1, 'final': 1})
        row = {k: case[k] for k in ('case','id','batch','instruction')}
        row.update(arm=arm, prediction=None, error=None)
        try:
            if arm == 'flat':
                row.update(infer_arm(case, 'flat', calls, policy=None, flat_prompt=(output / 'flat_prompt.txt').read_text()))
            else:
                row['extraction'] = RichEvidenceExtractor(calls).extract(case['instruction'], case['evidence'],
                                                                       case_id=case['id'], max_tokens=CAP)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed': row['error'] = job.get('error') or job['outcome']
        print({'batch':case['batch'],'case':case['case'],'arm':arm,
               'observed':row.get('extraction') is not None if arm == 'calitree' else row['prediction'] is not None,
               'error':row['error']},flush=True)
        return row
    with ThreadPoolExecutor(max_workers=m['workers']) as pool: return list(pool.map(work, tasks))


def class_metrics(rows):
    return classification_metrics([LABELS.index(r['prediction']) if r['prediction'] is not None else -1 for r in rows],
                                  [LABELS.index(r['reference']) for r in rows])[0]


def fit_batches(cases, observations):
    """Each fit receives only its own group's inputs, labels and source groups."""
    by_key = {(r['id'],r['arm']):r for r in observations}; batches = {}; flat_all = []; local_all = []; artifacts = {}
    for name in ('G1','G2','G3','G4'):
        subset = [c for c in cases if c['batch'] == name]
        rich = [by_key[(c['id'],'calitree')] for c in subset]
        flat = [{**by_key[(c['id'],'flat')],'reference':c['reference']} for c in subset]
        valid = [i for i,r in enumerate(rich) if r.get('extraction') is not None]
        inputs = [{'instruction':rich[i]['instruction'],'observations':rich[i]['extraction']['observations']} for i in valid]
        targets = [LABELS.index(subset[i]['reference']) for i in valid]; groups = [subset[i]['group'] for i in valid]
        artifact = None; error = None; predictions = {}
        try:
            model = ClassBalancedEvidenceRuleCalibrator().fit(inputs,targets,source_groups=groups)
            artifact = model.metadata(); predictions = dict(zip(valid,model.predict_records(inputs)))
        except ValueError as exc: error = str(exc)
        local = [{**{k:c[k] for k in ('case','id','batch','instruction','reference')},
                  'prediction':predictions[i]['label'] if i in predictions else None,
                  'decision':predictions.get(i), 'extraction_error':rich[i].get('error')}
                 for i,c in enumerate(subset)]
        fitted = artifact is not None
        status = 'qualified_local_fit' if fitted else 'infeasible'
        batches[name] = {'fit_status':status,'fit_error':error,'valid_extractions':len(valid),
                         'flat_metrics':score(flat),'flat_class_metrics':class_metrics(flat),
                         'local_metrics':score(local) if fitted else None,
                         'local_class_metrics':class_metrics(local) if fitted else None,
                         'flat_cases':flat,'cases':local,'policy':artifact}
        artifacts[name] = {'status':status,'policy':artifact,'fit_error':error,
                           'fit_case_ids':[subset[i]['id'] for i in valid],
                           'fit_source_groups':groups,'extraction_ref':digest(rich)}
        flat_all += flat; local_all += local
    qualified = [name for name,b in batches.items() if b['fit_status'] == 'qualified_local_fit']
    q_flat = [r for r in flat_all if r['batch'] in qualified]; q_local = [r for r in local_all if r['batch'] in qualified]
    summary = {'qualified_groups':qualified,'qualified_count':len(qualified),'planned_groups':4,
               'flat_all48':score(flat_all),'flat_all48_class_metrics':class_metrics(flat_all),
               'all48_with_failed_group_abstentions':score(local_all),
               'qualified_local':score(q_local) if q_local else None,
               'qualified_local_class_metrics':class_metrics(q_local) if q_local else None,
               'flat_same_qualified_cases':score(q_flat) if q_flat else None}
    return batches, summary, artifacts


def execute(output, m, live):
    observations = collect(output,m,live)
    path = output / 'observations.json'
    if path.exists() and read(path) != observations: raise ValueError('Changed saved observations')
    if not path.exists():
        if not live: raise ValueError('Replay requires observations')
        save_json(path,observations)
    batches, summary, artifacts = fit_batches(m['cases'],observations)
    bundle = {'version':VERSION,'objective':OBJECTIVE,'batches':artifacts,'observations_ref':digest(observations)}
    if live:
        version,path = CalibrationRegistry(output / 'registry').publish(bundle)
        seal = {'version':version,'path':str(path.relative_to(output)),'artifact_ref':digest(bundle)}
        if (output / 'policy_seal.json').exists() and read(output / 'policy_seal.json') != seal: raise ValueError('Changed policy bundle')
        save_json(output / 'policy_seal.json',seal)
    else:
        seal = read(output / 'policy_seal.json'); old = read(output / seal['path'])
        if digest(old) != seal['artifact_ref'] or old != bundle: raise ValueError('Exact refit changed bundle')
    usage = {}
    for arm in ('flat','calitree'):
        jobs = [read(p) for p in sorted((output / 'ledgers').glob('*/'+arm+'/jobs/*.json'))]
        responses = [j['response'] for j in jobs if j.get('response')]
        usage[arm] = {'attempts':len(jobs),'outcomes':dict(Counter(j['outcome'] for j in jobs)),
                      'input_tokens':sum(r.get('promptTokens',0) for r in responses),
                      'completion_tokens':sum(r.get('completionTokens',0) for r in responses)}
    return {'version':VERSION,'model':IDENTITY,'scope':m['scope'],'batches':batches,'summary':summary,
            'registry':seal,'usage':usage,'objective':OBJECTIVE,'limits':LIMITS}


def report(output,r):
    lines = ['# Four separate balanced twelve-case local fits','',
             '**Each group is fitted and scored on its own twelve labels. These are local fitting results.**',
             'All four groups were frozen before calls; no source overlaps across groups or with the listed prior fits.',
             'Same GPT-6.1 Sol/high, prompts, v4 macro-F1 objective, depth/support limits and SOURCE-first presentation.', '',
             '| Group | Flat accuracy | Local accuracy | Flat F1 | Local F1 | No / Partial / Yes correct | Status |',
             '|---|---:|---:|---:|---:|---|---|']
    for name,b in r['batches'].items():
        local = b['local_metrics']; cls = b['local_class_metrics']
        counts = ' / '.join(str(cls['per_class'][k]['correct']) for k in LABELS) if cls else '—'
        local_acc = f"{local['correct']}/12 ({local['accuracy']:.1%})" if local else 'No eligible policy'
        local_f1 = f"{cls['macro_f1']:.3f}" if cls else '—'
        lines.append(f"| {name} | {b['flat_metrics']['correct']}/12 ({b['flat_metrics']['accuracy']:.1%}) | {local_acc} | {b['flat_class_metrics']['macro_f1']:.3f} | {local_f1} | {counts} (each /4) | {b['fit_status']} |")
    s = r['summary']; lines += ['',f"Qualified local fits: {s['qualified_count']}/4 groups."]
    if s['qualified_local']:
        q = s['qualified_local']; f = s['flat_same_qualified_cases']
        lines += [f"Pooled qualified-group cases: local {q['correct']}/{q['total']} ({q['accuracy']:.1%}), flat on those same cases {f['correct']}/{f['total']} ({f['accuracy']:.1%}).",
                  f"Qualified-group pooled local macro-F1: {s['qualified_local_class_metrics']['macro_f1']:.3f}."]
    lines += [f"Flat across all 48: {s['flat_all48']['correct']}/48 ({s['flat_all48']['accuracy']:.1%}).",
              'Failed-group cases are separately retained as abstentions in the machine-readable all-48 end-to-end score. They are not silently omitted from fit coverage.', '',
              '## Per-group policies and cases','']
    from run.calitree_local_calibration import rule_text
    for name,b in r['batches'].items():
        lines += [f'### {name}','']
        if b['policy']:
            lines += ['```text',*rule_text(b['policy']['tree']),'```','',f"Definite leaf support: {b['policy']['leaf_support']}.",'']
        else: lines += [f"Fit failed: {b['fit_error']}",'']
        lines += ['| Case | Instruction | Reference | Flat | Local |','|---|---|---|---|---|']
        for a,c in zip(b['flat_cases'],b['cases']):
            lines.append(f"| {c['case']} | {c['instruction'].replace('|','/')} | {c['reference']} | {a['prediction'] or 'unresolved'} | {c['prediction'] or 'unresolved'} |")
        lines += ['']
    lines += ['## Interpretation limits','',
              'Four different local batches test fitting consistency, not unseen transfer. Policies receive their own twelve reference labels.',
              'The absolute two-correct-source class gate requires at least 50% recall per class on a twelve-case group. It was not reduced to make more groups qualify.',
              'No resampling or objective changes follow failures. A group can be infeasible under the fixed shallow, monotone, reusable grammar.',
              'Successful-group averages are conditional on fit feasibility. Always consider the number of infeasible groups and all-48 coverage.',
              'Human labels are discretized aggregate means. Unknown or failed observations remain in denominators; no repeated model judgments were collected.',
              f"Usage: {r['usage']}",'']
    (output / 'report.md').write_text('\n'.join(lines))
    (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/*/llm-histories.log'))))


def main():
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true');mode.add_argument('--live',action='store_true');mode.add_argument('--replay',action='store_true')
    args = p.parse_args();output = args.output_dir.resolve()
    if args.replay and not (output / 'results.json').exists(): raise ValueError('Replay needs saved results')
    m = prepare(output)
    if args.preflight:
        print({'ready':True,'groups':4,'classes_per_group':{k:4 for k in LABELS},'unique_cases':48,'max_calls':96,'workers':m['workers']});return
    result = execute(output,m,args.live);verify(output,m)
    if args.replay:
        if read(output / 'results.json') != result: raise ValueError('Replay changed results')
        save_json(output / 'verification.json',{'exact_refit_and_replay':True,'new_api_calls':0,
                  'groups_disjoint':True,'no_cross_group_fit':True,'results_sha256':fingerprint(output / 'results.json')})
        print({'exact_refit_and_replay':True,'new_api_calls':0})
    else:
        if (output / 'results.json').exists() and read(output / 'results.json') != result: raise ValueError('Different saved results')
        save_json(output / 'results.json',result);report(output,result)
        print({'summary':result['summary'],'groups':{k:{'status':v['fit_status'],'flat':v['flat_metrics'],'local':v['local_metrics'],'fit_error':v['fit_error']} for k,v in result['batches'].items()}})


if __name__ == '__main__':main()
