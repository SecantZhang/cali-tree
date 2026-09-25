"""Focused robust candidate selection against the prior single-draw GEPA baseline.

C08/C05 are development cases. Candidate generation, development batches,
confirmation, and final evaluation use distinct draw identities. --live gates calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random

import numpy as np

from run.robust_prompt_repair_pilot import (
    ROOT, ARMS, CallStore, Pilot, candidate_issue, correct, digest, judge_request,
    load_cases, save,
)
from vejudge.lm_engine.gate import require_live

PRIOR = ROOT / 'logs/exps/260924-09:37:00-exps/frozen_prompts.json'
FOCUS = ('C08', 'C05')
SCENE_RULE = """
Decision checklist (apply to any image edit):
1. Identify the requested change and whether it is visibly achieved.
2. Compare the identities, number, arrangement, and surroundings of source objects
   with the edited image. Explicitly check for unrequested additions, deletions,
   replacements, text, and scene changes. Similar object categories alone do not
   establish that the same scene was preserved.
3. If the requested change is absent or contradicted, choose no. If it is visibly
   achieved but another meaningful semantic condition or preserved source element
   is only partly satisfied, choose partial. Choose yes when the requested change
   is achieved and relevant source content remains intact.
4. A visible requested relation may coexist with a meaningful count or scene
   mismatch. In that situation choose partial rather than yes. Do not call it no
   solely because the edit has unrelated changes when the requested outcome is
   still recognizable. Ignore purely aesthetic differences.
Return the original JSON contract with label and rationale. Do not quote this
checklist verbatim; cite image evidence in the rationale.
""".strip()
RELATION_RULE = """
Decision checklist (apply to any relation or movement edit):
First identify the specific source object and the requested destination or relation.
Check whether the same object occupies that destination in the edited image.
Proximity to the destination is not equivalent to being inside, beneath, behind,
or on the requested object. If the specified relation remains absent, choose no;
if it is partly achieved, choose partial; if it is clearly achieved with the
source context preserved, choose yes. Preserve the JSON label/rationale contract.
""".strip()
COACHING = """The human label is partial. In the source there are two separate
unlit candles on a wooden surface. The edit brings candles closer, but the edited
image shows three lit candles, a changed setting, and text. Prior wrong answers
called the candle scene 'intact' merely because the objects are candles and closer.
Derive a reusable policy: check requested relation AND unrelated count, identity,
and scene changes. When the requested effect exists but preservation is materially
imperfect, distinguish partial from yes. Do not mention candles or these images
in the revised rubric. This visual audit is coaching evidence, not an instruction
to assign the label without examining images."""


def candidate_bank(cases, prior, pilot, out):
    path = out / 'candidate_bank.json'
    if path.exists():
        bank = json.loads(path.read_text())
        for c in cases:
            for text in bank[c['case_id']].values():
                if candidate_issue(text, c):
                    raise ValueError('Saved candidate violates the prompt contract')
        return bank
    bank = {}
    for c in cases:
        cid = c['case_id']
        old = prior[cid]
        pool = {'seed': old['unchanged'], 'gepa_baseline': old['single'],
                'previous_repeated': old['repeated']}
        if cid == 'C08':
            pool['scene_seed'] = old['unchanged'] + '\n\n' + SCENE_RULE
            pool['scene_gepa'] = old['single'] + '\n\n' + SCENE_RULE
            for idx, name in enumerate(('seed', 'gepa_baseline'), 1):
                proposal = pilot.propose(c, 'contrastive', idx, pool[name], coaching=COACHING)
                pool['contrastive_' + name] = proposal['prompt']
        else:
            pool['relation_gepa'] = old['single'] + '\n\n' + RELATION_RULE
        # Equal texts have one evaluation identity and cannot create fake diversity.
        unique = {}
        seen = set()
        for name, text in pool.items():
            if digest(text) in seen:
                continue
            seen.add(digest(text))
            if candidate_issue(text, c):
                if name.startswith('contrastive_'):
                    continue
                raise ValueError(f'{cid}/{name}: invalid candidate')
            unique[name] = text
        bank[cid] = unique
    save(path, bank)
    return bank


def block_score(values):
    return float(np.mean(values) - .25 * (max(values) - min(values)))


def evaluate_blocks(pilot, case, texts, phase, blocks, draws):
    result = {name: [] for name in texts}
    for b in range(blocks):
        names = list(texts)
        random.Random(pilot.config['seed'] + 100 * b + int(case['case_id'][1:])).shuffle(names)
        for name in names:
            r = pilot.evaluate(case, phase, 0, f'b{b}-{name}', texts[name], draws)
            result[name].append({'accuracy': r['accuracy'], 'counts': r['counts']})
    return result


def rate(rows):
    return float(np.mean([r['accuracy'] for r in rows]))


def select(candidates, dev, incumbent='gepa_baseline'):
    base_score = block_score([r['accuracy'] for r in dev[incumbent]])
    ranked = sorted(candidates, key=lambda n:(block_score([r['accuracy'] for r in dev[n]]),
                                              rate(dev[n]), -len(candidates[n])), reverse=True)
    name = ranked[0]
    score = block_score([r['accuracy'] for r in dev[name]])
    return name if name != incumbent and score >= base_score + .05 - 1e-12 else incumbent


def confirm(pilot, case, bank, chosen):
    if chosen == 'gepa_baseline':
        return {'selected': chosen, 'confirmed': False, 'reason': 'no development gain'}
    texts = {name:bank[name] for name in ('gepa_baseline', chosen)}
    rows = evaluate_blocks(pilot, case, texts, 'confirm', 3, 12)
    base = rows['gepa_baseline']; challenger = rows[chosen]
    gain = rate(challenger) - rate(base)
    floor = min(r['accuracy'] for r in challenger) - min(r['accuracy'] for r in base)
    accepted = gain >= .10 - 1e-12 and floor >= -.10 - 1e-12
    return {'selected': chosen if accepted else 'gepa_baseline',
            'confirmed': accepted, 'reason': 'accepted' if accepted else 'insufficient fresh gain',
            'candidate': chosen, 'gain': gain, 'worst_block_difference': floor,
            'blocks': rows}


def frozen_selection(cases, prior, bank, pilot, out):
    path = out / 'frozen_selection.json'
    if path.exists():
        value = json.loads(path.read_text())
        for c in cases:
            cid = c['case_id']
            if digest(bank[cid][value[cid]['candidate']]) != value[cid]['prompt_sha256']:
                raise ValueError('Frozen candidate changed')
        return value
    decisions = {}
    for c in cases:
        cid = c['case_id']; pool = bank[cid]
        dev = evaluate_blocks(pilot, c, pool, 'development', 3, 8)
        save(out / f'development_{cid}.json', dev)
        tentative = select(pool, dev)
        confirmation = confirm(pilot, c, pool, tentative)
        final_name = confirmation['selected']
        decisions[cid] = {'candidate': final_name, 'prompt_sha256': digest(pool[final_name]),
                          'development_choice': tentative, 'development': dev,
                          'confirmation': confirmation}
        save(out / f'decision_{cid}.json', decisions[cid])
    save(path, decisions)
    save(out / 'frozen_manifest.json', {'sha256': digest(path.read_bytes()),
                                       'time': datetime.now(timezone.utc).isoformat()})
    return decisions


def fresh_final(pilot, cases, prior, bank, decisions, out):
    frozen_path = out / 'frozen_selection.json'
    if digest(frozen_path.read_bytes()) != json.loads((out/'frozen_manifest.json').read_text())['sha256']:
        raise ValueError('Frozen selection changed')
    all_cases = load_cases()
    original = {c['case_id']:c for c in all_cases}
    schedule = []
    for c in all_cases:
        cid = c['case_id']; baseline = prior[cid]['single']
        for rep in range(pilot.config['final_repeats']):
            schedule.append((cid,'baseline',rep,baseline))
        if cid in decisions:
            selected = bank[cid][decisions[cid]['candidate']]
            if selected != baseline:
                for rep in range(pilot.config['final_repeats']):
                    schedule.append((cid,'challenger',rep,selected))
    random.Random(pilot.config['seed'] + 791).shuffle(schedule)
    from concurrent.futures import ThreadPoolExecutor
    def call(job):
        cid,arm,rep,prompt=job
        case=original[cid]
        request=judge_request(case,prompt,pilot.config)
        identity=f'{cid}/{arm}/0/final/{digest(prompt)}/{rep:03}'
        row=pilot.store.call(identity,request)
        return cid,arm,rep,row['parsed']
    with ThreadPoolExecutor(max_workers=pilot.config['concurrency']) as pool:
        list(pool.map(call,schedule))
    results = {cid:{'baseline':[],'challenger':[]} for cid in original}
    for cid,arm,rep,prompt in schedule:
        identity=f'{cid}/{arm}/0/final/{digest(prompt)}/{rep:03}'
        results[cid][arm].append((rep,pilot.store.rows[identity]['parsed']))
    for cid in results:
        results[cid]['baseline']=[r for _,r in sorted(results[cid]['baseline'])]
        results[cid]['challenger']=[r for _,r in sorted(results[cid]['challenger'])]
        if not results[cid]['challenger']:
            results[cid]['challenger']=results[cid]['baseline']
    save(out/'final_results.json',results)
    return results


def report(out,cases,results,decisions,store,config):
    allcases=load_cases()
    metrics={}
    for arm in ('baseline','challenger'):
        rates={c['case_id']:sum(correct(d,c['target_label']) for d in results[c['case_id']][arm])/
               len(results[c['case_id']][arm]) for c in allcases}
        metrics[arm]={'accuracy':float(np.mean(list(rates.values()))),'per_case':rates}
    delta=np.array([metrics['challenger']['per_case'][c['case_id']] -
                    metrics['baseline']['per_case'][c['case_id']] for c in allcases])
    rng=np.random.default_rng(config['seed'])
    resamples=rng.integers(0,len(allcases),(10000,len(allcases)))
    ci=np.quantile(delta[resamples].mean(axis=1),[.025,.975]).tolist()
    value={'metrics':metrics,'difference':float(delta.mean()),'case_bootstrap_95_ci':ci,
           'selected':{cid:d['candidate'] for cid,d in decisions.items()},
           'completed_calls':len(store.rows),'estimated_list_cost_usd':store.spent}
    save(out/'summary.json',value)
    lines=['# Focused robust GEPA repair', '',
           'Exploratory development on two previously seen cases. The other eight use identical',
           'GEPA prompts and *shared final judgments* in both arms, so their contribution to',
           'the paired difference is exactly zero.', '',
           f"Baseline GEPA: **{metrics['baseline']['accuracy']:.1%}**; challenger: **{metrics['challenger']['accuracy']:.1%}**.",
           f"Difference: **{100*delta.mean():+.1f} percentage points**, descriptive paired case-bootstrap",
           f"95% interval [{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] points.", '',
           '| Case | Baseline | Challenger | Selected prompt |', '|---|---:|---:|---|']
    for c in allcases:
        cid=c['case_id']; selected=decisions[cid]['candidate'] if cid in decisions else 'same'
        lines.append(f"| {cid} | {metrics['baseline']['per_case'][cid]:.1%} | "
                     f"{metrics['challenger']['per_case'][cid]:.1%} | {selected} |")
    lines += ['', '## Limits', '',
              '- These two cases and their labels informed development. This does not establish unseen-task transfer.',
              '- C08 used an assistant visual audit of counts and scene changes as optimizer coaching; scaling requires a reliable source for such evidence.',
              '- Final evaluation was frozen before calls; the same control draw is reused when prompts are identical.',
              '- API calls are fresh requests, but their statistical independence and stationarity are not guaranteed.',
              '- Costs are estimated list prices; failed-call billing is unknown.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--dry-run',action='store_true');p.add_argument('--live',action='store_true')
    p.add_argument('--resume',action='store_true');p.add_argument('--report',action='store_true')
    p.add_argument('--budget-usd',type=float,default=5.0)
    p.add_argument('--final-repeats',type=int,default=30)
    p.add_argument('--concurrency',type=int,default=8)
    args=p.parse_args()
    if args.final_repeats<2 or args.concurrency<1 or args.budget_usd<=0:p.error('Invalid counts/budget')
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    cases={c['case_id']:c for c in load_cases()};focus=[cases[k] for k in FOCUS]
    prior=json.loads(PRIOR.read_text())
    config={'model':'gpt-5.4-mini','temperature':.3,'judge_max_tokens':512,
            'reflection_max_tokens':4096,'seed':44,'concurrency':args.concurrency,
            'search_repeats':5,'confirmation_repeats':12,'final_repeats':args.final_repeats,
            'input_price':.75,'output_price':4.5,'budget_usd':args.budget_usd,
            'gepa_python':str((ROOT/'.venv-gepa/bin/python').absolute()),
            'source_sha256':digest(Path(__file__).read_bytes()),
            'gepa_worker_sha256':digest((ROOT/'run/aurora_prompt_repair/gepa_worker.py').read_bytes()),
            'prior_sha256':digest(PRIOR.read_bytes()),
            'manual_coaching_sha256':digest(COACHING)}
    saved=out/'run_config.json'
    if saved.exists():
        if json.loads(saved.read_text())!=config:raise ValueError('Frozen configuration changed')
        if not args.resume and not args.report and not args.dry_run:p.error('Existing run needs --resume')
    else:save(saved,config)
    # Upper bound includes 7+4 candidates, three blocks of eight each; two
    # confirmations, two GEPA mutations, and final baseline+focus challenger.
    estimate={'development_judges':(7+4)*3*8,'confirmation_judges_at_most':2*2*3*12,
              'gepa_judges_at_most':2*4*5,
              'final_judges_at_most':(10+2)*args.final_repeats,
              'reflections_at_most':2,
              'budget_usd':args.budget_usd}
    save(out/'estimate.json',estimate)
    if args.dry_run:print(json.dumps(estimate,indent=2));return
    if args.report:
        results=json.loads((out/'final_results.json').read_text())
        decisions=json.loads((out/'frozen_selection.json').read_text())
        report(out,focus,results,decisions,CallStore(out,config),config);return
    require_live(args.live,context='Focused robust GEPA repair')
    store=CallStore(out,config);store.connect()
    pilot=Pilot(out,config,focus,store)
    bank=candidate_bank(focus,prior,pilot,out)
    decisions=frozen_selection(focus,prior,bank,pilot,out)
    results=fresh_final(pilot,focus,prior,bank,decisions,out)
    outcome=report(out,focus,results,decisions,store,config)
    pilot.log(f"Complete: baseline={outcome['metrics']['baseline']['accuracy']:.3f}; "
              f"challenger={outcome['metrics']['challenger']['accuracy']:.3f}; "
              f"cost=${store.spent:.3f}")

if __name__=='__main__':main()
