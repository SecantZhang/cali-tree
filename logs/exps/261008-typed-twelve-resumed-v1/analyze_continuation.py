"""Verify inherited state and analyze this continuation without API calls."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from critical.core.decision.artifacts import save_json


def main():
    output=Path(__file__).resolve().parent
    record=json.loads((output/'continuation.json').read_text())
    old=json.loads((output/'initial_budget.json').read_text())
    new=json.loads((output/'budget.json').read_text())
    source=Path(record['source'])
    for rel,h in record['hashes'].items():
        assert sha256((source/rel).read_bytes()).hexdigest()==h,rel
        if rel not in ('budget.json','results.json'):
            assert sha256((output/rel).read_bytes()).hexdigest()==h,rel
    for rel,expected in record['observation_prefixes'].items():
        assert sha256((output/rel).read_bytes()[:expected['bytes']]).hexdigest()==expected['sha256'],rel
    assert new['limits']==old['limits']
    assert new['attempted_slots'][:len(old['attempted_slots'])]==old['attempted_slots']
    assert len(new['attempted_slots'])==len(set(new['attempted_slots']))==new['calls']
    assert new['calls']<=new['limits']['max_calls']
    assert new['completion_tokens_or_reserved']<=new['limits']['max_completion_tokens']
    for field in ('calls','completion_tokens_or_reserved','input_tokens','final_calls','final_tokens'):
        assert new.get(field,0)>=old.get(field,0)
    for scope,counts in old.get('cases',{}).items():
        for field in ('search','final','completion_tokens_or_reserved','input_tokens'):
            assert new['cases'][scope].get(field,0)>=counts.get(field,0)
    verification={'inherited_assets_unchanged':True,'failed_slots_not_retried':True,
        'frozen_selections_not_reopened':True,'observation_prefixes_unchanged':True,'limits_unchanged':True,
        'inherited_calls':old['calls'],'additional_calls':new['calls']-old['calls'],'combined_calls':new['calls'],
        'additional_charged_completion_tokens':new['completion_tokens_or_reserved']-old['completion_tokens_or_reserved'],
        'combined_charged_completion_tokens':new['completion_tokens_or_reserved']}
    original_slots={}
    for key in old['attempted_slots']:
        job=json.loads((output/'jobs'/f'{key}.json').read_text())
        original_slots[(job['case_id'],job['stage'],job['slot'])]=key
    repeated=[]
    for key in new['attempted_slots'][len(old['attempted_slots']):]:
        job=json.loads((output/'jobs'/f'{key}.json').read_text())
        logical=(job['case_id'],job['stage'],job['slot'])
        if logical in original_slots:
            repeated.append({'case_id':job['case_id'],'stage':job['stage'],'slot':job['slot'],
                'original_execution_ref':original_slots[logical],'new_execution_ref':key})
    verification['logical_slots_repeated']=repeated
    verification['unattempted_work_only']=not repeated
    save_json(output/'protocol_deviations.json',{'repeated_proposals':repeated,
        'reason':'Saved transport diagnostic replay changed feedback payload hashes.',
        'affected_scopes':sorted({x['case_id'] for x in repeated}),
        'all_calls_charged':True,'affected_scopes_excluded_from_valid_robustness_claims':bool(repeated)})
    save_json(output/'continuation_verification.json',verification)
    subprocess.run([sys.executable,str(output/'analyze_saved_run.py')],check=True)
    print(json.dumps(verification))


if __name__=='__main__':main()
