"""Run matched single-draw and repeated GEPA repair on 50 AURORA cases.

The selected cases are task-disjoint from the earlier 100-case repair sample.
Both arms start from the same CaliTree rubric; their focal human labels are used
for search feedback, so this is an in-sample optimizer comparison.
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
    ROOT, WORKER, CallStore, Pilot, digest, metrics, save,
)
from vejudge.lm_engine.gate import require_live


SOURCE = ROOT / 'logs/exps/aurora-prompt-repair/clean_holdout_manifest.json'
RUBRIC = ROOT / 'vejudge/core/prompts/templates/calitree_v2/initial_rubric.txt'
DATA = ROOT / 'data/aurora/bench'
ARMS = ('single', 'repeated')


def select_cases(rows, seed=44, n=50):
    if n != 50:
        raise ValueError('This frozen experiment requires exactly 50 cases')
    pool = [r for r in rows if r['source_split'] == 'test']
    rng = random.Random(seed)
    rng.shuffle(pool)
    by_label = {label: [r for r in pool if r['target_label'] == label]
                for label in ('no', 'partial', 'yes')}
    quotas = {'no': 17, 'partial': 17, 'yes': 16}
    chosen, used = [], set()
    task_counts, model_counts = Counter(), Counter()
    while any(quotas.values()):
        for label in ('no', 'partial', 'yes'):
            if not quotas[label]:
                continue
            eligible = [(i, r) for i, r in enumerate(by_label[label])
                        if r['task_uid'] not in used]
            if not eligible:
                raise ValueError(f'Insufficient distinct test tasks for {label}')
            _, row = min(eligible, key=lambda pair: (
                task_counts[pair[1]['task']], model_counts[pair[1]['model']], pair[0]))
            chosen.append(row)
            used.add(row['task_uid'])
            task_counts[row['task']] += 1
            model_counts[row['model']] += 1
            quotas[label] -= 1
    return chosen


def prepare_cases(out, source=SOURCE, data=DATA, rubric=RUBRIC, seed=44):
    path = out / 'cases.json'
    if path.exists():
        cases = json.loads(path.read_text())
    else:
        rows = json.loads(source.read_text())['cases']
        prompt = rubric.read_text()
        cases = []
        for index, row in enumerate(select_cases(rows, seed), 1):
            case = dict(row)
            case['case_id'] = f'F{index:02}'
            case['prompt'] = prompt
            case['prompt_sha256'] = digest(prompt)
            for kind, field in [('source', 'source_image_path'),
                                ('edited', 'edited_image_path')]:
                old = str(row[field])
                if '/human_ratings/' not in old:
                    raise ValueError(f'Unknown AURORA image layout: {old}')
                local = data / 'human_ratings' / old.split('/human_ratings/', 1)[1]
                if not local.is_file():
                    raise FileNotFoundError(local)
                case[f'{kind}_local_image'] = str(local.resolve())
                case[f'{kind}_image_sha256'] = digest(local.read_bytes())
            cases.append(case)
        save(path, cases)
    if len(cases) != 50 or len({c['task_uid'] for c in cases}) != 50:
        raise ValueError('Frozen cases must contain 50 distinct source tasks')
    if [c['item_id'] for c in cases] != [c['item_id'] for c in select_cases(
            json.loads(source.read_text())['cases'], seed)]:
        raise ValueError('Frozen selection no longer matches source manifest')
    prompt = rubric.read_text()
    for case in cases:
        if case['prompt'] != prompt or case['prompt_sha256'] != digest(prompt):
            raise ValueError('Seed rubric changed')
        for kind in ('source', 'edited'):
            if digest(Path(case[f'{kind}_local_image']).read_bytes()) != case[f'{kind}_image_sha256']:
                raise ValueError(f"Image hash changed for {case['case_id']} {kind}")
    return cases


class FiftyPilot(Pilot):
    def final(self, frozen):
        if digest((self.out / 'frozen_prompts.json').read_bytes()) != json.loads(
                (self.out / 'frozen_manifest.json').read_text())['sha256']:
            raise ValueError('Frozen prompts changed before final evaluation')
        results = {}
        jobs = [(c, arm) for c in self.cases for arm in ARMS]
        random.Random(self.config['seed'] + 1).shuffle(jobs)
        for case, arm in jobs:
            results.setdefault(case['case_id'], {})[arm] = self.evaluate(
                case, arm, 0, 'final', frozen[case['case_id']][arm],
                self.config['final_repeats'])
            self.log(f"Final {case['case_id']} {arm}: "
                     f"{results[case['case_id']][arm]['accuracy']:.3f}; "
                     f"cost=${self.store.spent:.3f}")
        save(self.out / 'final_results.json', results)
        return results


def write_report(out, cases, config):
    results = json.loads((out / 'final_results.json').read_text())
    summary = {arm: metrics(cases, results, arm) for arm in ARMS}
    delta = np.array([results[c['case_id']]['repeated']['accuracy'] -
                      results[c['case_id']]['single']['accuracy'] for c in cases])
    rng = np.random.default_rng(config['seed'])
    indices = rng.integers(0, len(cases), size=(10000, len(cases)))
    ci = np.quantile(delta[indices].mean(axis=1), [.025, .975]).tolist()
    decisions = [json.loads(p.read_text()) for p in
                 (out / 'search').glob('*/*/*/decision.json')]
    rows = [json.loads(line) for line in (out / 'llm-histories.log').read_text().splitlines()
            if '"response"' in line]
    by_kind = Counter('reflect' if r['request']['kind'] == 'reflect' else
                      ('final' if '/final/' in r['id'] else 'search_or_confirm')
                      for r in rows)
    usage = {'prompt_tokens': sum(r['response']['usage']['prompt_tokens'] for r in rows),
             'completion_tokens': sum(r['response']['usage']['completion_tokens'] for r in rows),
             'estimated_list_cost_usd': sum(r['cost_usd'] for r in rows),
             'completed_calls': len(rows), 'calls_by_kind': dict(by_kind)}
    same = [c['case_id'] for c in cases if digest(json.loads(
        (out / 'frozen_prompts.json').read_text())[c['case_id']]['single']) == digest(json.loads(
        (out / 'frozen_prompts.json').read_text())[c['case_id']]['repeated'])]
    value = {'arms': summary, 'repeated_minus_single': float(delta.mean()),
             'case_bootstrap_95_ci': ci, 'same_prompt_cases': same,
             'accepted_edits': dict(Counter(d['arm'] for d in decisions if d['accepted'])),
             'usage': usage, 'case_count': len(cases),
             'final_repeats': config['final_repeats']}
    save(out / 'summary.json', value)
    lines = ['# Fifty-case repeated GEPA comparison', '',
             'Both arms start from the same rubric, receive five mutation proposals per case,',
             'and are frozen before 15 fresh final judgments. Search feedback uses focal',
             'human labels, so this compares in-sample repair on new source tasks rather',
             'than held-out generalization.', '',
             f"Single-draw: **{summary['single']['accuracy']:.1%}**; repeated: "
             f"**{summary['repeated']['accuracy']:.1%}**. Difference: "
             f"**{100*delta.mean():+.1f} percentage points**; descriptive task-bootstrap "
             f"95% interval [{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] points.", '',
             '| Case | Human label | Single / 15 | Repeated / 15 |',
             '|---|---|---:|---:|']
    for c in cases:
        cid = c['case_id']
        lines.append(f"| {cid} | {c['target_label']} | "
                     f"{round(results[cid]['single']['accuracy'] * config['final_repeats'])} | "
                     f"{round(results[cid]['repeated']['accuracy'] * config['final_repeats'])} |")
    lines += ['', '## Stability and cost', '',
              '| Arm | Pairwise disagreement | Always wrong | All 15 correct | Accepted edits |',
              '|---|---:|---:|---:|---:|']
    for arm in ARMS:
        m = summary[arm]
        lines.append(f"| {arm} | {m['disagreement']:.1%} | {m['stable_wrong_cases']} | "
                     f"{m['all_correct_cases']} | {value['accepted_edits'].get(arm, 0)} |")
    lines += ['', f"Completed calls: {usage['completed_calls']}; input tokens: "
              f"{usage['prompt_tokens']:,}; output tokens: {usage['completion_tokens']:,}; "
              f"estimated list cost: **${usage['estimated_list_cost_usd']:.3f}**.", '',
              f"Same final prompt in both arms for {len(same)}/50 cases; those cases use "
              'separate fresh draws, so their observed differences reflect sampling.', '',
              'The sample is class-balanced, not prevalence-weighted. It contains only',
              'AURORA test-split tasks outside the earlier 100-case sample. One trajectory',
              'per case and arm does not establish optimizer reliability.']
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--live', action='store_true')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--report', action='store_true')
    p.add_argument('--model', default='gpt-5.4-mini')
    p.add_argument('--gepa-python', type=Path, default=ROOT / '.venv-gepa/bin/python')
    p.add_argument('--rounds', type=int, default=5)
    p.add_argument('--search-repeats', type=int, default=5)
    p.add_argument('--confirmation-repeats', type=int, default=10)
    p.add_argument('--final-repeats', type=int, default=15)
    p.add_argument('--temperature', type=float, default=.3)
    p.add_argument('--judge-max-tokens', type=int, default=512)
    p.add_argument('--reflection-max-tokens', type=int, default=4096)
    p.add_argument('--seed', type=int, default=44)
    p.add_argument('--concurrency', type=int, default=8)
    p.add_argument('--budget-usd', type=float, default=30.0)
    p.add_argument('--input-price', type=float, default=.75)
    p.add_argument('--output-price', type=float, default=4.5)
    args = p.parse_args()
    if min(args.rounds, args.search_repeats, args.confirmation_repeats,
           args.concurrency, args.final_repeats) < 1 or args.budget_usd <= 0:
        p.error('Invalid counts or budget')
    out = args.output_dir.resolve()
    if args.report:
        cases = prepare_cases(out)
        write_report(out, cases, json.loads((out / 'run_config.json').read_text()))
        return
    out.mkdir(parents=True, exist_ok=True)
    cases = prepare_cases(out, seed=args.seed)
    config = {k: str(v.absolute()) if isinstance(v, Path) else v
              for k, v in vars(args).items()
              if k not in ('dry_run', 'live', 'resume', 'report', 'output_dir')}
    config.update(source_sha256=digest(SOURCE.read_bytes()),
                  rubric_sha256=digest(RUBRIC.read_bytes()),
                  worker_sha256=digest(WORKER.read_bytes()),
                  runner_sha256=digest(Path(__file__).read_bytes()),
                  base_runner_sha256=digest((ROOT / 'run/robust_prompt_repair_pilot.py').read_bytes()),
                  cases_sha256=digest((out / 'cases.json').read_bytes()),
                  gepa_version='0.1.4')
    path = out / 'run_config.json'
    if path.exists():
        if json.loads(path.read_text()) != config:
            raise ValueError('Frozen run configuration changed')
        if not args.resume and not args.dry_run:
            p.error('Existing run requires --resume')
    else:
        save(path, config)
    max_judges = 50 * args.rounds * (4 + 4 * args.search_repeats +
                                    2 * args.confirmation_repeats) + 100 * args.final_repeats
    reflections = 100 * args.rounds
    estimate = {'max_judge_calls': max_judges,
                'max_reflection_calls': reflections,
                'final_judge_calls': 100 * args.final_repeats,
                'planning_cost_usd': (max_judges * (1800 * args.input_price +
                                   args.judge_max_tokens * args.output_price) +
                                   reflections * (7000 * args.input_price +
                                   args.reflection_max_tokens * args.output_price)) / 1e6,
                'note': 'Conservative planning assumes 1800 judge input and 7000 reflection input tokens.'}
    save(out / 'estimate.json', estimate)
    if args.dry_run:
        print(json.dumps(estimate, indent=2))
        return
    require_live(args.live, context='Fifty-case repeated GEPA comparison')
    store = CallStore(out, config)
    store.connect()
    pilot = FiftyPilot(out, config, cases, store)
    frozen = pilot.search()
    pilot.final(frozen)
    summary = write_report(out, cases, config)
    pilot.log(f"Complete: {summary['usage']['completed_calls']} calls, "
              f"${summary['usage']['estimated_list_cost_usd']:.3f}")


if __name__ == '__main__':
    main()
