"""Bounded 50-case observation study; retained checker, no label-driven repairs.

One durable record per compiler/check invocation, including failed/interrupted
attempts. Network failures do not erase partial case results or trigger retries.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from critical.core.optimization.prompt.calitree.decomposition import FrozenCriteria, FrozenCriteriaExecutor
from critical.lm_engine import get_engine, load_creds, require_live
from critical.logging.llm_history import LLMHistoryWriter
from run.calitree_observation_reliability import label_from_statuses
from tests.unit.calitree.assumption3_probe import BASELINE, FITTED, ROOT, BudgetedEngine, BudgetExhausted, ProviderUnavailable, load_inputs, save, digest
from tests.unit.calitree.casewise_fitting import PLAN_SCHEMA, TEMPLATES, validate_plan

MODEL = 'gpt-6-luna'
NEW_SOURCE = ROOT / '.cache/calitree-tests/vision-fresh64-gpt41-20260926/fresh_validation/results.json'
NEW_IDS = ['N01','N04','N14','N16','N20','N24','N25','N31','N35','N38','N42','N43','N46','N48','N50','N54','N57','N59','N64']
MAX_CALLS = 465
COMPLETION_BUDGET = 495616


def cohort():
    rows = load_inputs(BASELINE, FITTED, [f'J{i:02}' for i in range(1,33) if i != 16])
    old = json.loads((BASELINE / 'results.json').read_text())['manifest']['cases']
    for case, row in rows.items():
        row['task'] = old[case]['task']
        row['plan_origin'] = 'historical_frozen'
    source = json.loads(NEW_SOURCE.read_text())['manifest']['cases']
    for case in NEW_IDS:
        r = source[case]
        assert hashlib.sha256(r['optimized'].encode()).hexdigest() == r['optimized_prompt_sha256']
        rows[case] = {'instruction': r['instruction'], 'optimized_prompt': r['optimized'],
                      'human_label': r['target_label'], 'task': r['task'], 'feedback_used': False,
                      'criteria_origin': 'luna_initial_compilation', 'plan_origin': 'new_luna', 'plan': None,
                      'images': [{'path': str((ROOT / r[role+'_image']).resolve()), 'sha256': r[role+'_image_sha256']}
                                 for role in ('source','edited')]}
    identities = []
    for row in rows.values():
        if row.get('annotation_review', {}).get('status') == 'uncertain':
            raise ValueError('Reviewed uncertain case in cohort')
        for item in row['images']:
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Image bytes changed')
        identities.append(tuple(i['sha256'] for i in row['images']))
    if len(rows) != 50 or len(set(identities)) != 50:
        raise ValueError('Expected 50 unique eligible image pairs')
    return rows


def freeze(out, rows):
    sources = [Path(__file__), ROOT/'run/calitree_observation_reliability.py',
               ROOT/'critical/lm_engine/provider_api.py', ROOT/'tests/unit/calitree/assumption3_probe.py']
    sources += list((ROOT/'critical/core/optimization/prompt/calitree/decomposition').glob('*.py'))
    manifest = {'version': 'calitree-observation50-v1', 'model': MODEL, 'temperature': 0,
                'reasoning_effort': 'none', 'repeats': 2, 'max_calls': MAX_CALLS,
                'completion_budget': COMPLETION_BUDGET, 'compile_max_tokens': 2048, 'check_max_tokens': 1024,
                'max_conditions_per_new_plan': 8, 'schema_retries': 0, 'http_attempts_per_call': 1,
                'compiler_template': (TEMPLATES/'decompose.txt').read_text(), 'compiler_schema': PLAN_SCHEMA,
                'checker_templates': {p.name:p.read_text() for p in (ROOT/'critical/core/prompts/templates/calitree_decomposition_casewise_v1').glob('*.txt')},
                'source_sha256': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                'rows': rows}
    out.mkdir(parents=True, exist_ok=True)
    path = out/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Protocol changed; use a new directory')
    save(path, manifest)
    return manifest


def compile_once(engine, row, template):
    payload = {'instruction': row['instruction'], 'optimized_prompt': row['optimized_prompt']}
    response = engine.generate(template+'\nINPUT_JSON: '+json.dumps(payload), media_inputs=[], schema=PLAN_SCHEMA, strict_schema=True)
    record = {'input': payload, 'response': response, 'outcome': 'invalid'}
    try:
        if response.get('finishReason') not in (None,'stop'):
            raise ValueError('Non-stop compiler finish')
        record['plan'] = validate_plan(response.get('parsed'))
        record['outcome'] = 'completed'
    except ValueError as exc:
        record['error'] = str(exc)
    return record


def check_once(engine, row, condition):
    # One-condition binding changes only local artifact identity, not the prompt.
    plan = {'conditions': [deepcopy(condition)], 'rubric_conflicts': []}
    bound = FrozenCriteria.bind(row['optimized_prompt'], row['instruction'], plan,
                                feedback_used=row['feedback_used'], origin=row['criteria_origin'])
    executor = FrozenCriteriaExecutor(engine, schema_retries=0)
    record = {'outcome': 'invalid', 'full_plan_sha256': digest(row['plan'])}
    try:
        observations = executor.observe(bound, prompt=row['optimized_prompt'], instruction=row['instruction'],
                                        evidence=dict(zip(('source_image','edited_image'),[i['path'] for i in row['images']])))
        if executor.calls[0]['response'].get('finishReason') not in (None,'stop'):
            raise ValueError('Non-stop checker finish')
        record.update(outcome='completed', check=observations['checks'][0])
    except ValueError as exc:
        record['error'] = str(exc)
    except ProviderUnavailable as exc:
        record.update(outcome='transport_error', error=str(exc))
    finally:
        record['calls'] = executor.calls
    return record


def summary(rows, records):
    cases, conditions = {}, []
    for case, row in rows.items():
        statuses = [[],[]]
        for c in (row.get('plan') or {}).get('conditions',[]):
            pair=[]
            for rep in range(2):
                r=records.get(f'check/{rep}/{case}/{c["id"]}',{})
                s=r.get('check',{}).get('status') if r.get('outcome')=='completed' else r.get('outcome','not_run')
                pair.append(s);statuses[rep].append(s)
            conditions.append({'case':case,'id':c['id'],'statuses':pair,
                               'consistent':pair[0]==pair[1] and pair[0] in {'complete','partial','absent','unknown'},
                               'consistent_known':pair[0]==pair[1] and pair[0] in {'complete','partial','absent'}})
        predictions=[label_from_statuses(s) for s in statuses]
        cases[case]={'task':row['task'],'instruction':row['instruction'],'plan_origin':row['plan_origin'],
                     'feedback_used':row['feedback_used'],'provisional_label':row['human_label'],
                     'predictions':predictions,'agreement':sum(p==row['human_label'] for p in predictions),
                     'plan_available':row.get('plan') is not None}
    return {'cases':cases,'conditions':conditions,'consistent_conditions':sum(c['consistent'] for c in conditions),
            'consistent_known_conditions':sum(c['consistent_known'] for c in conditions),'total_conditions':len(conditions),
            'outcomes':dict(Counter(r['outcome'] for r in records.values()))}


def execute(out, manifest, engine_factory):
    rows=deepcopy(manifest['rows']);records={}
    for p in (out/'jobs').glob('*.json'):
        r=json.loads(p.read_text());records[r['job_id']]=r
    (out/'jobs').mkdir(exist_ok=True)
    consecutive_errors=0
    stop_reason='complete'
    last_budget=None
    def invoke(job_id, fn):
        nonlocal consecutive_errors
        if job_id in records:
            return records[job_id]
        path=out/'jobs'/(hashlib.sha256(job_id.encode()).hexdigest()+'.json')
        records[job_id]={'job_id':job_id,'outcome':'interrupted_or_pending'}
        save(path,records[job_id])
        try:
            value=fn()
        except ProviderUnavailable as exc:
            value={'outcome':'transport_error','error':str(exc)}
        except BudgetExhausted:
            records[job_id]={'job_id':job_id,'outcome':'budget_exhausted'};save(path,records[job_id]);raise
        value['job_id']=job_id;records[job_id]=value;save(path,value)
        consecutive_errors=consecutive_errors+1 if value['outcome']=='transport_error' else 0
        message=json.dumps({'job':job_id,'outcome':value['outcome'],'usage':last_budget.usage})
        print(message,flush=True)
        with (out/'run.log').open('a') as f:f.write(message+'\n')
        if consecutive_errors>=3:
            raise RuntimeError('Three consecutive transport failures; no further calls')
        return value
    try:
        compiler=BudgetedEngine(engine_factory(2048),out/'budget.json',MAX_CALLS,COMPLETION_BUDGET);last_budget=compiler
        for case,row in rows.items():
            if row['plan'] is None:
                record=invoke('compile/'+case,lambda row=row:compile_once(compiler,row,manifest['compiler_template']))
                if record['outcome']=='completed':row['plan']=record['plan']
        save(out/'frozen_plans.json',rows)
        checks=BudgetedEngine(engine_factory(1024),out/'budget.json',MAX_CALLS,COMPLETION_BUDGET);last_budget=checks
        for rep in range(2):
            for case,row in rows.items():
                for condition in (row.get('plan') or {}).get('conditions',[]):
                    invoke(f'check/{rep}/{case}/{condition["id"]}',lambda row=row,c=condition:check_once(checks,row,c))
            save(out/'progress.json',summary(rows,records))
    except (RuntimeError,BudgetExhausted) as exc:
        stop_reason=str(exc)
    result={'stop_reason':stop_reason,'usage':last_budget.usage if last_budget else {},'summary':summary(rows,records)}
    save(out/'results.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--live',action='store_true')
    args=parser.parse_args();rows=cohort();manifest=freeze(args.output_dir,rows)
    print(json.dumps({'cases':len(rows),'new_compilations':19,'max_calls':MAX_CALLS,'completion_budget':COMPLETION_BUDGET}),flush=True)
    if not args.live:return
    require_live(args.live,context='50-case user-requested observation expansion')
    creds=load_creds(model=MODEL)
    if creds.provider!='openai' or creds.endpoints!=['https://api.openai.com/v1']:raise ValueError('Official OpenAI only')
    def factory(tokens):
        return get_engine('gpt',model=MODEL,creds=creds,temperature=0,max_tokens=tokens,timeout=60,
                          history=LLMHistoryWriter(args.output_dir/'llm-histories.log'))
    result=execute(args.output_dir,manifest,factory)
    print(json.dumps({k:v for k,v in result.items() if k!='summary'}),flush=True)


if __name__=='__main__':main()
