from copy import deepcopy
import json

import pytest

from run import calitree_aurora_pilot_v29 as pilot
from run import collect_calitree_aurora_pilot_v29 as collection


def tasks():
    result={}
    for category in pilot.AURORA_TASKS:
        for i in range(4):
            uid=f'{category}-{i}'
            result[uid]={'task_uid':uid,'task':category,'source_group':uid,'used':i>=2,
                         'outputs':[{'editor':model,'instruction':f'Instruction {uid}'}for model in pilot.AURORA_MODELS]}
    return result


def test_sampling_prefers_unused_is_balanced_and_has_no_label_selection():
    data=tasks();chosen,shortages=pilot.select_tasks(data,allow_used=True)
    assert not shortages and len(chosen)==16 and not any(t['used']for t in chosen)
    for t in data.values():
        for output in t['outputs']:output['reference']='yes';output['human_score']=2
    changed,_=pilot.select_tasks(dict(reversed(list(data.items()))),allow_used=True)
    assert [t['task_uid']for t in chosen]==[t['task_uid']for t in changed]


def test_recent_exclusions_and_duplicate_source_pixels_are_hard_constraints():
    data=tasks();data['ag-1']['source_group']='ag-0'
    chosen,shortages=pilot.select_tasks(data,allow_used=True,excluded_groups={'clevr-0','clevr-1','clevr-2','clevr-3'})
    assert shortages['clevr']['available']==0
    assert len({t['source_group']for t in chosen})==len(chosen)
    assert not any(t['task']=='clevr'for t in chosen)
    assert any(t['used']for t in chosen if t['task']=='ag')


def test_missing_category_or_model_is_reported_not_silently_replaced():
    data=tasks()
    for t in data.values():
        if t['task']=='emu':t['used']=True
    chosen,shortages=pilot.select_tasks(data)
    assert shortages['emu']['available']==0 and len(chosen)==14
    for t in data.values():
        if t['task']=='ag':t['outputs'].pop()
    _,shortages=pilot.select_tasks(data,allow_used=True)
    assert shortages['ag']['available']==0


def test_estimate_covers_one_repair_per_instruction_and_all_per_output_stages():
    usage={s:{'mean_input':1000,'mean_output':100,'p90_input':2000,'p90_output':200}for s in('compile','observe','interpret','regular')}
    cost=pilot.estimate(80,16,usage)
    assert cost['expected_requests']==256 and cost['max_requests']==272
    assert cost['max_completion_tokens']==2392064
    assert cost['completion_cap_cost_usd']==pytest.approx(1.196032)
    assert cost['scenarios']['historical_mean']['estimated_usd']==pytest.approx(.0384)


def test_paid_collection_requires_explicit_live_before_reading_credentials(tmp_path):
    with pytest.raises(ValueError,match='authorization'):
        collection.collect(tmp_path)
    assert not list(tmp_path.iterdir())


def test_collection_reuses_compilation_keeps_labels_out_and_resumes_without_retries(tmp_path,monkeypatch):
    inputs=[{'case':f'P{i}','instruction':'Same instruction','compilation_ref':'same',
             'evidence':{'source_image':'source.png','edited_image':f'edit{i}.png'},'reference':'DO NOT SEND'}for i in range(2)]
    (tmp_path/'inputs.json').write_text(json.dumps(inputs))
    (tmp_path/'instructions.json').write_text(json.dumps({'same':{'instruction':'Same instruction'}}))
    events=[]
    class Compiler:
        def __init__(self,calls):pass
        def compile(self,instruction,**kwargs):
            events.append(('compile',instruction));return {'program':{'instruction':instruction}}
    class Pipeline:
        def __init__(self,calls):pass
        def extract(self,program,evidence,**kwargs):
            events.append(('extract',program));return {'obs':1},{'interp':1},'pair'
    class Calls:
        def call(self,stage,payload,schema,**kwargs):
            assert payload=={'instruction':'Same instruction'}
            events.append((stage,payload));return {'label':'partial','rationale':'test'},'ref'
    monkeypatch.setattr(collection,'BoundInstructionCompilerV3',Compiler)
    monkeypatch.setattr(collection,'BoundEvidencePipeline',Pipeline)
    collection.collect_with_calls(tmp_path,Calls())
    assert [e[0]for e in events].count('compile')==1
    assert [e[0]for e in events].count('flat_judge')==2
    assert [e[0]for e in events].count('extract')==2
    saved=deepcopy(events);collection.collect_with_calls(tmp_path,Calls());assert events==saved
    assert len(list((tmp_path/'collection/cases').glob('*.json')))==2


def test_extraction_failure_retains_regular_fallback_record(tmp_path,monkeypatch):
    case={'case':'P1','instruction':'Task','compilation_ref':'c','evidence':{'source_image':'s','edited_image':'e'}}
    (tmp_path/'inputs.json').write_text(json.dumps([case]));(tmp_path/'instructions.json').write_text(json.dumps({'c':{'instruction':'Task'}}))
    class Compiler:
        def __init__(self,calls):pass
        def compile(self,*args,**kwargs):raise ValueError('invalid compiler draft')
    class Calls:
        def call(self,*args,**kwargs):return {'label':'no','rationale':'test'},'regular-ref'
    monkeypatch.setattr(collection,'BoundInstructionCompilerV3',Compiler)
    collection.collect_with_calls(tmp_path,Calls())
    row=json.loads((tmp_path/'collection/cases/P1.json').read_text())
    assert row['regular_execution_ref']=='regular-ref' and row['regular']['label']=='no'
    assert row['extraction_error']=='CompilationFailed:ValueError'


def test_metrics_keep_unresolved_cases_and_group_bootstrap_by_source():
    rows=[{'source_group':str(i//5),'reference':i%3,'regular':-1,'routes':{}}for i in range(80)]
    result=collection.metrics(rows,'regular');interval=collection.bootstrap_accuracy(rows,'regular',draws=100)
    assert result['total']==80 and result['unresolved']==80 and result['accuracy']==0
    assert interval['source_clusters']==16 and interval['percentile_95']==[0,0]
