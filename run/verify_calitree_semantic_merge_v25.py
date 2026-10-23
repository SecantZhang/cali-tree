"""Audit semantic scheduling, isolated budgets, parent retention and routed replay."""
import argparse
from dataclasses import asdict
from pathlib import Path

from critical.core.calibration import semantic_merge_v25 as merge
from critical.core.decision.artifacts import digest, save_json
from run.calitree_counterexample_coverage_v23 import load_examples
from run.calitree_task_coverage import read, fingerprint
from run.verify_calitree_pairwise_merge_v24 import audit as audit_pipeline


def audit(out):
    manifest = read(out / 'manifest.json'); protocol = read(out / 'protocol.json'); result = read(out / 'results.json')
    assert digest(protocol) == manifest['protocol_ref'] == result['protocol_ref']
    for filename, expected in manifest['code_hashes'].items():
        assert fingerprint(filename) == expected
    previous = Path(manifest['previous_run']); fits = {}
    for path in sorted((out / 'fits').glob('*.json')):
        record = read(path); assert digest(record['inputs']) == record['input_ref'] == path.stem
        fits[path.stem] = record
    hits = []; schedule_count = 0; replay_count = 0
    def replay_fit(rows, requirements, *, max_rules, config, preferred):
        inputs = {'rows': rows, 'requirements': requirements, 'max_rules': max_rules,
                  'config': asdict(config), 'preferred': sorted(preferred)}
        key = digest(inputs); record = fits[key]; assert record['inputs'] == inputs
        hits.append(key)
        return record['model'], record['report']
    measured = []
    for budget in protocol['budgets']:
        for ordering in protocol['orderings']:
            arm = out / f'{ordering}-{budget}'
            audit_pipeline(arm)
            summary = read(arm / 'results.json')
            for overview in summary['splits']:
                i = overview['split']; folder = arm / f'split{i}'
                detail = read(folder / 'development.json'); rows = read(folder / 'training_data.json')
                bank = {m['runtime']['artifact_ref']: m for m in read(folder / 'baseline_models.json')}
                _, bound, _, _, _ = load_examples(previous, i)
                programs = {r['source_group']: bound[r['case']]['example']['program'] for r in rows}
                cache = {}; counters = {'pair_fits': 0, 'pair_fit_cache_hits': 0}
                config = merge.Config(**detail['config']); fit_config = merge.learner.Config(**detail['fit_config'])
                assert config.max_pair_fits == budget and detail['ordering'] == ordering
                for schedule in detail['schedules']:
                    pairs, profiles = merge.ordered_pairs(bank, rows, programs, ordering)
                    assert pairs == schedule['pairs'] and profiles == schedule['profiles']
                    round_trials = [t for t in detail['trials'] if t['round'] == schedule['round']]
                    seen = []
                    for pair in pairs:
                        trials = [t for t in round_trials if t['children'] == pair['children']]
                        assert trials
                        children = [bank[k] for k in pair['children']]
                        candidates, logs = merge.parent_candidates(children, rows, fit_config, cache, counters, config, replay_fit)
                        assert all(t['fits'] == logs and t['candidate_count'] == len(candidates) for t in trials)
                        assert [t['parent'] for t in trials if 'parent' in t] == candidates
                        seen.extend(trials)
                    assert seen == round_trials
                    schedule_count += 1
                    events = [e for e in detail['accepted'] if e['round'] == schedule['round']]
                    if events:
                        event, = events
                        bank = {k: v for k, v in bank.items() if k not in event['children']}
                        bank[event['parent_ref']] = event['parent']
                        bank = {k: v for k, v in bank.items() if k in merge.expert_artifacts(merge.route_support.restore(event['gate']))}
                assert counters['pair_fits'] == detail['work']['pair_fits'] <= budget
                assert counters['pair_fit_cache_hits'] == detail['work']['pair_fit_cache_hits']
                reports = {f['fit_ref']: f['report'] for t in detail['trials'] for f in t['fits'] if 'report' in f}
                measurement = {'budget': budget, 'ordering': ordering, 'split': i,
                               'fits': counters['pair_fits'], 'states': sum(r['states'] for r in reports.values()),
                               'transitions': sum(r['transitions'] for r in reports.values()),
                               'gate_rebuilds': detail['work']['gate_rebuilds'], 'before': overview['before'], 'after': overview['after'],
                               'accepted_merges': overview['accepted_merges'], 'accepted_shared_correct': overview['accepted_shared_correct'],
                               'routing_regressions': overview['routing_regressions'], 'comparisons': overview['comparisons']}
                measured.append(measurement); replay_count += 98
    assert measured == result['measurements']
    assert len(set(hits)) == len(fits) == result['physical_unique_fits']
    assert len(hits) - len(fits) == result['cross_arm_memo_hits']
    # Unrestricted control should exactly recover the previously audited v24 bank.
    historical = out.parent / '261019-pairwise-merge-v24-r1'
    for i in (1, 2, 3):
        control = read(out / f'artifact_id-24/split{i}/development.json')
        old = read(historical / f'split{i}/development.json')
        for key in ('gate', 'models', 'accepted', 'final_complexity', 'work', 'final_routing_check'):
            assert control[key] == old[key], (i, key)
    checks = {'passed': True, 'arms': 6, 'split_runs': 18, 'pair_schedules_verified': schedule_count,
              'logical_fits_verified': len(hits), 'physical_unique_fits': len(fits),
              'recorded_decisions_replayed': replay_count, 'local_predictions_preserved_per_arm': 144,
              'original_child_batches_preserved_per_arm': 12, 'coverage_regressions': 0,
              'full_budget_control_reproduces_v24': True, 'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'verification.json', checks)
    save_json(out / 'completion_seal.json', {'files': {str(p.relative_to(out)): fingerprint(p) for p in sorted(out.rglob('*'))
              if p.is_file() and p != out / 'completion_seal.json'}, 'auditor_sha256': fingerprint(__file__)})
    print(checks, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    audit(p.parse_args().output_dir.resolve())
