"""Resume the frozen fifty-case run with independent trajectories in parallel."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import random

from run.robust_prompt_repair_pilot import (
    CallStore, candidate_issue, digest, improves, save,
)
from run.robust_prompt_repair_50 import (
    FiftyPilot, prepare_cases, write_report,
)
from vejudge.lm_engine.gate import require_live


class ParallelFiftyPilot(FiftyPilot):
    def search_one(self, case, arm):
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
                old = self.evaluate(case, arm, rnd, 'confirm-parent', prompt,
                                    self.config['confirmation_repeats'])
                new = self.evaluate(case, arm, rnd, 'confirm-candidate', candidate,
                                    self.config['confirmation_repeats'])
                confirmation = {'parent': old, 'candidate': new}
                accepted = improves(old, new)
            decision = {'case_id': cid, 'arm': arm, 'round': rnd,
                        'parent_sha256': digest(prompt),
                        'candidate_sha256': digest(candidate),
                        'screening_improved': screening,
                        'candidate_issue': issue, 'confirmation': confirmation,
                        'accepted': accepted,
                        'selected_prompt': candidate if accepted else prompt}
            save(decision_path, decision)
            (folder / 'candidate.txt').write_text(candidate)
            (folder / 'candidate.diff').write_text(''.join(difflib.unified_diff(
                prompt.splitlines(True), candidate.splitlines(True),
                fromfile='parent', tofile='candidate')))
            prompt = decision['selected_prompt']
            self.log(f'{cid} {arm} round {rnd}: accepted={accepted}; '
                     f'cost=${self.store.spent:.3f}')
        return cid, arm, prompt

    def search(self, workers=3):
        frozen_path = self.out / 'frozen_prompts.json'
        if frozen_path.exists():
            manifest = json.loads((self.out / 'frozen_manifest.json').read_text())
            if digest(frozen_path.read_bytes()) != manifest['sha256']:
                raise ValueError('Frozen prompts changed')
            return json.loads(frozen_path.read_text())
        jobs = [(c, arm) for c in self.cases for arm in ('single', 'repeated')]
        random.Random(self.config['seed']).shuffle(jobs)
        frozen = {c['case_id']: {'unchanged': c['prompt']} for c in self.cases}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self.search_one, case, arm) for case, arm in jobs]
            for future in as_completed(futures):
                cid, arm, prompt = future.result()
                frozen[cid][arm] = prompt
        save(frozen_path, frozen)
        save(self.out / 'frozen_manifest.json', {
            'sha256': digest(frozen_path.read_bytes()),
            'time': datetime.now(timezone.utc).isoformat(),
            'orchestrator': 'parallel_fifty_case_resume'})
        return frozen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--live', action='store_true')
    args = p.parse_args()
    if args.workers < 1 or args.workers > 4:
        p.error('workers must be 1..4')
    out = args.output_dir.resolve()
    config = json.loads((out / 'run_config.json').read_text())
    cases = prepare_cases(out, seed=config['seed'])
    if digest((out / 'cases.json').read_bytes()) != config['cases_sha256']:
        raise ValueError('Frozen cases changed')
    orchestration = {'script_sha256': digest(Path(__file__).read_bytes()),
                     'workers': args.workers,
                     'resumes_frozen_run_config_sha256': digest((out / 'run_config.json').read_bytes())}
    orchestration_path = out / 'orchestrator_config.json'
    if orchestration_path.exists():
        if json.loads(orchestration_path.read_text()) != orchestration:
            raise ValueError('Parallel orchestration changed')
    else:
        save(orchestration_path, orchestration)
    require_live(args.live, context='Fifty-case repeated GEPA comparison resume')
    store = CallStore(out, config)
    store.connect()
    pilot = ParallelFiftyPilot(out, config, cases, store)
    frozen = pilot.search(args.workers)
    pilot.final(frozen)
    summary = write_report(out, cases, config)
    pilot.log(f"Complete: {summary['usage']['completed_calls']} calls, "
              f"${summary['usage']['estimated_list_cost_usd']:.3f}")


if __name__ == '__main__':
    main()
