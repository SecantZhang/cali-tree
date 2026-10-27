"""Fit a12/24-term rubric on source-held semantic interactions.

All interaction candidates come from the selected fold's already fitted small
semantic trees. No held labels choose the basis, coefficients or strength.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT, admissible, f32
from critical.core.calibration.rubric_score_v82 import RubricScore
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.verify_calitree_semantic_residual_v105 import load, fold_arrays
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_accuracy_headroom_v37 import accuracy

CONFIGS = [(count, reg) for count in (12, 24) for reg in (.1, 1.)]


def basis(matrix, names, clauses):
    result=np.ones((len(matrix),len(clauses)),dtype=float)
    for j,clause in enumerate(clauses):
        for term in clause['conditions']:
            assert term['greater'] is True
            result[:,j] *= matrix[:,names.index(term['feature'])].astype(np.float32)>f32(term['border'])
    return result


def readable_terms(compiled):
    descriptions={}; conditions={}
    for j,clause in enumerate(compiled['clauses']):
        name='semantic_condition_'+str(j+1)
        descriptions[name]=' AND '.join(compiled['feature_descriptions'][t['feature']]+(' > '+str(t['border']) if t['feature'] in SUPPORT else '') for t in clause['conditions'])
        conditions[name]=clause['conditions']
    return descriptions,conditions


def boolean_artifact(model, conditions):
    """Absorb the0/1 normalization into an exact readable intercept/effect."""
    intercept=model.coefficients[0].copy(); terms=[]
    for row,col in enumerate(model.columns,1):
        low=float(np.clip(-model.means[col]/model.scales[col],-5.,5.)); high=float(np.clip((1-model.means[col])/model.scales[col],-5.,5.))
        intercept += low*model.coefficients[row]
        terms.append({'conditions':conditions[model.names[col]],'coefficients_no_partial_yes':((high-low)*model.coefficients[row]).tolist()})
    return {'version':'sparse-semantic-interactions-v113','strength':model.strength,'teacher_log_weight':1+model.strength*(model.temperature-1),
        'intercept_no_partial_yes':(model.strength*intercept).tolist(),
        'terms':[{'conditions':t['conditions'],'coefficients_no_partial_yes':(model.strength*np.asarray(t['coefficients_no_partial_yes'])).tolist()} for t in terms],
        'equation':'teacher_log_weight*log(max(teacher_support,1e-9)) + intercept + sum(coefficients for each satisfied semantic conjunction). Largest class score wins, with No/Partial/Yes tie order.',
        'guard':'An override still requires an affirmative local grade warrant or the existing independent-judge review reason.',
        'limit':'A learned human-grade correction, not a factual certificate or correctness probability.'}


def run(cache, cache_audit, source_study, verified, out):
    if out.exists():
        raise ValueError('Fresh sparse-interaction study required')
    prior=read(verified/'verification.json'); assert prior['passed'] and prior['accuracy']['correct']==227
    assert read(verified/'manifest.json')['study_manifest_sha256']==file_hash(source_study/'manifest.json')
    d=load(cache,cache_audit); names=d['names']; y=d['y']; examples=d['examples']
    protocol={'version':'source-held-sparse-interaction-rubric-v113','configs':CONFIGS,
        'basis':'Exact shared conditions from each selected contextual depth-two v103 model; that model used only genuine source-excluded fitting rows and original protection. Never use another fold or held labels to form the basis.',
        'fit':'Same available genuine OOS review rows plus actual original review inputs as labeled fitting anchors, equal weight per source. Original groups are already in fitting.12/24 selected binary conjunctions, regularization .1/1, fit-only strength with original veto.',
        'flow':'Same .8 review region, v72/v87 priority, exact observer binding and missing-observation fallback. Measure score-only and unchanged positive-warrant/independent-review guard.',
        'readability':'Absorb binary0/1 standardization/clipping into explicit clause effects and intercept. Check this formula against fitted probabilities before reporting results.',
        'denominator':276,'originals':99,'slots':144,'new_api_calls':0,'new_observer_calls':0,'reserved_sources_used':0,'serving_changed':False}
    out.mkdir(parents=True);save_json(out/'protocol.json',protocol);(out/'run.log').write_text('Source-held sparse interaction fits started.\n');(out/'llm-histories.log').write_text('No API, observer, encoder or reserved-source calls. Cached semantic facts only.\n')
    files=[Path(__file__),ROOT/'critical/core/calibration/semantic_polynomial_v111.py',ROOT/'critical/core/calibration/rubric_score_v82.py',ROOT/'run/verify_calitree_semantic_residual_v105.py']
    for p in files:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    originals=[r for bank in(1,2,3) for r in old_inputs(PREVIOUS,bank)[3]['local']];records=[];retention=[]
    for f in [f for f in read(STUDY/'folds.json') if f['candidate']=='boost_full_vision']:
        a=fold_arrays(d,f);folder=a['folder'];native=read(source_study/folder/'contextual_depth2-native.json');metadata=read(source_study/folder/'contextual_depth2.json')
        assert digest(native)==read(verified/folder/'rubric.json')['native_model_ref']
        compiled=compile_polynomial(native,metadata);descriptions,conditions=readable_terms(compiled);basis_names=list(descriptions)
        full=basis(a['full'],names,compiled['clauses']);T=basis(a['T'],names,compiled['clauses']);fit=a['fit'];protected=a['protected'];chosen=fit+protected
        assert len(set(chosen))==len(chosen) and set(chosen)<=set(a['train']) and not set(d['groups'][chosen]) & set(d['groups'][a['held']])
        train_X=np.concatenate([T[fit],full[protected]],axis=0);support=np.concatenate([a['oof'][fit],a['ps'][protected]],axis=0)
        for count,reg in CONFIGS:
            model=RubricScore(basis_names,regularization=reg,max_features=count).fit(train_X,y[chosen],support=support,groups=d['groups'][chosen],
                protected_X=full[protected],protected_y=y[protected],protected_support=a['ps'][protected])
            scores=model.predict_proba(full,support=a['ps']);proposed=np.argmax(scores,axis=1);simplified=boolean_artifact(model,conditions)
            equation=simplified['teacher_log_weight']*np.log(np.clip(a['ps'],1e-9,1.))+np.asarray(simplified['intercept_no_partial_yes'])
            for term in simplified['terms']:
                column=next(j for j,clause in enumerate(compiled['clauses']) if clause['conditions']==term['conditions'])
                equation += full[:,column,None]*np.asarray(term['coefficients_no_partial_yes'])
            from scipy.special import softmax
            assert np.allclose(softmax(equation,axis=1),scores,atol=1e-12,rtol=0) and np.array_equal(np.argmax(equation,axis=1),proposed)
            stem='terms'+str(count)+'_reg'+str(reg);artifact=model.artifact(descriptions);artifact.update(boolean_policy=simplified,basis_conditions=conditions,
                basis_ref=compiled['artifact_ref'],fit_cases=[examples[i]['case'] for i in fit],anchor_cases=[examples[i]['case'] for i in protected],observer_identity_ref=digest(d['profile']))
            save_json(out/folder/(stem+'.json'),artifact)
            for guarded in(False,True):
                candidate=stem+('_guarded' if guarded else '_score');p=a['current'].copy()
                for i in np.flatnonzero(a['actual'] & d['available']):
                    if not guarded or admissible(d['flags_by_row'][i],int(np.argmax(a['ps'][i])),int(d['regular'][i]),int(proposed[i])):
                        p[i]=proposed[i]
                assert np.all(p[:99]==y[:99]) and np.array_equal(p[~(a['actual']&d['available'])],a['current'][~(a['actual']&d['available'])])
                slots=int(sum(p[d['pos'][r['case']]]==r['reference'] for r in originals));assert slots==144
                save_json(out/folder/(candidate+'-predictions.json'),p.tolist());retention.append({'candidate':candidate,'fold':f['fold'],'original_correct':99,'slots_correct':slots,'terms':len(model.columns),'strength':model.strength})
                for i in a['held']:
                    records.append({**examples[i],'candidate':candidate,'fold':f['fold'],'prediction':int(p[i]),'baseline':int(a['current'][i]),'review':bool(a['actual'][i]),'local_available':bool(a['actual'][i]&d['available'][i])})
        save_json(out/'predictions.json',records);save_json(out/'retention.json',retention);print({'fold':f['fold'],'basis_terms':len(basis_names),'configs':4},flush=True)
    results={}
    for candidate in sorted({r['candidate'] for r in records}):
        rows=[r for r in records if r['candidate']==candidate];score=accuracy(rows,'prediction')
        results[candidate]={'accuracy':score,'baseline':accuracy(rows,'baseline'),'gains':sum(r['prediction']==r['reference']!=r['baseline'] for r in rows),'losses':sum(r['baseline']==r['reference']!=r['prediction'] for r in rows),
            'coverage':sum(r['covered'] for r in rows),'original_cases_retained':99,'original_slots_retained':144,'target_exceeded':score['correct']>=235}
    save_json(out/'results.json',results);save_json(out/'manifest.json',{'code_sha256':{str(p):file_hash(p) for p in files},'cache_audit_manifest_sha256':file_hash(cache_audit/'manifest.json'),
        'source_study_manifest_sha256':file_hash(source_study/'manifest.json'),'protocol_ref':digest(protocol),'targets_ref':digest(y.tolist())})
    (out/'run.log').write_text('Completed four sparse interaction fits and score/guarded arms; exact binary formula checked. No serving changes.\n');print(results,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('cache','cache-audit','source-study','verified','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.cache.resolve(),a.cache_audit.resolve(),a.source_study.resolve(),a.verified.resolve(),a.output_dir.resolve())
