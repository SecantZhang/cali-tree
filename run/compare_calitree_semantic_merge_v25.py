"""Paired offline budget comparison of ID and semantic pair scheduling."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from critical.core.calibration import semantic_merge_v25 as merge
from critical.core.decision.artifacts import digest, save_json
from run.calitree_semantic_merge_v25 import run
from run.calitree_task_coverage import read, fingerprint


class FitMemo:
    """Share identical computation only; each arm pays its own logical fit budget."""
    def __init__(self, folder):
        self.folder = folder
        self.values = {}
        self.hits = 0

    def __call__(self, rows, requirements, *, max_rules, config, preferred):
        inputs = {'rows': rows, 'requirements': requirements, 'max_rules': max_rules,
                  'config': asdict(config), 'preferred': sorted(preferred)}
        key = digest(inputs)
        if key not in self.values:
            started = perf_counter()
            value, report = merge.learner.fit(rows, requirements, max_rules=max_rules, config=config, preferred=preferred)
            record = {'input_ref': key, 'inputs': inputs, 'model': value, 'report': report,
                      'cold_seconds': perf_counter() - started}
            save_json(self.folder / (key + '.json'), record)
            self.values[key] = value, report
        else:
            self.hits += 1
        return deepcopy(self.values[key])


def compare(out, previous):
    if out.exists():
        raise ValueError('Use a fresh comparison directory')
    out.mkdir(parents=True)
    protocol = {'version': merge.VERSION, 'budgets': [4, 8, 24], 'orderings': ['artifact_id', 'semantic'],
                'primary_budget': 4, 'splits': [1, 2, 3], 'fit_config': asdict(merge.learner.Config()),
                'ranking': ['supported task-outcome distribution overlap', 'prediction agreement on shared task types in child union',
                            'top-two-level predicate-family overlap', 'artifact ID for ties'],
                'controls': 'Same starting v23 bank, v24 fitter, candidate selection, child accuracy floors, and full routing checks.',
                'budget_accounting': 'Every arm has a separate logical fit cache; identical fits memoized physically across arms. Report logical fits and states, not memo wall time as search savings.',
                'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'protocol.json', protocol)
    memo = FitMemo(out / 'fits'); measurements = []
    for budget in protocol['budgets']:
        for ordering in protocol['orderings']:
            folder = out / f'{ordering}-{budget}'
            run(folder, previous, fit_budget=budget, ordering=ordering, fitter=memo)
            result = read(folder / 'results.json')
            for split in result['splits']:
                detail = read(folder / f"split{split['split']}/development.json")
                reports = {f['fit_ref']: f['report'] for t in detail['trials'] for f in t['fits'] if 'report' in f}
                measurements.append({'budget': budget, 'ordering': ordering, 'split': split['split'],
                                     'fits': split['work']['pair_fits'], 'states': sum(r['states'] for r in reports.values()),
                                     'transitions': sum(r['transitions'] for r in reports.values()),
                                     'gate_rebuilds': split['work']['gate_rebuilds'], 'before': split['before'], 'after': split['after'],
                                     'accepted_merges': split['accepted_merges'], 'accepted_shared_correct': split['accepted_shared_correct'],
                                     'routing_regressions': split['routing_regressions'], 'comparisons': split['comparisons']})
            save_json(out / 'progress.json', measurements)
    summary = {'protocol_ref': digest(protocol), 'measurements': measurements,
               'physical_unique_fits': len(memo.values), 'cross_arm_memo_hits': memo.hits,
               'new_model_calls': 0, 'reserved_final_predictions': 0}
    save_json(out / 'results.json', summary)
    save_json(out / 'manifest.json', {'previous_run': str(previous), 'protocol_ref': digest(protocol),
              'code_hashes': {str(Path(f).resolve()): fingerprint(f) for f in (__file__, merge.__file__, 'run/calitree_semantic_merge_v25.py')}})
    print({'comparison_complete': True, 'physical_unique_fits': len(memo.values)}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True); p.add_argument('--previous-run', type=Path, required=True)
    a = p.parse_args(); compare(a.output_dir.resolve(), a.previous_run.resolve())
