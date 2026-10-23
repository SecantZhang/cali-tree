"""Audit completed frozen AURORA collection, budgets, payloads and gate replay."""
import argparse
from collections import Counter
from contextlib import redirect_stdout
import io
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.decision import bound_compiler_v3 as compiler, bound_evidence_v2 as physical, semantic_interpretation_v5 as interpretation
from critical.core.decision.compiler import media_inputs
from critical.core.optimization.prompt.calitree import task_coverage as task
from run.collect_calitree_aurora_pilot_v29r1 import verify_execution, report
from run.calitree_aurora_pilot_v29 import read, fingerprint, IDENTITY, CAPS


def audit(out):
    plan=verify_execution(out);cases=read(out/'inputs.json');instructions=read(out/'instructions.json')
    budget=read(out/'ledger/budget.json');jobs={p.stem:read(p)for p in (out/'ledger/jobs').glob('*.json')}
    assert len(jobs)==budget['calls']==len(budget['attempted_slots']) and set(jobs)==set(budget['attempted_slots'])
    assert budget['limits']['max_calls']==plan['max_requests'] and budget['limits']['max_completion_tokens']==plan['max_completion_tokens']
    assert budget['calls']+plan['prior_local_attempts']<=272
    assert budget['completion_tokens_or_reserved']+plan['prior_reserved_completion_tokens']<=2392064
    by_case={c['case']:c for c in cases};seen=Counter();usage_input=usage_output=reserved=0
    for key,row in jobs.items():
        stage=row['stage'];case_id=row['case_id'];seen[stage]+=1
        if case_id.startswith('compile-'):
            instruction=instructions[case_id.removeprefix('compile-')]['instruction']
            assert stage in ('bound_instruction_v3','bound_instruction_v3_repair')
            expected_payload={'instruction':instruction,'max_checks':physical.MAX_CHECKS}
            template=compiler.TEMPLATE.read_text();schema=compiler.schema_for(instruction);media=[];cap=CAPS['compile']
            if stage.endswith('_repair'):
                initial=[r for r in jobs.values()if r['case_id']==case_id and r['stage']=='bound_instruction_v3']
                assert len(initial)==1 and initial[0]['outcome']=='completed'
                assert row['payload']['draft']==initial[0]['parsed']
                expected_payload.update(draft=row['payload']['draft'],validation_error=row['payload']['validation_error'])
                template=compiler.REPAIR_TEMPLATE+template
        else:
            case=by_case[case_id];saved=read(out/'collection/cases'/(case_id+'.json'))
            if stage=='flat_judge':
                expected_payload={'instruction':case['instruction']};template=(task.TEMPLATES/'regular.txt').read_text()
                schema=task.SCHEMA;media=media_inputs(case['evidence']);cap=CAPS['regular']
                if saved['regular_error'] is None:
                    assert saved['regular']==row['parsed'] and saved['regular_execution_ref']==key
            elif stage=='bound_visual_observation_v2':
                program=saved['program'];pair=physical.image_identity(case['evidence'])[1]
                expected_payload={'program':program,'image_pair_ref':pair};schema=physical.observation_schema(program,pair)
                template=(physical.TEMPLATES/'observe.txt').read_text();media=media_inputs(case['evidence']);cap=CAPS['observe']
                if saved['extraction_error'] is None:
                    assert row['parsed']==saved['observation'];physical.validate_observation(program,row['parsed'],pair)
            elif stage=='instruction_relative_interpretation':
                program=saved['program'];obs=saved['observation']
                if obs is None:
                    observed=[r for r in jobs.values()if r['case_id']==case_id and r['stage']=='bound_visual_observation_v2']
                    assert len(observed)==1;obs=observed[0]['parsed']
                pair=physical.image_identity(case['evidence'])[1]
                expected_payload=interpretation.make_input(program,obs,pair);schema=interpretation.schema(expected_payload)
                template=interpretation.PROMPT;media=[];cap=CAPS['interpret']
                if saved['extraction_error'] is None:
                    assert row['parsed']==saved['interpretation'];interpretation.validate(expected_payload,row['parsed'])
            else:raise AssertionError('Unapproved request stage: '+stage)
        media_identity=[{'type':m['type'],'sha256':fingerprint(m['path'])}if m['type']=='image' else m for m in media]
        assert row['payload']==expected_payload and row['media_identity']==media_identity and row['slot']=='once' and row['max_tokens']==cap
        assert key==digest([IDENTITY,case_id,stage,expected_payload,schema,template,media_identity,'once',cap])
        if 'response' in row:
            response=row['response'];assert response['model']==IDENTITY['model']
            usage_input+=response['promptTokens'];usage_output+=response['completionTokens'];reserved+=response['completionTokens']
        else:reserved+=row['max_tokens']
    assert seen['bound_instruction_v3']==len(instructions) and seen['flat_judge']==len(cases)
    assert seen['bound_instruction_v3_repair']<=len(instructions)
    assert seen['bound_visual_observation_v2']<=len(cases) and seen['instruction_relative_interpretation']<=len(cases)
    assert usage_input==budget['input_tokens'] and reserved==budget['completion_tokens_or_reserved']
    for key in instructions:
        saved=read(out/'collection/compilations'/(key+'.json'))
        if saved['compilation'] is not None:
            value=saved['compilation'];row=jobs[value['execution_ref']]
            assert compiler.checked_program(instructions[key]['instruction'],row['parsed'])==value['program']
    for case in cases:
        saved=read(out/'collection/cases'/(case['case']+'.json'))
        assert saved['case']==case['case']
    before=read(out/'collection/results.json')
    with redirect_stdout(io.StringIO()):replayed=report(out)
    assert replayed==before
    pricing=read(out/'estimate.json')['pricing']
    result={'passed':True,'outputs':len(cases),'source_groups':len({c['source_group']for c in cases}),
            'actual_api_attempts':budget['calls'],'prior_local_pre_http_failures':plan['prior_local_attempts'],
            'combined_attempts':budget['calls']+plan['prior_local_attempts'],'stage_counts':dict(seen),
            'completed_api_responses':sum(r['outcome']=='completed'for r in jobs.values()),
            'input_tokens':usage_input,'completion_tokens':usage_output,
            'combined_completion_tokens_or_reserved':reserved+plan['prior_reserved_completion_tokens'],
            'approved_request_limit':272,'approved_completion_token_limit':2392064,
            'standard_rate_cost_estimate_usd':round((usage_input*pricing['input_per_million']+usage_output*pricing['output_per_million'])/1e6,6),
            'all_input_cache_write_rate_cost_estimate_usd':round((usage_input*pricing['cache_write_per_million']+usage_output*pricing['output_per_million'])/1e6,6),
            'cost_note':'Usage priced at the reviewed rates; not an invoice and does not resolve provider cache accounting.',
            'frozen_payload_hashes_verified':True,'all_six_gates_replayed':True,'new_fitting':False,'case_replacements':0}
    save_json(out/'collection/verification.json',result)
    save_json(out/'completion_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='completion_seal.json'},'auditor_sha256':fingerprint(__file__)})
    print(result,flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    audit(p.parse_args().output_dir.resolve())
