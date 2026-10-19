"""Continue after a valid provider response failed the compiler's semantic checks.

The original one-attempt failure is retained, with no retry or replacement.
Only a completed first provider slot from the declared Luna model qualifies.
"""
import argparse
from pathlib import Path

from critical.core.decision.artifacts import digest
from run.calitree_three_splits import prepare, read, exact, collect_physical, collect_all, fit_one, summarize, IDENTITY, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--live', action='store_true', required=True)
    args = parser.parse_args(); out = args.output_dir.resolve(); manifest = prepare(out)
    first = manifest['cases'][0]
    jobs = [read(p) for p in (out / 'extraction/ledgers' / first['case'] / 'compile/jobs').glob('*.json')]
    if len(jobs) != 1 or jobs[0]['outcome'] != 'completed' or jobs[0]['response']['model'] != IDENTITY['model']:
        raise ValueError('Provider availability was not established; continuation is not permitted')
    retained = read(out / 'extraction/cases' / (first['case'] + '.json'))
    if retained['compilation'] is not None or not retained['error']:
        raise ValueError('This continuation only handles a retained first compiler-validation failure')
    exact(out / 'continuation.json', {'reason': 'Provider completed successfully; first source failed compiler semantic validation. Retain failure and continue other declared sources.',
        'first_case': first['case'], 'retained_error': retained['error'], 'first_slot_ref': jobs[0]['execution_ref'],
        'retries': 0, 'resampling': False, 'changed_gates': False,
        'runner_sha256': fingerprint(Path(__file__).resolve())})
    observations = collect_physical(out / 'extraction', manifest, True)
    exact(out / 'extraction/observations.json', observations)
    collect_all(out, manifest, True)
    for name in ('split1', 'split2', 'split3'):
        fit_one(out, name)
    summarize(out)


if __name__ == '__main__':
    main()
