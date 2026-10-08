"""Saved-data analysis and zero-network replay of the one-case refinement pilot."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from critical.core.decision.artifacts import save_json
from critical.core.decision.robust.models import restore_program
from critical.core.decision.robust.refinement import validate_refinement
from critical.core.decision.robust.decomposition import validate_broad
from run.calitree_forced_decomposition import execute

OUTPUT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((OUTPUT/'manifest.json').read_text())
    results = json.loads((OUTPUT/'results.json').read_text())
    budget = json.loads((OUTPUT/'budget.json').read_text())
    assert manifest['version'] == 'nested-evidence-small-seeded-v1'
    assert len(manifest['cases']) == 1 and budget['calls'] <= 150
    assert budget['completion_tokens_or_reserved'] <= 192000
    previous=manifest['previous_small_attempt']
    assert previous['calls']+budget['calls'] <= 150
    assert previous['completion_tokens_or_reserved']+budget['completion_tokens_or_reserved'] <= 192000
    for rel, expected in manifest['code_hashes'].items():
        assert sha256((OUTPUT/'source_snapshot'/rel).read_bytes()).hexdigest() == expected
        assert sha256(Path(rel).read_bytes()).hexdigest() == expected, 'Use frozen sources for replay: '+rel
    raw = manifest['cases'][0]
    for key, path in raw['evidence'].items():
        assert sha256(Path(path).read_bytes()).hexdigest() == raw['image_hashes'][key]
    original = restore_program(raw['broad_seed'])
    jobs = {p.stem: json.loads(p.read_text()) for p in (OUTPUT/'jobs').glob('*.json')}
    ordered = [jobs[k] for k in budget['attempted_slots'] if k in jobs]
    final_started = False
    for job in ordered:
        if job['phase'] == 'final':
            final_started = True
        if final_started:
            assert job['phase'] == 'final' and job['stage'] == 'check'
        if job['stage'] in ('compile_refinement','audit_pair','audit','check','visual_discovery'):
            assert 'reference_label' not in job['payload'] and 'feedback' not in job['payload']
        if job['stage'] == 'visual_discovery':
            assert not {'agreement','label_distribution','rejected_diagnostics'} & job['payload'].keys()
        if job['stage'] == 'check' and job['payload'].get('contract') == 'nested-evidence-readout-v1':
            images = sum(m['type'] == 'image' for m in job['media_identity'])
            assert images == (2 if job['payload']['node']['role'] == 'support' else 0)
            if job['outcome'] == 'completed' and 'observation_validation_error' not in job:
                assert job['parsed']['used_dependency_ids'] == job['payload']['node']['dependencies']
    rows = []
    for arm in manifest['arms']:
        local = json.loads((OUTPUT/'frozen'/arm/'0.json').read_text()) if (OUTPUT/'frozen'/arm/'0.json').exists() else {}
        row = results['cases'].get(raw['id'], {}).get(arm, {})
        detail = {'arm':arm, 'result':row}
        if 'nodes' in local:
            saved = local['nodes']['leaf:'+raw['id']]['result']
            seed, selected = (restore_program(saved[k]) for k in ('seed','selected'))
            validator = validate_refinement if arm == 'decomposed-greedy' else validate_broad
            validator(seed, original); validator(selected, original)
            for candidate in saved['candidates'].values():
                restore_program(candidate)
            events = saved['lineage'][-1].get('events', [])
            old = {n.id:n for n in seed.nodes}
            detail.update(seed_ref=seed.ref, selected_ref=selected.ref, program_changed=seed.ref != selected.ref,
                seed_checks=len(seed.nodes), selected_checks=len(selected.nodes),
                selected_nodes=selected.to_dict()['nodes'],
                selected_audit=saved['candidates'].get(selected.ref, {}).get('audit', {}),
                added_supports=[n.id for n in selected.nodes if n.role=='support' and n.id not in old],
                nested_supports=[n.id for n in selected.nodes if n.role=='support' and n.dependencies],
                repair_transactions=[h for h in saved['lineage'] if 'transaction' in h],
                visual_discovery=[e['visual_discovery'] for e in events if 'visual_discovery' in e],
                diagnostic_only_candidates=[r for r,c in saved['candidates'].items() if 'diagnostic' in c],
                gradient_nodes=[list(e.get('gradients',{})) for e in events if 'gradients' in e])
        rows.append(detail)
    usage = {'calls':budget['calls'], 'completion_tokens_charged':budget['completion_tokens_or_reserved'],
        'completion_tokens_reported':sum(int(j.get('response',{}).get('completionTokens',0)) for j in jobs.values()),
        'input_tokens':budget['input_tokens'], 'outcomes':dict(Counter(j['outcome'] for j in jobs.values())),
        'stages':dict(Counter(j['stage'] for j in jobs.values())), 'returned_models':results.get('returned_models',[])}
    usage.update(cumulative_calls=previous['calls']+budget['calls'],
        cumulative_completion_tokens_charged=previous['completion_tokens_or_reserved']+budget['completion_tokens_or_reserved'])
    save_json(OUTPUT/'component_analysis.json',rows)
    save_json(OUTPUT/'usage_summary.json',usage)
    lines=['# One-case nested evidence repair: saved-seed corrective results','',
        'Instruction: '+raw['instruction'], 'Reference: `'+raw['target']+'`.',
        'One previously observed local fitting case; five fresh final draws per seed and selected program. '
        'All compilation, checking, auditing and visual discovery are label-blind; backward/proposal requests may use the label. '
        'Discovery uses GPT-6 Luna only, so this test does not measure diversity benefits from other model families.',
        'The first 38-call attempt had invalid compilation. It is preserved separately; this corrective test explicitly promotes the historical label-free decomposition seed, obtains a fresh audit, and deducts first-attempt usage from the same ceiling. No historical optimization feedback, old audit approval, or final traces enter this search.',
        '', 'Status: '+results['status'],'',
        '| Method | Seed → selected reference matches / 5 | Selected usable / 5 | Minimum reported confidence | Selected checks | Program changed? | Final status |',
        '|---|---:|---:|---:|---:|---|---|']
    for d in rows:
        r=d['result'];a=r.get('final',{}).get('seed',{});b=r.get('final',{}).get('selected',{})
        confidences=[o['confidence'] for t in b.get('traces',[]) for o in t['observations'] if o['queried'] and o['confidence'] is not None]
        lines.append(f"| {d['arm']} | {round(5*a.get('agreement',0))} → {round(5*b.get('agreement',0))} | {round(5*b.get('coverage',0))} | {min(confidences) if confidences else 'unavailable'} | {d.get('selected_checks','unavailable')} | {d.get('program_changed','unavailable')} | {r.get('support_status','unattempted')} |")
    lines += ['', 'Reference matches measure agreement with the saved partial label. Usable answers include incorrect answers. '
        'Confidence is model self-report; check consistency is modal repeat agreement. Matching the label does not certify atomic correctness.', '']
    for d in rows:
        lines += ['## '+d['arm'], '', 'Final acceptance: '+json.dumps(d['result'].get('acceptance',{})),
            'Selected audit: '+json.dumps(d.get('selected_audit',{})),
            'Added supports: '+json.dumps(d.get('added_supports',[])),
            'Nested support dependencies: '+json.dumps(d.get('nested_supports',[])),
            'Diagnostic-only parent candidates: '+json.dumps(d.get('diagnostic_only_candidates',[])), '',
            '| Component | Role / evidence inputs | Question | Final states | Repeat consistency |',
            '|---|---|---|---|---:|']
        stats=d['result'].get('final',{}).get('selected',{}).get('nodes',{})
        for n in d.get('selected_nodes',[]):
            s=stats.get(n['id'],{});inputs='images' if n['role']=='support' else 'saved evidence only' if d['arm']=='decomposed-greedy' else 'images'
            if n['dependencies']:inputs+='; dependencies '+', '.join(n['dependencies'])
            lines.append('| '+' | '.join([n['id'],n['role']+' / '+inputs,n['question'].replace('|','/'),json.dumps(s.get('states',{})),str(s.get('consistency'))])+' |')
        lines += ['', '### Repair history','']
        for h in d.get('repair_transactions',[]):
            lines += [f"- Round {h['round']+1}, batch {h['batch']+1}: {h['transaction']['reason']}",
                '  Result: '+json.dumps({k:v for k,v in h.items() if k not in ('transaction','parent')})]
        if not d.get('repair_transactions'):lines += ['No repair transactions recorded.']
        lines += ['', '### Visual discovery hypotheses','']
        for review in d.get('visual_discovery',[]):
            for hypothesis in review['findings']:
                lines.append('- '+hypothesis['question']+' — '+hypothesis['rationale'])
    lines += ['', '## Usage','',json.dumps(usage,indent=2),'',
        f"Search/confirmation has {manifest['max_calls']-50} remaining calls; 50 calls and 51,200 tokens remain reserved for final comparison. "
        'Budget-limited search is an explicit outcome. Final draws never trigger more optimization. '
        'A single failure-selected case cannot establish generalization.']
    (OUTPUT/'analysis.md').write_text('\n'.join(lines)+'\n')
    verification={'label_isolation':True,'image_hashes_verified':True,'program_hashes_verified':True,
        'sources_verified':True,'final_after_frozen_selection':True,'calls_within_ceiling':True,
        'tokens_within_ceiling':True,'zero_call_replay':None}
    if results['status']=='completed':
        with tempfile.TemporaryDirectory(prefix='calitree-small-replay-') as directory:
            clone=Path(directory)/'run'
            shutil.copytree(OUTPUT,clone,ignore=shutil.ignore_patterns('llm-histories.log','console.log','source_snapshot'))
            contacted=[]
            def forbid(cap):
                contacted.append(cap)
                raise AssertionError('Completed replay must not contact a provider')
            replay=execute(clone,manifest,forbid)
            assert not contacted and replay['budget']['calls']==budget['calls']
            assert replay['cases']==results['cases']
        verification['zero_call_replay']=True
    save_json(OUTPUT/'protocol_verification.json',verification)
    print(json.dumps({'status':results['status'],'usage':usage,'verification':verification}))


if __name__=='__main__':main()
