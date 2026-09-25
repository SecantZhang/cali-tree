"""Offline checks for live pilot design and analysis; never contact a provider."""
import json
from pathlib import Path
import pytest
from run.assumptions_model_comparison import (SOURCE, base_jobs, make_job,
    metrics, paired_interval, request_settings)


def test_frozen_design_has_ten_tasks_unique_draws_and_no_labels_in_requests():
    bundles=json.loads(SOURCE.read_text())
    jobs=base_jobs(bundles)
    assert len({b['case']['task_uid'] for b in bundles})==10
    assert len(jobs)==1150
    assert len({j['id'] for j in jobs})==len(jobs)
    forbidden={'target_label','human_score','search_stats','confirmation_stats'}
    assert all(not forbidden.intersection(j) for j in jobs)
    for model in ['mini','luna']:
        assert len([j for j in jobs if j['model']==model and j['family']=='direct'])==100
        assert len([j for j in jobs if j['model']==model and j['family']=='fixed'])==320
    plans=[j for j in jobs if j['decomposition']]
    assert len(plans)==10
    assert all(j['images']==[] and j['user_text']==j['instruction'] for j in plans)


def test_settings_preserve_primary_comparison_and_omit_unsupported_temperature():
    mini=request_settings('gpt-5.4-mini','none')
    luna=request_settings('gpt-6-luna','none')
    assert {k:v for k,v in mini.items() if k!='model'}=={k:v for k,v in luna.items() if k!='model'}
    assert mini['temperature']==.3
    assert 'temperature' not in request_settings('gpt-6-luna','medium')


def test_invalid_predictions_count_against_accuracy_and_ties_are_explicit():
    cases=[{'case_id':f'C{i:02}','target_label':['no','partial','yes'][i%3]} for i in range(10)]
    predictions=[[{'valid':True,'label':c['target_label']} for _ in range(10)] for c in cases]
    perfect=metrics(cases,predictions)
    assert perfect['accuracy']==1 and perfect['all_ten_correct_cases']==10
    predictions[0]=[{'valid':True,'label':'no'}]*5+[{'valid':True,'label':'yes'}]*5
    predictions[1][0]={'valid':False,'label':'partial'}
    changed=metrics(cases,predictions)
    assert changed['accuracy']==pytest.approx(.94)
    assert changed['modal_ties']==1 and changed['invalid']==1
    assert changed['stable_cases']==8
    assert paired_interval(perfect,changed)['difference']==pytest.approx(-.06)


def test_pricing_configuration_survives_json_checkpoint_roundtrip():
    from run.assumptions_model_comparison import PRICES
    assert json.loads(json.dumps(PRICES))==PRICES


def test_generation_settings_do_not_leak_judging_targets():
    bundles=json.loads(SOURCE.read_text())
    original=bundles[0]['case']
    changed={**original,'human_score':0,'target_label':'no','model':'different-editor'}
    for decomposition in [False,True]:
        a=make_job(original,'luna','probe',0,'frozen prompt',decomposition=decomposition)
        b=make_job(changed,'luna','probe',0,'frozen prompt',decomposition=decomposition)
        assert a==b


def test_vision_requests_include_source_then_edited_and_no_scores(monkeypatch):
    import run.assumptions_model_comparison as pilot
    case=json.loads(SOURCE.read_text())[0]['case']
    monkeypatch.setattr(pilot,'media',lambda path:{'type':'image_url','image_url':{'url':path}})
    job=make_job(case,'luna','direct',0,'frozen rubric')
    messages=pilot.request_messages(job)
    assert messages[0]=={'role':'system','content':'frozen rubric'}
    blocks=messages[1]['content']
    assert len(blocks)==3
    assert blocks[1]['image_url']['url']==case['source_local_image']
    assert blocks[2]['image_url']['url']==case['edited_local_image']
    assert 'human_score' not in str(messages)


def test_full_analysis_writes_seven_arms_and_four_grouped_tree_results(tmp_path,monkeypatch):
    import run.assumptions_model_comparison as pilot
    bundles=json.loads(SOURCE.read_text())
    plans={b['case']['case_id']:b['tree']['decomposition'] for b in bundles}
    jobs=base_jobs(bundles)
    for b in bundles:
        for model in pilot.MODELS:
            for rep in range(10):
                jobs.extend(pilot.requirement_jobs(b['case'],model,'regenerated',rep,plans[b['case']['case_id']]['requirements']))
    targets={b['case']['case_id']:b['case']['target_label'] for b in bundles}
    rows={}
    for job in jobs:
        parsed={'valid':True,'label':targets[job['case_id']] if job['family'].startswith('direct') else 'yes','rationale':'synthetic offline fixture'}
        if job['decomposition']:
            parsed=plans[job['case_id']]
        rows[job['id']]={'request':job,'parsed':parsed,'response':{'model':pilot.MODELS[job['model']],'usage':{'prompt_tokens':1,'completion_tokens':1}},'estimated_list_cost_usd':0}
    monkeypatch.setattr(pilot,'ROOT',tmp_path.parent)
    result=pilot.summarize(tmp_path,bundles,rows,plans)
    assert len(result)==7
    assert result['mini_direct']['accuracy']==1
    assert result['luna_fixed']['accuracy']==.3
    for arm in ['mini_fixed','luna_fixed','mini_regenerated','luna_regenerated']:
        assert (tmp_path/arm/'learned_trees.json').exists()
    assert (tmp_path/'report.md').exists()
