"""Per-case GEPA robustness pilot. Offline by default; live calls require --live."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import threading
import time

import numpy as np
from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError
from vejudge.lm_engine import load_creds, openai_compat
from vejudge.lm_engine.gate import require_live

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/260923-20:00:01-exps/selected_records.json'
WORKER = ROOT / 'run/aurora_prompt_repair/gepa_worker.py'
ARMS = ('unchanged', 'single', 'repeated')
LABELS = ('no', 'partial', 'yes')
RULES = ('Revise a reusable semantic-consistency rubric, preserving JSON fields label and '
         'rationale and labels no/partial/yes. Never hardcode the answer, copy the focal '
         'instruction, or include case identifiers, editor identity, or image-specific '
         'exceptions. Perceptual aesthetics alone must not affect semantic consistency. '
         'Use the observed rationales as hypotheses, not verified internal reasoning. '
         'Address recurring misinterpretations while preserving correct interpretations. '
         'If every draw is correct, clarify the existing boundary without changing its meaning.')


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def load_cases(source=SOURCE):
    cases = []
    for bundle in json.loads(source.read_text()):
        c = dict(bundle['case'])
        c['prompt'] = bundle['ablation']['original']['prompt']
        c['prompt_sha256'] = digest(c['prompt'])
        if c['prompt_sha256'] != bundle['structured']['original_prompt_sha256']:
            raise ValueError('Original prompt hash mismatch')
        for kind in ('source', 'edited'):
            if digest(Path(c[f'{kind}_local_image']).read_bytes()) != c[f'{kind}_image_sha256']:
                raise ValueError('Image hash mismatch')
        cases.append(c)
    if len(cases) != 10 or len({c['task_uid'] for c in cases}) != 10:
        raise ValueError('Expected ten distinct frozen tasks')
    return cases


def parse(raw, finish='stop'):
    try:
        text = raw.strip()
        if text.startswith('```'):
            text = '\n'.join(text.splitlines()[1:-1])
        value = json.loads(text)
        valid = (finish == 'stop' and value.get('label') in LABELS and
                 isinstance(value.get('rationale'), str) and bool(value['rationale'].strip()))
        return {'valid': valid, 'label': value.get('label', ''),
                'rationale': value.get('rationale', ''), 'finish_reason': finish}
    except (ValueError, AttributeError, TypeError):
        return {'valid': False, 'label': '', 'rationale': '', 'finish_reason': finish}


def correct(draw, target):
    return int(draw.get('valid', False) and draw.get('label') == target)


def aggregate(draws, target):
    counts = Counter(d['label'] if d['valid'] else 'invalid' for d in draws)
    evidence = [{'draw': n, **d, 'correct': bool(correct(d, target))}
                for n, d in enumerate(draws)]
    accuracy = sum(correct(d, target) for d in draws) / len(draws)
    feedback = (f'Human target label: {target}. Correct: {sum(correct(d, target) for d in draws)}'
                f'/{len(draws)}. Observed labels: {dict(counts)}.\n'
                'The evidence lists every sampled outcome, including successes and failures. '
                'Compare rationales across labels to identify possible interpretation conflicts; '
                'do not invent visual facts.\n' + RULES)
    return {'accuracy': accuracy, 'counts': dict(counts), 'draws': evidence, 'feedback': feedback}


def improves(parent, child):
    return child['accuracy'] > parent['accuracy']


def candidate_issue(prompt, case):
    if not prompt.strip() or len(prompt) > 20000:
        return 'empty or oversized prompt'
    for field in ('case_id', 'task_uid', 'item_id', 'instruction'):
        if str(case[field]).lower() in prompt.lower():
            return f'copies {field}'
    if not all(re.search(r'\b' + word + r'\b', prompt.lower()) for word in (*LABELS, 'label', 'rationale')):
        return 'missing output contract'
    if re.search(r'\balways\s+(?:return|output|predict|answer)\s+[\"\s]*(?:no|partial|yes)\b', prompt.lower()):
        return 'unconditional label instruction'
    return None


def judge_request(case, prompt, config):
    return {'kind': 'judge', 'model': config['model'], 'prompt': prompt,
            'user_text': f"Instruction: {case['instruction']}\nThe first image is SOURCE; the second is EDITED.",
            'images': [{'path': case[f'{k}_local_image'], 'sha256': case[f'{k}_image_sha256']}
                       for k in ('source', 'edited')],
            'temperature': config['temperature'], 'reasoning_effort': 'none',
            'max_completion_tokens': config['judge_max_tokens']}


def messages(request):
    if request['kind'] == 'reflect':
        return request['messages']
    return [{'role': 'system', 'content': request['prompt']},
            {'role': 'user', 'content': [{'type': 'text', 'text': request['user_text']},
             *[openai_compat.image_part(row['path']) for row in request['images']]]}]


class CallStore:
    """One process owns cost reservations, full response logs, and all checkpoints."""
    def __init__(self, out, config, client=None):
        self.out, self.config = out, config
        self.lock = threading.Lock()
        self.rows, self.reserved = {}, 0.0
        self.history = out / 'llm-histories.log'
        if self.history.exists():
            for line in self.history.read_text().splitlines():
                row = json.loads(line)
                if 'response' in row:
                    if row['id'] in self.rows:
                        raise ValueError('Duplicate completed call identity')
                    self.rows[row['id']] = row
        self.spent = sum(r['cost_usd'] for r in self.rows.values())
        self.client = client

    def connect(self):
        if self.client is None:
            creds = load_creds(model=self.config['model'])
            if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
                raise ValueError('Pilot requires the official OpenAI endpoint')
            self.client = OpenAI(api_key=creds.token, timeout=120, max_retries=0)

    def reservation(self, req):
        # UTF-8 bytes upper-bound text tokens; image allowance deliberately conservative.
        n = len(json.dumps(req, ensure_ascii=False).encode()) + 16384 * len(req.get('images', []))
        return (n * self.config['input_price'] + req['max_completion_tokens'] * self.config['output_price']) / 1e6

    def call(self, identity, req):
        amount = self.reservation(req)
        with self.lock:
            if identity in self.rows:
                row = self.rows[identity]
                if row['request'] != req:
                    raise ValueError('Checkpoint request mismatch')
                return row
            if self.spent + self.reserved + amount > self.config['budget_usd']:
                raise RuntimeError('Estimated cost cap reached; run is incomplete')
            self.reserved += amount
        try:
            self.connect()
            for attempt in range(4):
                try:
                    response = self.client.chat.completions.create(
                        model=req['model'], messages=messages(req),
                        temperature=req['temperature'], reasoning_effort=req['reasoning_effort'],
                        max_completion_tokens=req['max_completion_tokens'])
                    break
                except (APIConnectionError, APITimeoutError, APIStatusError) as exc:
                    retryable = not isinstance(exc, APIStatusError) or exc.status_code in (408,409,429,500,502,503,504)
                    with self.lock:
                        with self.history.open('a') as f:
                            f.write(json.dumps({'id': identity, 'attempt': attempt,
                                                'transport_error': type(exc).__name__}) + '\n')
                    if not retryable or attempt == 3:
                        raise
                    time.sleep(min(2 ** attempt, 8))
            raw = response.choices[0].message.content or ''
            usage = response.usage
            cost = (usage.prompt_tokens * self.config['input_price'] +
                    usage.completion_tokens * self.config['output_price']) / 1e6
            row = {'id': identity, 'request': req, 'response': response.model_dump(mode='json'),
                   'raw': raw, 'parsed': parse(raw, response.choices[0].finish_reason),
                   'cost_usd': cost, 'time': datetime.now(timezone.utc).isoformat()}
            with self.lock:
                with self.history.open('a') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                self.rows[identity] = row
                self.spent += cost
            return row
        finally:
            with self.lock:
                self.reserved -= amount


class Pilot:
    def __init__(self, out, config, cases, store):
        self.out, self.config, self.cases, self.store = out, config, cases, store

    def log(self, text):
        line = f'{datetime.now(timezone.utc).isoformat()} {text}'
        print(line, flush=True)
        with (self.out / 'run.log').open('a') as f:
            f.write(line + '\n')

    def evaluate(self, case, arm, rnd, stage, prompt, repeats):
        req = judge_request(case, prompt, self.config)
        prefix = f"{case['case_id']}/{arm}/{rnd}/{stage}/{digest(prompt)}"
        def draw(n):
            return self.store.call(f'{prefix}/{n:03}', req)['parsed']
        with ThreadPoolExecutor(max_workers=self.config['concurrency']) as pool:
            draws = list(pool.map(draw, range(repeats)))
        return aggregate(draws, case['target_label'])

    def propose(self, case, arm, rnd, prompt, coaching=None):
        folder = self.out / 'search' / case['case_id'] / arm / f'{rnd:02}'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'proposal.json'
        request = {'mode': 'repeated_rpc', 'prompt': prompt, 'case_id': case['case_id'],
                   'instruction': case['instruction'], 'seed': self.config['seed'] + rnd}
        if coaching is not None:
            request['coaching'] = coaching
        if path.exists():
            value = json.loads(path.read_text())
            if value['request'] != request:
                raise ValueError('Proposal checkpoint mismatch')
            return value['result']
        repeats = 1 if arm == 'single' else self.config['search_repeats']
        with (folder / 'worker.log').open('w') as log:
            proc = subprocess.Popen([self.config['gepa_python'], str(WORKER)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
            try:
                proc.stdin.write(json.dumps(request) + '\n'); proc.stdin.flush()
                for line in proc.stdout:
                    event = json.loads(line)
                    if event.get('error'):
                        raise RuntimeError(event['error'])
                    kind = event.get('event')
                    if kind == 'done':
                        proc.wait(timeout=10)
                        save(path, {'request': request, 'result': event})
                        return event
                    stage = f"gepa-{event['index']}-{kind}"
                    if kind == 'evaluate':
                        result = self.evaluate(case, arm, rnd, stage, event['prompt'], repeats)
                    elif kind == 'reflect':
                        req = {'kind': 'reflect', 'model': self.config['model'],
                               'messages': event['messages'], 'temperature': 0.0,
                               'reasoning_effort': 'none',
                               'max_completion_tokens': self.config['reflection_max_tokens']}
                        identity = f"{case['case_id']}/{arm}/{rnd}/{stage}/{digest(prompt)}/000"
                        row = self.store.call(identity, req)
                        if row['response']['choices'][0]['finish_reason'] != 'stop':
                            raise RuntimeError('Reflection completion truncated; no prompt adopted')
                        result = row['raw']
                    else:
                        raise RuntimeError(f'Unexpected worker event {kind}')
                    proc.stdin.write(json.dumps({'result': result}) + '\n'); proc.stdin.flush()
                raise RuntimeError(f'Worker exited without a result; see {folder}')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)

    def search(self):
        frozen_path = self.out / 'frozen_prompts.json'
        if frozen_path.exists():
            manifest = json.loads((self.out / 'frozen_manifest.json').read_text())
            if digest(frozen_path.read_bytes()) != manifest['sha256']:
                raise ValueError('Frozen prompts changed')
            return json.loads(frozen_path.read_text())
        frozen = {}
        jobs = [(c, arm) for c in self.cases for arm in ('single', 'repeated')]
        random.Random(self.config['seed']).shuffle(jobs)
        for case, arm in jobs:
            cid = case['case_id']
            prompt = case['prompt']
            for rnd in range(1, self.config['rounds'] + 1):
                folder = self.out / 'search' / cid / arm / f'{rnd:02}'
                decision_path = folder / 'decision.json'
                if decision_path.exists():
                    decision = json.loads(decision_path.read_text())
                    if decision['parent_sha256'] != digest(prompt):
                        raise ValueError('Broken prompt lineage')
                    prompt = decision['selected_prompt']
                    continue
                proposal = self.propose(case, arm, rnd, prompt)
                candidate = proposal['prompt']
                issue = candidate_issue(candidate, case)
                parent, child = proposal['parent_evaluation'], proposal['candidate_evaluation']
                screening = bool(parent and child and improves(parent, child))
                accepted = screening and not issue and candidate != prompt
                confirmation = None
                if accepted and arm == 'repeated':
                    old = self.evaluate(case, arm, rnd, 'confirm-parent', prompt, self.config['confirmation_repeats'])
                    new = self.evaluate(case, arm, rnd, 'confirm-candidate', candidate, self.config['confirmation_repeats'])
                    confirmation = {'parent': old, 'candidate': new}
                    accepted = improves(old, new)
                decision = {'case_id': cid, 'arm': arm, 'round': rnd,
                            'parent_sha256': digest(prompt), 'candidate_sha256': digest(candidate),
                            'screening_improved': screening, 'candidate_issue': issue,
                            'confirmation': confirmation, 'accepted': accepted,
                            'selected_prompt': candidate if accepted else prompt}
                save(decision_path, decision)
                (folder / 'candidate.txt').write_text(candidate)
                (folder / 'candidate.diff').write_text(''.join(difflib.unified_diff(
                    prompt.splitlines(True), candidate.splitlines(True), fromfile='parent', tofile='candidate')))
                prompt = decision['selected_prompt']
                self.log(f'{cid} {arm} round {rnd}: accepted={accepted}; cost=${self.store.spent:.3f}')
            frozen.setdefault(cid, {'unchanged': case['prompt']})[arm] = prompt
        save(frozen_path, frozen)
        save(self.out / 'frozen_manifest.json', {'sha256': digest(frozen_path.read_bytes()),
                                              'time': datetime.now(timezone.utc).isoformat()})
        return frozen

    def final(self, frozen):
        results = {}
        jobs = [(c, arm) for c in self.cases for arm in ARMS]
        random.Random(self.config['seed'] + 1).shuffle(jobs)
        for case, arm in jobs:
            results.setdefault(case['case_id'], {})[arm] = self.evaluate(
                case, arm, 0, 'final', frozen[case['case_id']][arm], self.config['final_repeats'])
            self.log(f"Final {case['case_id']} {arm}: {results[case['case_id']][arm]['accuracy']:.3f}")
        save(self.out / 'final_results.json', results)
        return results


def metrics(cases, results, arm):
    per_case, confusion = [], {label: [] for label in LABELS}
    for c in cases:
        row = results[c['case_id']][arm]
        draws = row['draws']; n = len(draws)
        counts = Counter(d['label'] if d['valid'] else 'invalid' for d in draws)
        accuracy = sum(correct(d,c['target_label']) for d in draws) / n
        disagreement = 1 - sum(v*(v-1) for v in counts.values()) / (n*(n-1)) if n > 1 else None
        per_case.append({'case_id': c['case_id'], 'accuracy': accuracy, 'counts': dict(counts),
                         'disagreement': disagreement, 'invalid': sum(not d['valid'] for d in draws),
                         'stable_wrong': len(counts)==1 and accuracy==0,
                         'all_correct': accuracy==1})
        confusion[c['target_label']].append(accuracy)
    return {'accuracy': float(np.mean([c['accuracy'] for c in per_case])),
            'disagreement': float(np.mean([c['disagreement'] for c in per_case])),
            'stable_wrong_cases': sum(c['stable_wrong'] for c in per_case),
            'all_correct_cases': sum(c['all_correct'] for c in per_case),
            'invalid': sum(c['invalid'] for c in per_case),
            'class_recall': {k: float(np.mean(v)) if v else None for k,v in confusion.items()},
            'per_case': per_case}


def report(out, cases, config):
    results = json.loads((out / 'final_results.json').read_text())
    summary = {arm: metrics(cases, results, arm) for arm in ARMS}
    rng = np.random.default_rng(config['seed'])
    indices = rng.integers(0, len(cases), (10000, len(cases)))
    comparisons = {}
    for base in ('unchanged', 'single'):
        delta = np.array([v['accuracy'] for v in summary['repeated']['per_case']]) - np.array(
            [v['accuracy'] for v in summary[base]['per_case']])
        comparisons[f'repeated_minus_{base}'] = {'difference': float(delta.mean()),
            'case_bootstrap_95_ci': np.quantile(delta[indices].mean(axis=1), [.025,.975]).tolist()}
    usage = {a: {'calls':0,'input_tokens':0,'output_tokens':0,'cost_usd':0.,'accepted_edits':0} for a in ARMS}
    ids = set()
    for line in (out / 'llm-histories.log').read_text().splitlines():
        row = json.loads(line)
        if 'response' not in row: continue
        if row['id'] in ids: raise ValueError('Duplicate response')
        ids.add(row['id'])
        arm = row['id'].split('/')[1]
        u = usage[arm]; tokens = row['response']['usage']
        u['calls'] += 1; u['input_tokens'] += tokens['prompt_tokens']; u['output_tokens'] += tokens['completion_tokens']
        u['cost_usd'] += row['cost_usd']
    for path in (out / 'search').glob('*/*/*/decision.json'):
        row = json.loads(path.read_text()); usage[row['arm']]['accepted_edits'] += row['accepted']
    final_ids = [i for i in ids if '/0/final/' in i]
    expected = len(cases)*len(ARMS)*config['final_repeats']
    if len(final_ids) != expected: raise ValueError('Final evaluation is incomplete')
    value = {'metrics':summary, 'comparisons':comparisons,'usage':usage,
             'completed_calls':len(ids),'final_calls':len(final_ids)}
    save(out / 'summary.json', value)
    lines = ['# Ten-case repeated-evaluation GEPA pilot', '',
             'Per-case repair; fresh repetitions of known cases. No claim of unseen-task generalization or equal-cost superiority.', '',
             '| Arm | Accuracy | Disagreement | Stable wrong cases | All draws correct | Accepted edits | Calls | Cost |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in ARMS:
        m,u=summary[a],usage[a]
        lines.append(f"| {a} | {m['accuracy']:.1%} | {m['disagreement']:.1%} | {m['stable_wrong_cases']} | {m['all_correct_cases']} | {u['accepted_edits']} | {u['calls']} | ${u['cost_usd']:.3f} |")
    lines += ['', '## Paired case-bootstrap differences', '']
    for name,v in comparisons.items():
        lo,hi=v['case_bootstrap_95_ci']
        lines.append(f"- {name}: {100*v['difference']:+.1f} percentage points; descriptive 95% interval [{100*lo:+.1f}, {100*hi:+.1f}].")
    lines += ['', '## Per-case final accuracy', '', '| Case | Human | Unchanged | Single | Repeated |', '|---|---|---:|---:|---:|']
    for c in cases:
        rates=[results[c['case_id']][a]['accuracy'] for a in ARMS]
        lines.append(f"| {c['case_id']} | {c['target_label']} | " + ' | '.join(f'{r:.1%}' for r in rates) + ' |')
    lines += ['', '## Interpretation limits', '',
              '- Ten previously selected cases and one search trajectory per method; intervals are descriptive.',
              '- Both repair arms get five proposals; repeated repair spends more evaluation calls.',
              '- Final outcomes never feed back into prompt selection. Stable outputs can still be wrong.',
              '- Human targets are treated as fixed benchmark labels; no independent concept annotations.',
              '- Full draws, prompts, feedback, and decisions are saved. Costs use configured list rates and omit cache discounts.']
    (out / 'report.md').write_text('\n'.join(lines)+'\n')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true'); p.add_argument('--live', action='store_true')
    p.add_argument('--resume', action='store_true'); p.add_argument('--report', action='store_true')
    p.add_argument('--model', default='gpt-5.4-mini')
    p.add_argument('--gepa-python', type=Path, default=ROOT/'.venv-gepa/bin/python')
    p.add_argument('--rounds', type=int, default=5); p.add_argument('--search-repeats',type=int,default=5)
    p.add_argument('--confirmation-repeats',type=int,default=10); p.add_argument('--final-repeats',type=int,default=30)
    p.add_argument('--temperature',type=float,default=.3); p.add_argument('--judge-max-tokens',type=int,default=512)
    p.add_argument('--reflection-max-tokens',type=int,default=4096)
    p.add_argument('--seed',type=int,default=44); p.add_argument('--concurrency',type=int,default=8)
    p.add_argument('--budget-usd',type=float,default=15); p.add_argument('--input-price',type=float,default=.75)
    p.add_argument('--output-price',type=float,default=4.5)
    args=p.parse_args()
    if min(args.rounds,args.search_repeats,args.confirmation_repeats,args.concurrency) < 1 or args.final_repeats < 2:
        p.error('Counts must be positive and final-repeats at least two')
    out=args.output_dir.resolve(); cases=load_cases()
    if args.report:
        report(out,cases,json.loads((out/'run_config.json').read_text())); return
    # Preserve the venv interpreter symlink: resolving it loses its environment.
    config={k:str(v.absolute()) if isinstance(v,Path) else v for k,v in vars(args).items()
            if k not in ('dry_run','live','resume','report','output_dir')}
    config.update(source_sha256=digest(SOURCE.read_bytes()),worker_sha256=digest(WORKER.read_bytes()),
                  runner_sha256=digest(Path(__file__).read_bytes()),gepa_version='0.1.4')
    out.mkdir(parents=True,exist_ok=True)
    config_path=out/'run_config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != config: raise ValueError('Frozen configuration changed')
        if not args.resume and not args.dry_run: p.error('Existing run requires --resume')
    else:
        save(config_path,config); save(out/'cases.json',cases)
    # One-step GEPA performs at most four evaluation batches and one reflection.
    max_judges=10*args.rounds*(4+4*args.search_repeats+2*args.confirmation_repeats)+30*args.final_repeats
    reflections=20*args.rounds
    estimate={'max_judge_calls':max_judges,'max_reflection_calls':reflections,
              'final_calls':30*args.final_repeats,
              'planning_cost_usd':(max_judges*(1800*args.input_price+args.judge_max_tokens*args.output_price)+
                                   reflections*(7000*args.input_price+args.reflection_max_tokens*args.output_price))/1e6,
              'note':'Planning estimate assumes 1800 judge input tokens and 7000 reflection input tokens; runtime reserves conservatively per call.'}
    save(out/'estimate.json',estimate)
    if args.dry_run: print(json.dumps(estimate,indent=2)); return
    require_live(args.live,context='Repeated-evaluation GEPA pilot')
    store=CallStore(out,config); store.connect()
    pilot=Pilot(out,config,cases,store)
    frozen=pilot.search(); pilot.final(frozen)
    summary=report(out,cases,config)
    pilot.log(f"Complete: {summary['completed_calls']} calls, ${store.spent:.3f}")


if __name__=='__main__':
    main()
