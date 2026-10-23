"""Find exact historical flat-judge slots for the frozen forward inputs.

Read only: never contacts a model or copies results into the live collector.
Slot hashes must prove the same identity, prompt, schema, media and token cap.
"""
import argparse
import hashlib
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.calitree_aurora_pilot_v29 import IDENTITY, read, fingerprint
from run.collect_calitree_guarded_forward_v32 import verify


def audit(forward, roots, output):
    if output.exists():
        raise ValueError('A fresh audit directory is required')
    verify(forward)
    expected = {}
    instructions = defaultdict(list)
    for e in read(forward / 'inputs.json'):
        media = [{'type': m['type'], 'sha256': hashlib.sha256(Path(m['path']).read_bytes()).hexdigest()}
                 if m['type'] == 'image' else m for m in media_inputs(e['evidence'])]
        expected[e['case']] = media
        instructions[e['instruction']].append(e['case'])
    budgets = subprocess.run(['rg', '--files', '--no-ignore', *map(str, roots), '-g', 'budget.json'],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    counts = Counter()
    matches = defaultdict(list)
    prompt = (task.TEMPLATES / 'regular.txt').read_text()
    for file in sorted(budgets):
        p = Path(file)
        try:
            budget = read(p)
        except (OSError, ValueError):
            counts['invalid_budget_files'] += 1
            continue
        if not isinstance(budget, dict) or not isinstance(budget.get('limits'), dict):
            counts['other_budget_schemas'] += 1
            continue
        if budget['limits'].get('identity') != IDENTITY:
            continue
        counts['identity_matched_ledgers'] += 1
        for job in sorted((p.parent / 'jobs').glob('*.json')):
            counts['job_files_scanned'] += 1
            r = read(job)
            if not isinstance(r, dict) or r.get('stage') != 'flat_judge':
                continue
            payload = r.get('payload')
            if not isinstance(payload, dict) or set(payload) != {'instruction'}:
                continue
            cases = instructions.get(payload['instruction'], [])
            if not cases:
                continue
            counts['instruction_matches'] += 1
            if r.get('route') is not None or r.get('slot') != 'once' or r.get('max_tokens') != 2048:
                counts['incompatible_slot_protocols'] += 1
                continue
            slot = digest([IDENTITY, r.get('case_id'), 'flat_judge', payload, task.SCHEMA,
                           prompt, r.get('media_identity'), 'once', 2048])
            if slot != job.stem or r.get('execution_ref') != slot:
                counts['prompt_schema_or_identity_hash_mismatches'] += 1
                continue
            for case in cases:
                if r.get('media_identity') != expected[case]:
                    counts['different_media_pairs'] += 1
                    continue
                matches[case].append({'job': str(job.resolve()), 'sha256': fingerprint(job),
                                      'ledger': str(p.resolve()), 'ledger_sha256': fingerprint(p),
                                      'outcome': r.get('outcome'), 'slot_ref': slot})
    result = {'counts': dict(counts), 'budget_files_inspected': len(budgets),
              'matched_cases': len(matches), 'cases': 36, 'matches': dict(matches),
              'unmatched_cases': sorted(set(expected) - set(matches)),
              'new_model_calls': 0, 'references_read_for_scoring': False,
              'selection_if_reused': 'First sorted matching job path, before examining its predicted label; retain failed outcomes.',
              'roots': [str(p.resolve()) for p in roots],
              'forward_inputs_sha256': fingerprint(forward / 'inputs.json')}
    output.mkdir(parents=True)
    save_json(output / 'results.json', result)
    (output / 'run.log').write_text('Searched exact-identity durable ledgers; validated slot hashes before any label scoring.\n')
    (output / 'llm-histories.log').write_text('Zero model calls.\n')
    save_json(output / 'completion_seal.json', {'files': {str(p.relative_to(output)): fingerprint(p) for p in sorted(output.iterdir()) if p.is_file()},
              'auditor_sha256': fingerprint(__file__)})
    print({k: v for k, v in result.items() if k not in ('matches', 'unmatched_cases', 'roots')}, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--search-root', type=Path, action='append', required=True)
    args = parser.parse_args()
    audit(args.forward_dir.resolve(), args.search_root, args.output_dir.resolve())
