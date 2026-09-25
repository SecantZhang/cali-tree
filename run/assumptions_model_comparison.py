"""Live, checkpointed model comparison on the frozen ten-case assumption pilot.

No live calls without --live. Run --dry-run first to freeze the protocol. No labels
or historical outcomes enter model requests. Full prompts, outputs, usage and image
hashes are logged; malformed generations are outcomes, never selectively retried.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import threading
import time

import numpy as np
from openai import OpenAI
from run.assumptions_pilot import distribution, features, fit_trees, save
from run.aurora_prompt_tree import (DECOMPOSER_SYSTEM, PRESERVATION_LEAF,
    aggregate_tree, combine_requirement_leaves, compile_requirement_leaf,
    compile_fidelity_leaf, parse_requirements)
from vejudge.experiments.aurora_prompt_repair import parse_judgment
from vejudge.lm_engine import load_creds, openai_compat
from vejudge.lm_engine.gate import require_live

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'logs/exps/260923-20:00:01-exps/selected_records.json'
MODELS = {'mini': 'gpt-5.4-mini', 'luna': 'gpt-6-luna'}
# USD/million, standard list rates, deliberately ignore cache discounts.
PRICES = {'gpt-5.4-mini': [0.75, 4.5], 'gpt-6-luna': [0.1, 0.5]}
LABELS = ['no', 'partial', 'yes']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def request_settings(model, effort, decomposition=False):
    result = {'model': model, 'reasoning_effort': effort,
              'max_completion_tokens': 4096 if effort != 'none' else (1024 if decomposition else 512)}
    if effort == 'none':
        result['temperature'] = 0.0 if decomposition else 0.3
    return result


def make_job(case, model, family, repeat, prompt, effort='none', leaf='direct', decomposition=False):
    return {'id': f"{model}/{family}/{case['case_id']}/{repeat:02d}/{leaf}",
            'case_id': case['case_id'], 'model': model, 'family': family,
            'repeat': repeat, 'leaf': leaf, 'prompt': prompt,
            'instruction': case['instruction'], 'decomposition': decomposition,
            'settings': request_settings(MODELS[model], effort, decomposition),
            'images': [] if decomposition else [
                {'path': case['source_local_image'], 'sha256': case['source_image_sha256']},
                {'path': case['edited_local_image'], 'sha256': case['edited_image_sha256']}],
            'user_text': case['instruction'] if decomposition else
                f"Instruction: {case['instruction']}\nThe first image is SOURCE; the second is EDITED."}


@lru_cache(maxsize=32)
def media(path):
    return openai_compat.image_part(path)


def request_messages(job):
    content = job['user_text'] if job['decomposition'] else [
        {'type': 'text', 'text': job['user_text']},
        *[media(row['path']) for row in job['images']]]
    return [{'role': 'system', 'content': job['prompt']}, {'role': 'user', 'content': content}]


class Runner:
    def __init__(self, out, concurrency=16, budget=15.0):
        self.out, self.concurrency, self.budget = out, concurrency, budget
        self.lock = threading.Lock()
        self.rows = {}
        self.history = out / 'llm-histories.log'
        if self.history.exists():
            for line in self.history.read_text().splitlines():
                row = json.loads(line)
                if not row.get('transport_error'):
                    self.rows[row['id']] = row
        self.spent = sum(row.get('estimated_list_cost_usd', 0) for row in self.rows.values())
        self.clients = {}
        for alias, model in MODELS.items():
            creds = load_creds(model=model)
            if creds.provider != 'openai' or creds.endpoints != ['https://api.openai.com/v1']:
                raise ValueError('This comparison requires the official OpenAI API for both models')
            self.clients[alias] = OpenAI(api_key=creds.token, base_url=creds.endpoints[0], timeout=120, max_retries=2)

    def log(self, message):
        line = f'{stamp()} {message}'
        print(line, flush=True)
        with (self.out / 'run.log').open('a') as f:
            f.write(line + '\n')

    def call(self, job):
        if job['id'] in self.rows:
            old = self.rows[job['id']]
            assert old['request'] == job, 'Checkpoint request changed'
            return old
        with self.lock:
            if self.spent >= self.budget:
                raise RuntimeError('Estimated list-price budget reached; no new calls scheduled')
        start = time.monotonic()
        row = {'id': job['id'], 'request': job, 'started_at': stamp()}
        try:
            result = self.clients[job['model']].chat.completions.create(
                messages=request_messages(job), **job['settings'])
            raw = result.choices[0].message.content or ''
            row.update(response=result.model_dump(mode='json'), raw_content=raw,
                       latency_seconds=time.monotonic()-start, transport_error=None)
            if job['decomposition']:
                try:
                    row['parsed'] = {'valid': True, 'requirements': parse_requirements(raw, job['instruction'])}
                except (ValueError, TypeError, KeyError) as exc:
                    row['parsed'] = {'valid': False, 'error': str(exc), 'requirements': []}
            else:
                row['parsed'] = parse_judgment(raw)
                if result.choices[0].finish_reason != 'stop':
                    row['parsed']['valid'] = False
                    row['parsed']['finish_error'] = result.choices[0].finish_reason
            usage = result.usage
            inp, output = PRICES[job['settings']['model']]
            row['estimated_list_cost_usd'] = (usage.prompt_tokens*inp + usage.completion_tokens*output)/1e6
        except Exception as exc:
            # SDK errors expose provider messages, never headers or credentials.
            row.update(transport_error=f'{type(exc).__name__}: {str(exc)[:1000]}',
                       latency_seconds=time.monotonic()-start, parsed={'valid':False})
        with self.lock:
            with self.history.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            self.spent += row.get('estimated_list_cost_usd', 0)
            if not row.get('transport_error'):
                self.rows[job['id']] = row
        if row.get('transport_error'):
            raise RuntimeError(row['transport_error'])
        return row

    def run(self, jobs, name):
        pending = [j for j in jobs if j['id'] not in self.rows]
        random.Random(44).shuffle(pending)
        self.log(f'{name}: {len(jobs)} planned, {len(pending)} pending')
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = {pool.submit(self.call, j): j for j in pending}
            for n, future in enumerate(as_completed(futures), 1):
                try:
                    future.result()
                except Exception:
                    for f in futures:
                        f.cancel()
                    raise
                if n % 25 == 0 or n == len(pending):
                    self.log(f'{name}: {n}/{len(pending)} completed; cumulative list estimate ${self.spent:.3f}')
        return [self.rows[j['id']] for j in jobs]


def base_jobs(bundles):
    jobs = []
    for b in bundles:
        c = b['case']
        for model in MODELS:
            for rep in range(10):
                jobs.append(make_job(c, model, 'direct', rep, b['ablation']['original']['prompt']))
                if model == 'luna':
                    jobs.append(make_job(c, model, 'direct_medium', rep, b['ablation']['original']['prompt'], effort='medium'))
                jobs.append(make_job(c, model, 'preservation', rep, PRESERVATION_LEAF, leaf='preservation'))
                jobs.extend(requirement_jobs(c, model, 'fixed', rep, b['tree']['decomposition']['requirements']))
        # Freeze the first validly formatted draw; do not select against labels.
        jobs.append(make_job(c, 'luna', 'decomposition', 0, DECOMPOSER_SYSTEM,
                             effort='medium', decomposition=True, leaf='plan'))
    return jobs


def requirement_jobs(case, model, family, rep, requirements):
    result = []
    for q in requirements:
        result += [make_job(case, model, family, rep, compile_requirement_leaf(q), leaf=q['id']+'/presence'),
                   make_job(case, model, family, rep, compile_fidelity_leaf(q), leaf=q['id']+'/fidelity')]
    return result


def metrics(cases, predictions):
    per_case = []
    confusion = [[0]*4 for _ in LABELS]
    for c, repeats in zip(cases, predictions):
        labels = [r.get('label') if r.get('valid') else 'invalid' for r in repeats]
        d = distribution(labels)
        d.update(case_id=c['case_id'], target=c['target_label'],
                 correct=sum(v == c['target_label'] for v in labels),
                 invalid=labels.count('invalid'))
        per_case.append(d)
        for label in labels:
            confusion[LABELS.index(c['target_label'])][LABELS.index(label) if label in LABELS else 3] += 1
    return {'accuracy':sum(r['correct'] for r in per_case)/100,
            'modal_correct_cases':sum(r['mode']==r['target'] for r in per_case),
            'modal_ties':sum(r['mode']=='tie' for r in per_case),
            'stable_cases':sum(r['stable'] and not r['invalid'] for r in per_case),
            'all_ten_correct_cases':sum(r['correct']==10 for r in per_case),
            'invalid':sum(r['invalid'] for r in per_case),
            'mean_pairwise_disagreement':float(np.mean([r['pairwise_disagreement'] for r in per_case])),
            'confusion_rows_no_partial_yes_columns_no_partial_yes_invalid':confusion,
            'recall':{label:confusion[i][i]/sum(confusion[i]) for i,label in enumerate(LABELS)},
            'cases':per_case}


def paired_interval(a, b):
    diffs = np.array([(y['correct']-x['correct'])/10 for x,y in zip(a['cases'],b['cases'])])
    rng = np.random.default_rng(44)
    boot = diffs[rng.integers(0,10,size=(10000,10))].mean(axis=1)
    return {'difference':float(diffs.mean()), 'task_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist()}


def summarize(out, bundles, rows, plans):
    cases = [b['case'] for b in bundles]
    arms = {}
    for model in MODELS:
        for family in ['direct'] + (['direct_medium'] if model=='luna' else []):
            arms[model+'_'+family] = [[rows[make_job(c, model, family, rep, '', effort='medium' if family.endswith('medium') else 'none')['id']]['parsed'] for rep in range(10)] for c in cases]
        for family in ['fixed','regenerated']:
            predictions, feature_rows = [], []
            all_valid = True
            leaf_groups = []
            for b in bundles:
                c = b['case']
                req = b['tree']['decomposition']['requirements'] if family=='fixed' else plans[c['case_id']]['requirements']
                reps = []
                for rep in range(10):
                    leaves = []
                    for q in req:
                        presence = rows[f"{model}/{family}/{c['case_id']}/{rep:02d}/{q['id']}/presence"]['parsed']
                        fidelity = rows[f"{model}/{family}/{c['case_id']}/{rep:02d}/{q['id']}/fidelity"]['parsed']
                        leaves.append(combine_requirement_leaves(q,presence,fidelity))
                    preservation = rows[f"{model}/preservation/{c['case_id']}/{rep:02d}/preservation"]['parsed']
                    prediction = {**aggregate_tree(req,leaves,preservation),'requirements':leaves,'preservation':preservation}
                    reps.append(prediction)
                    all_valid &= prediction['valid']
                    if prediction['valid']:
                        feature_rows.append(features({'decomposition':{'requirements':req}},prediction))
                predictions.append(reps)
                for idx,q in enumerate(req):
                    for kind in ['presence','fidelity']:
                        labels = [r['requirements'][idx][kind].get('label','invalid') for r in reps]
                        leaf_groups.append({'case_id':c['case_id'],'leaf':q['id']+'/'+kind,**distribution(labels)})
                leaf_groups.append({'case_id':c['case_id'],'leaf':'preservation',**distribution([r['preservation'].get('label','invalid') for r in reps])})
            arm = model+'_'+family
            arms[arm] = predictions
            tree_dir = out / arm
            tree_dir.mkdir(exist_ok=True)
            save(tree_dir/'leaf_stability.json',leaf_groups)
            if all_valid:
                fit_trees(cases,feature_rows,tree_dir)
    result = {arm: metrics(cases, preds) for arm,preds in arms.items()}
    comparisons = {}
    for a,b in [('mini_direct','luna_direct'),('luna_direct','luna_direct_medium'),
                ('mini_fixed','luna_fixed'),('mini_regenerated','luna_regenerated'),
                ('luna_fixed','luna_regenerated'),('mini_fixed','mini_regenerated')]:
        comparisons[b+' minus '+a] = paired_interval(result[a],result[b])
    usage = {}
    for alias in MODELS:
        subset = [r for r in rows.values() if r['request']['model']==alias]
        usage[alias] = {'calls':len(subset),'returned_models':dict(Counter(r['response']['model'] for r in subset)),
                       'input_tokens':sum(r['response']['usage']['prompt_tokens'] for r in subset),
                       'output_tokens':sum(r['response']['usage']['completion_tokens'] for r in subset),
                       'estimated_list_cost_usd':sum(r['estimated_list_cost_usd'] for r in subset)}
    save(out/'predictions.json',arms)
    save(out/'summary.json',{'arms':result,'comparisons':comparisons,'usage':usage})
    lines = ['# GPT-6-Luna: ten-case model comparison','',
             'Fresh official OpenAI API calls, ten independent repetitions per case. The primary comparison holds prompts, images, temperature 0.3, reasoning none and aggregation constant. Luna medium reasoning is a separate direct-judge arm with temperature omitted, so it changes both reasoning and sampling configuration.', '',
             'The regenerated plan is the first Luna medium-reasoning decomposition of each instruction using the existing decomposer prompt. No image, human label, historical output, or optimized judge rubric is shown to the decomposer. Both models evaluate that same frozen plan with reasoning none. Preservation measurements are deliberately shared between fixed/regenerated arms within each model and repetition.', '',
             '| Arm | Correct /100 | Correct modes /10 | Stable /10 | All ten correct /10 | Pair disagreement | Invalid |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for arm,m in result.items():
        lines.append(f"| {arm} | {m['accuracy']*100:.0f} | {m['modal_correct_cases']} | {m['stable_cases']} | {m['all_ten_correct_cases']} | {m['mean_pairwise_disagreement']:.1%} | {m['invalid']} |")
    lines += ['', '## Paired accuracy differences', '', 'Intervals resample ten task groups, not 100 repeat records. They are descriptive on this selected diagnostic subset.', '', '| Comparison | Difference | 95% task-bootstrap interval |','|---|---:|---:|']
    for name,d in comparisons.items():
        lo,hi=d['task_bootstrap_95_ci'];lines.append(f"| {name} | {d['difference']*100:+.1f} pp | [{lo*100:+.1f}, {hi*100:+.1f}] pp |")
    lines += ['', '## Per-case correct repetitions', '', '| Case | Human | '+ ' | '.join(result)+' |', '|---|---|'+'---:|'*len(result)]
    for i,c in enumerate(cases):
        lines.append(f"| {c['case_id']} | {c['target_label']} | "+' | '.join(str(m['cases'][i]['correct']) for m in result.values())+' |')
    lines += ['', '## Learned trees', '', 'Frozen depth-2 trees, minimum 20 records/leaf, all ten repetitions of a task kept in the same fold. No hyperparameter selection. See each arm directory for trees, fold memberships, collisions, and leaf stability.', '', '| Arm | Detailed leave-task-out | Detailed leave-category-out | Yes recall, task-out | Unstable atomic checks |','|---|---:|---:|---:|---:|']
    for arm in ['mini_fixed','luna_fixed','mini_regenerated','luna_regenerated']:
        path=out/arm/'learned_trees.json'
        leaves=json.loads((out/arm/'leaf_stability.json').read_text())
        if path.exists():
            m=json.loads(path.read_text())['detailed'];conf=m['leave_task_out']['confusion']
            lines.append(f"| {arm} | {m['leave_task_out']['repeat_accuracy']:.0%} | {m['leave_category_out']['repeat_accuracy']:.0%} | {conf[2][2]/sum(conf[2]):.0%} | {sum(not r['stable'] for r in leaves)}/{len(leaves)} |")
        else:
            lines.append(f'| {arm} | Not fit: invalid leaves | — | — | — |')
    lines += ['', '## Usage', '', 'List-price estimates ignore cache discounts; these are not an invoice.', '', '```json',json.dumps(usage,indent=2),'```', '', '## Limits', '',
        '- Ten selected repair cases are not a probability sample or an untouched validation set. Their optimized prompts were previously selected using focal human labels.',
        '- Final-label accuracy uses benchmark aggregate human scores. No independent human condition annotations exist, so condition correctness is not established by repeatability.',
        '- Existing and regenerated trees decompose the instruction, not the optimized rubric. This tests the existing tree implementation, not a completed compiler of optimized prompts.',
        '- One regenerated plan per case does not establish decomposition stability or isolate decomposer model capability from plan sampling and reasoning configuration.',
        '- Reused preservation draws intentionally pair the two decomposition arms; these arms are not independent.',
        '- More stable output can still be consistently wrong. Report all-ten-correct separately.',
        '- No prompt, rule, case selection, or tree setting was changed in response to experimental outcomes.', '',
        '## Reproduction', '', f'`PYTHONPATH=. .venv/bin/python run/assumptions_model_comparison.py --output-dir {out.relative_to(ROOT)} --live`', '',
        'The runner checkpoints every completed generation, including malformed model output. Resume reuses completed draws; only transport failures can be retried. See run_config.json, plans.json, predictions.json, summary.json, llm-histories.log, and run.log.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--concurrency',type=int,default=16)
    parser.add_argument('--budget-usd',type=float,default=15)
    args=parser.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    bundles=json.loads(SOURCE.read_text())
    assert len(bundles)==10 and len({b['case']['task_uid'] for b in bundles})==10
    for b in bundles:
        for which in ['source','edited']:
            c=b['case'];assert sha(c[which+'_local_image'])==c[which+'_image_sha256']
    jobs=base_jobs(bundles)
    config={'schema_version':1,'source':str(SOURCE),'source_sha256':sha(SOURCE),
            'runner_sha256':sha(__file__),'tree_module_sha256':sha(ROOT/'run/aurora_prompt_tree.py'),
            'analysis_module_sha256':sha(ROOT/'run/assumptions_pilot.py'),
            'models':MODELS,'repeats':10,'concurrency':args.concurrency,
            'budget_usd':args.budget_usd,'list_prices':PRICES,'initial_calls':len(jobs),
            'max_regenerated_calls':1600,'shuffle_seed':44,'bootstrap_seed':44,
            'regeneration':'First Luna medium instruction-only decomposition, both evaluators crossed; shared preservation',
            'primary_settings':request_settings(MODELS['luna'],'none'),
            'reasoning_settings':request_settings(MODELS['luna'],'medium'),
            'selection':'Frozen from prior 10-case pilot; not untouched or probability sampled',
            'no_labels_in_requests':True}
    if (out/'run_config.json').exists():
        assert json.loads((out/'run_config.json').read_text())==config,'Configuration changed; use a new directory'
    else:
        save(out/'run_config.json',config)
        save(out/'initial_requests.json',jobs)
    if args.dry_run:
        print(json.dumps({'initial_calls':len(jobs),'maximum_total_calls':len(jobs)+1600,
                          'budget_usd':args.budget_usd,'network_calls':0,'output_dir':str(out)},indent=2))
        return
    require_live(args.live,context='Ten-case model comparison')
    runner=Runner(out,args.concurrency,args.budget_usd)
    # Billable first draws are retained in the analysis, not discarded smoke draws.
    for model,family in [('mini','direct'),('luna','direct'),('luna','direct_medium')]:
        job=next(j for j in jobs if j['model']==model and j['family']==family)
        row=runner.call(job)
        if not row['parsed']['valid']:
            raise RuntimeError(f'Preflight output invalid for {job["id"]}; inspect history before proceeding')
        runner.log(f'Preflight success: {model}/{family}; returned {row["response"]["model"]}')
    runner.run(jobs,'direct/fixed/decomposition')
    plans={b['case']['case_id']:runner.rows[f"luna/decomposition/{b['case']['case_id']}/00/plan"]['parsed'] for b in bundles}
    save(out/'plans.json',plans)
    if not all(p['valid'] for p in plans.values()):
        raise RuntimeError('Invalid regenerated plan; no whole-instruction fallback is allowed')
    regenerated=[]
    for b in bundles:
        c=b['case']
        for model in MODELS:
            for rep in range(10):
                regenerated.extend(requirement_jobs(c,model,'regenerated',rep,plans[c['case_id']]['requirements']))
    save(out/'regenerated_requests.json',regenerated)
    runner.run(regenerated,'regenerated conditions')
    result=summarize(out,bundles,runner.rows,plans)
    runner.log('Complete: '+json.dumps({k:v['accuracy'] for k,v in result.items()}))


if __name__=='__main__':
    main()
