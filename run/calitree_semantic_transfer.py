"""Frozen v16 policies on one new balanced AURORA cohort; never recalibrates."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import shutil

from critical.core.calibration.evidence_rules_v4 import classification_metrics
from critical.core.calibration.instruction_semantic_rules import ObservableDNFCalibrator
from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.calls import DurableCalls
from critical.core.decision.instruction_role_facts import compile_record
from critical.core.decision.intermediate_facts import IntermediateFactExtractor
from critical.core.decision.observable_facts import ObservableFactExtractor, fact_record
from critical.core.decision.postcondition_binding import PostconditionCompiler
from critical.core.decision.semantic_evidence import SemanticEvidenceExtractor
from critical.core.decision.semantic_policy_executor import prose_observations
from critical.database.dl_aurora.loader import AURORA_MODELS, score_to_label
from run.calitree_single_call import ROOT, IDENTITY, fingerprint, read, metrics

VERSION = 'frozen-semantic-transfer-v16-new12-v1'
SEED = 20261014
LABELS = ('no', 'partial', 'yes')
GROUPS = ('G1', 'G2', 'G3', 'G4')
POLICY_SOURCE = ROOT / 'logs/exps/261014-instruction-semantic-distillation-v16'
TRAIN_SOURCE = ROOT / 'logs/exps/261013-four-groups-local-v4'
DATA = ROOT / 'data/aurora/bench'
CAPS = {'vision': 16384, 'postconditions': 4096, 'physical': 16384, 'intermediate': 4096}
UPSTREAM = ('261014-semantic-contract-evidence-v5', '261014-observable-semantic-facts-v10',
            '261014-semantic-postconditions-v12', '261014-physical-intermediates-v13')


def select_cases(candidates, excluded):
    """Fixed class balance, category spreading, source independence, hash ties."""
    selected, used, tasks = [], set(excluded), Counter()
    for _ in range(4):
        for label in LABELS:
            eligible = [c for c in candidates if c['reference'] == label and c['group'] not in used]
            if not eligible:
                raise ValueError('Insufficient unseen source groups for ' + label)
            c = min(eligible, key=lambda r: (tasks[r['task']], digest([VERSION, SEED, r['id']])))
            selected.append({**c, 'case': f'H{len(selected)+1:02d}'})
            used.add(c['group']); tasks[c['task']] += 1
    return selected


def sample():
    from PIL import Image
    training = read(TRAIN_SOURCE / 'manifest.json')
    excluded = set(training['excluded_groups']) | {c['group'] for c in training['cases']}
    training_tasks = {c['task_uid'] for c in training['cases']}
    test = set(read(DATA / 'splits/seed_42.json')['test'])
    candidates, sources = [], {}
    for row in map(json.loads, (DATA / 'metadata.jsonl').read_text().splitlines()):
        if row['model'] != AURORA_MODELS[0] or row['task_uid'] not in test or row['task_uid'] in training_tasks:
            continue
        source = DATA / row['source_path']
        if str(source) not in sources:
            with Image.open(source) as im:
                rgb = im.convert('RGB')
                sources[str(source)] = sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        group = sources[str(source)]
        if group in excluded:
            continue
        evidence = {'source_image': str(source), 'edited_image': str(DATA / row['edited_path'])}
        candidates.append({'id': row['item_id'], 'task_uid': row['task_uid'], 'group': group,
                           'instruction': row['instruction'], 'task': row['task'], 'editing_model': row['model'],
                           'reference': score_to_label(row['human_score'])[1], 'human_score': row['human_score'],
                           'evidence': evidence, 'image_hashes': {k: fingerprint(p) for k, p in evidence.items()}})
    return select_cases(candidates, excluded), sorted(excluded), dict(Counter(c['reference'] for c in candidates))


def inference_case(case):
    """Only these fields enter collection; identity stays ledger metadata."""
    return {k: deepcopy(case[k]) for k in ('case', 'id', 'instruction', 'evidence')}


def save_exact(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError('Changed saved artifact: ' + str(path))
    else:
        save_json(path, value)


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        m = read(output / 'manifest.json'); verify(output, m); return m
    # Confirm that both the frozen learner/runtime and every extractor match
    # their training-era snapshots before creating the new test protocol.
    seals = [read(POLICY_SOURCE / 'fit_seal.json')]
    seals += [read(ROOT / 'logs/exps' / name / 'manifest.json') for name in UPSTREAM]
    for seal in seals:
        for rel, ref in seal['code_hashes'].items():
            if fingerprint(ROOT / rel) != ref:
                raise ValueError('Changed training-era source: ' + rel)
    trained = read(POLICY_SOURCE / 'results.json')
    policies = {}
    for group in GROUPS:
        source = POLICY_SOURCE / 'rules' / group / 'teacher_distilled/policy.json'
        artifact = read(source)
        if artifact != trained['groups'][group]['teacher_distilled']['policy']:
            raise ValueError('Policy disagrees with original experiment')
        model = ObservableDNFCalibrator.restore(artifact)
        dest = output / 'policies' / group
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest / 'policy.json')
        (dest / 'policy.txt').write_text(model.render() + '\n')
        policies[group] = {'source': str(source), 'sha256': fingerprint(source),
                           'local_metrics': trained['groups'][group]['teacher_distilled']['metrics']}
    cases, excluded, pool_counts = sample()
    files = [p for p in (ROOT / 'critical').rglob('*') if p.is_file() and p.suffix in ('.py', '.txt', '.json')]
    files += [Path(__file__).resolve(), ROOT / 'run/calitree_single_call.py',
              ROOT / 'tests/unit/calitree/test_semantic_transfer.py']
    code = {}
    for p in files:
        rel = str(p.relative_to(ROOT)); dst = output / 'source_snapshot' / rel
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); code[rel] = fingerprint(p)
    pins = [POLICY_SOURCE / 'results.json', POLICY_SOURCE / 'fit_seal.json', TRAIN_SOURCE / 'manifest.json',
            DATA / 'metadata.jsonl', DATA / 'splits/seed_42.json']
    pins += [ROOT / 'logs/exps' / n / 'manifest.json' for n in UPSTREAM]
    m = {'version': VERSION, 'seed': SEED, 'cases': cases, 'excluded_groups': excluded,
         'candidate_class_counts': pool_counts, 'policies': policies, 'judge_identity': IDENTITY,
         'workers': 8, 'caps': CAPS, 'max_calls': 48, 'image_calls_max': 12, 'text_calls_max': 36,
         'presentation': 'source_first', 'draws_per_stage_per_case': 1, 'http_attempts_per_slot': 1,
         'code_hashes': code, 'pinned_files': {str(p): fingerprint(p) for p in pins},
         'sampling': 'AURORA editor; repository seed-42 test split; four/class; category spread with fixed hash ties. Exclude all 48 fitting sources and all 144 previously excluded sources. No redraws.',
         'reference_mapping': 'Released mean: <0.5 No; [0.5,1.5) Partial; >=1.5 Yes. No majority-vote or agreement claim.',
         'inference': 'Unchanged v5 image observer, v10 physical facts, v12 instruction compiler, v13 intermediate facts, and v16 role compilation. Shared evidence for all four frozen teacher_distilled policies.',
         'evaluation': 'Restore and predict only. No fit, optimization, routing, ensemble, threshold adjustment, or policy selection. Keep failures and unresolved cases in denominator.',
         'scope': 'New source-disjoint cohort relative to the frozen study and its recorded exclusions. Historical unrelated project experiments are not guaranteed untouched; no repeat-robustness claim.'}
    save_json(output / 'manifest.json', m); save_json(output / 'seal.json', {'manifest_ref': digest(m)})
    save_json(output / 'estimate.json', {'max_model_calls': 48, 'image_calls': 12, 'text_calls': 36,
                                       'max_completion_tokens': 12 * sum(CAPS.values()), 'calibration_calls': 0,
                                       'policies': 4, 'policy_case_predictions': 48})
    verify(output, m)
    return m


def verify(output, m):
    if (digest(m) != read(output / 'seal.json')['manifest_ref'] or m['version'] != VERSION
            or m['judge_identity'] != IDENTITY or m['caps'] != CAPS):
        raise ValueError('Changed frozen evaluation protocol')
    cases = m['cases']
    if (len(cases) != 12 or len({c['group'] for c in cases}) != 12
            or Counter(c['reference'] for c in cases) != dict.fromkeys(LABELS, 4)
            or {c['group'] for c in cases} & set(m['excluded_groups'])):
        raise ValueError('Changed cohort balance or source independence')
    test = set(read(DATA / 'splits/seed_42.json')['test'])
    for c in cases:
        if c['task_uid'] not in test or c['editing_model'] != AURORA_MODELS[0] or score_to_label(c['human_score'])[1] != c['reference']:
            raise ValueError('Changed data semantics')
        for k, path in c['evidence'].items():
            if fingerprint(path) != c['image_hashes'][k]:
                raise ValueError('Changed test image')
    for group, p in m['policies'].items():
        if fingerprint(p['source']) != p['sha256'] or fingerprint(output / 'policies' / group / 'policy.json') != p['sha256']:
            raise ValueError('Frozen policy changed')
    for p, ref in m['pinned_files'].items():
        if fingerprint(p) != ref:
            raise ValueError('Pinned input changed: ' + p)
    for rel, ref in m['code_hashes'].items():
        if fingerprint(ROOT / rel) != ref or fingerprint(output / 'source_snapshot' / rel) != ref:
            raise ValueError('Frozen code changed: ' + rel)


def collect(output, m, live):
    from critical import config
    from critical.lm_engine import get_engine, load_creds, require_live
    from critical.logging.llm_history import LLMHistoryWriter
    config.PROJECT_ROOT = ROOT; config.CREDENTIALS_FILE = ROOT / '.env'
    creds = None
    if live:
        require_live(True); creds = load_creds(provider='openai', engine='gpt')
        if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
            raise ValueError('Official OpenAI only')
    cases = [inference_case(c) for c in m['cases']]

    def work(task):
        c, stage, previous = task
        row = {'case': c['case'], 'stage': stage, 'result': None, 'error': None}
        if stage in ('physical', 'intermediate') and previous is None:
            row['error'] = 'Missing source observation; no dependent call made'
            return row
        directory = output / 'ledgers' / c['case'] / stage
        if not live and not list((directory / 'jobs').glob('*.json')):
            raise ValueError('Missing replay slot: ' + str(directory))
        cap = CAPS[stage]

        def factory(limit):
            if not live:
                raise AssertionError('Replay attempted a model call')
            return get_engine('gpt', creds=creds, model=IDENTITY['model'], reasoning_effort=IDENTITY['reasoning_effort'],
                              temperature=None, max_tokens=limit, timeout=180, max_http_attempts=1,
                              history=LLMHistoryWriter(directory / 'llm-histories.log'))
        calls = DurableCalls(directory, factory, identity=IDENTITY, max_calls=1,
                             max_completion_tokens=cap, scope_limits={'search': 1, 'final': 1})
        try:
            kwargs = {'case_id': c['id'], 'max_tokens': cap}
            if stage == 'vision':
                row['result'] = SemanticEvidenceExtractor(calls).extract(c['instruction'], c['evidence'], **kwargs)
            elif stage == 'postconditions':
                row['result'] = PostconditionCompiler(calls).compile(c['instruction'], **kwargs)
            else:
                extractor = ObservableFactExtractor if stage == 'physical' else IntermediateFactExtractor
                row['result'] = extractor(calls).extract(c['instruction'], previous['observations'], **kwargs)
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
            jobs = list((directory / 'jobs').glob('*.json'))
            if jobs and (job := read(jobs[0]))['outcome'] != 'completed':
                row['error'] = job.get('error') or job['outcome']
        save_exact(output / 'stage_records' / c['case'] / (stage + '.json'), row)
        print({'case': c['case'], 'stage': stage, 'ok': row['result'] is not None, 'error': row['error']}, flush=True)
        return row

    with ThreadPoolExecutor(max_workers=m['workers']) as pool:
        first = list(pool.map(work, [(c, s, None) for c in cases for s in ('vision', 'postconditions')]))
        vision = {r['case']: r['result'] for r in first if r['stage'] == 'vision'}
        second = list(pool.map(work, [(c, s, vision[c['case']]) for c in cases for s in ('physical', 'intermediate')]))
    stages = {(r['case'], r['stage']): r for r in first + second}
    rows = []
    for c in cases:
        outputs = {s: stages[c['case'], s] for s in CAPS}
        record = None
        if all(r['result'] is not None for r in outputs.values()):
            record = compile_record(fact_record(outputs['physical']['result']['observations']),
                                    outputs['postconditions']['result']['program'],
                                    {'facts': {k: f['state'] for k, f in outputs['intermediate']['result']['observations']['facts'].items()}})
        rows.append({'case': c['case'], 'stages': outputs, 'record': record})
    return rows


def predict_frozen(policies, records):
    """No targets or case metadata accepted, and no fit method is called."""
    before = digest([policies, records])
    result = {name: ObservableDNFCalibrator.restore(policy).predict_records(records)
              for name, policy in policies.items()}
    if digest([policies, records]) != before:
        raise AssertionError('Inference mutated a policy or evidence')
    return result


def evaluate(cases, predictions):
    result = {}
    for name, decisions in predictions.items():
        if len(decisions) != len(cases):
            raise ValueError('Unpaired predictions')
        rows = [{**{k: c[k] for k in ('case', 'id', 'instruction', 'reference', 'human_score')},
                 'prediction': LABELS[d['prediction']] if d['prediction'] >= 0 else None, 'decision': d}
                for c, d in zip(cases, decisions)]
        result[name] = {'metrics': metrics(rows),
                        'class_metrics': classification_metrics([d['prediction'] for d in decisions],
                                                               [LABELS.index(c['reference']) for c in cases])[0],
                        'cases': rows}
    return result


def usage(output):
    result = {}
    for stage in CAPS:
        jobs = [read(p) for p in sorted((output / 'ledgers').glob('*/' + stage + '/jobs/*.json'))]
        responses = [j['response'] for j in jobs if j.get('response')]
        result[stage] = {'attempts': len(jobs), 'outcomes': dict(Counter(j['outcome'] for j in jobs)),
                         'input_tokens': sum(r.get('promptTokens', 0) for r in responses),
                         'completion_tokens': sum(r.get('completionTokens', 0) for r in responses),
                         'returned_models': sorted({r.get('model', 'unknown') for r in responses})}
    return result


def audit(output, m, observations, predictions):
    """Check exact model payloads, policies, pairing, and target independence."""
    from critical.core.decision.observable_facts import PREDICATES
    from critical.core.decision.intermediate_facts import PREDICATES as MID
    verify(output, m)
    checked = 0
    for case, row in zip(m['cases'], observations):
        if case['case'] != row['case']:
            raise AssertionError('Evidence reordered')
        for stage, part in row['stages'].items():
            jobs = list((output / 'ledgers' / case['case'] / stage / 'jobs').glob('*.json'))
            if not jobs:
                if stage not in ('physical', 'intermediate') or row['stages']['vision']['result'] is not None:
                    raise AssertionError('Unaccounted missing slot')
                continue
            if len(jobs) != 1:
                raise AssertionError('Repeated model attempt')
            job = read(jobs[0]); expected = {'instruction': case['instruction']}
            if stage == 'postconditions':
                expected['observable_predicates'] = PREDICATES
            elif stage in ('physical', 'intermediate'):
                expected['predicate_bank' if stage == 'physical' else 'physical_predicate_bank'] = PREDICATES if stage == 'physical' else MID
                expected['observations'] = prose_observations(row['stages']['vision']['result']['observations'])
            if job['payload'] != expected:
                raise AssertionError('Changed or non-whitelisted model payload')
            if stage == 'vision':
                expected_media = [{'type': 'text', 'text': 'SOURCE image'},
                                  {'type': 'image', 'sha256': case['image_hashes']['source_image']},
                                  {'type': 'text', 'text': 'EDITED image'},
                                  {'type': 'image', 'sha256': case['image_hashes']['edited_image']}]
                if job['media_identity'] != expected_media:
                    raise AssertionError('Changed image presentation')
            elif job['media_identity']:
                raise AssertionError('Unexpected additional image presentation')
            if part['result'] is not None:
                key = 'program' if stage == 'postconditions' else 'observations'
                if job['parsed'] != part['result'][key] or job['execution_ref'] != part['result']['execution_ref']:
                    raise AssertionError('Saved observations differ from model output')
            checked += 1
    policies = {g: read(output / 'policies' / g / 'policy.json') for g in GROUPS}
    records = [r['record'] for r in observations]
    if predictions != predict_frozen(policies, records):
        raise AssertionError('Frozen inference changed')
    training = read(TRAIN_SOURCE / 'manifest.json')['cases']
    return {'passed': True, 'checked_payloads': checked, 'shared_evidence_ref': digest(records),
            'policy_sha256': {g: fingerprint(output / 'policies' / g / 'policy.json') for g in GROUPS},
            'training_source_overlap': len({c['group'] for c in training} & {c['group'] for c in m['cases']}),
            'training_task_overlap': len({c['task_uid'] for c in training} & {c['task_uid'] for c in m['cases']}),
            'calibration_calls': 0, 'model_payloads_whitelisted': True, 'frozen_prediction_replay': True}


def report(output, m, result):
    lines = ['# Frozen semantic policies: new balanced AURORA twelve-case transfer', '',
             'Four teacher-distilled v16 policies were copied and hashed before calls. All four use the exact same new evidence; no recalibration, policy routing, or ensemble.',
             'GPT-6.1 Sol/high; AURORA editor only; one SOURCE-first image presentation and one attempt per existing extraction stage. Four cases per released-mean-derived label.', '',
             '| Frozen policy | Original local accuracy | New accuracy | No recall | Partial recall | Yes recall | Resolved | Macro-F1 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for g, arm in result['policies'].items():
        a = arm['metrics']; local = m['policies'][g]['local_metrics']
        rates = ' | '.join(f"{a['per_class_recall'][k]:.0%}" for k in LABELS)
        lines.append(f"| {g} | {local['correct']}/12 | {a['correct']}/12 ({a['accuracy']:.1%}) | {rates} | {a['resolved']}/12 | {arm['class_metrics']['macro_f1']:.3f} |")
    lines += ['', 'Unresolved predictions remain in the twelve-case accuracy denominator.', '',
              '| Case | Instruction | Mean | Reference | G1 | G2 | G3 | G4 |', '|---|---|---:|---|---|---|---|---|']
    for i, c in enumerate(m['cases']):
        preds = ' | '.join(result['policies'][g]['cases'][i]['prediction'] or 'unresolved' for g in GROUPS)
        lines.append(f"| {c['case']} | {c['instruction'].replace('|', '/')} | {c['human_score']:g} | {c['reference']} | {preds} |")
    lines += ['', '## Evidence and limits', '',
              f"Source overlap with all 48 fitting cases: {result['audit']['training_source_overlap']}; task overlap: {result['audit']['training_task_overlap']}. The 144 earlier excluded sources are also excluded.",
              'The source image observer still emits its original graded schema; only grade-free prose reaches the physical extractors, and only physical states reach the frozen rules. Extraction prompts and runtime code match the training-era snapshots.',
              'This tests new-case transfer, not repeated-run robustness. Twelve cases are a small sample; each label has only four examples. No policy should be selected or tuned on this set and then described as independently validated on it.',
              'Labels are derived from released mean human scores (<0.5 No; <1.5 Partial; otherwise Yes), not recovered individual votes. The sample is disjoint from the frozen study and its recorded exclusions; unrelated historical experiments may have seen some source images.', '',
              '## Calls', '', '| Stage | Attempts | Outcomes | Input tokens | Completion tokens |', '|---|---:|---|---:|---:|']
    for s, u in result['usage'].items():
        lines.append(f"| {s} | {u['attempts']} | {json.dumps(u['outcomes'])} | {u['input_tokens']} | {u['completion_tokens']} |")
    (output / 'report.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('preflight', 'live', 'replay'):
        modes.add_argument('--' + mode, action='store_true')
    args = parser.parse_args(); output = args.output_dir.resolve(); m = prepare(output)
    if args.preflight:
        print(read(output / 'estimate.json'))
        print({'class_counts': dict(Counter(c['reference'] for c in m['cases'])),
               'categories': dict(Counter(c['task'] for c in m['cases'])), 'eligible_pool': m['candidate_class_counts']})
        return
    observations = collect(output, m, args.live)
    save_exact(output / 'observations.json', observations)
    policies = {g: read(output / 'policies' / g / 'policy.json') for g in GROUPS}
    predictions = predict_frozen(policies, [r['record'] for r in observations])
    save_exact(output / 'predictions.json', predictions)
    checks = audit(output, m, observations, predictions)
    result = {'version': VERSION, 'manifest_ref': digest(m), 'model': IDENTITY,
              'policies': evaluate(m['cases'], predictions), 'audit': checks, 'usage': usage(output)}
    save_exact(output / 'results.json', result); save_exact(output / 'audit.json', checks)
    report(output, m, result)
    if args.replay:
        save_exact(output / 'replay.json', {'exact_replay': True, 'new_api_calls': 0,
                                          'results_sha256': fingerprint(output / 'results.json')})
    else:
        (output / 'llm-histories.log').write_text(''.join(p.read_text() for p in sorted((output / 'ledgers').glob('*/*/llm-histories.log'))))
    print({g: arm['metrics'] for g, arm in result['policies'].items()})


if __name__ == '__main__':
    main()
