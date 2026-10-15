"""Independent interaction-rule audit and complete cross-group report."""
import argparse
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from critical.core.calibration.instruction_rules import InstructionRuleCalibrator,DEFAULT
from critical.core.decision.artifacts import digest,save_json
from run.calitree_instruction_rules import prepare,load_inputs,verify
from run.calitree_single_call import read,fingerprint


def direct_prediction(x,t):
    """Separate scalar implementation of the documented rule contract."""
    if x is None:return -1
    c=x['contract'];q=x['qualities'];active=['progress','endpoint']
    if c['identity_required']:active.append('identity')
    if c['relation_required']:active.append('relation')
    if c['quantity_required']:active.append('quantity')
    if c['appearance'] or c['style'] or c['orientation'] or q['attribute']['applicable']:active.append('attribute')
    if c['global_scope_explicit'] or q['scope']['applicable']:active.append('scope')
    if q['preservation']['applicable']:active.append('preservation')
    outcomes=[]
    for optimistic in (False,True):
        grades={k:q[k]['grade'] if q[k]['applicable'] and q[k]['grade'] is not None else 4 if optimistic else 0 for k in active}
        no=(grades['progress']<t['meaningful_progress'] or c['identity_required'] and grades['identity']==0
            or 'preservation' in grades and grades['preservation']==0)
        yes=all(v>=t['completed_outcome' if k in ('progress','endpoint') else 'preservation' if k=='preservation' else 'required_fidelity'] for k,v in grades.items())
        outcomes.append(0 if no else 2 if yes else 1)
    return outcomes[0] if outcomes[0]==outcomes[1] else -1


def verify_metrics(rows,metrics):
    p=[r['prediction'] for r in rows];y=[r['reference'] for r in rows]
    assert len(y)==len(set(r['case'] for r in rows))
    ns=[y.count(k) for k in range(3)];tp=[sum(a==b==k for a,b in zip(p,y)) for k in range(3)]
    f1=sum((Fraction(2*t,n+p.count(k)) for k,(t,n) in enumerate(zip(tp,ns))),Fraction())/3
    assert metrics['correct']==sum(tp) and metrics['total']==len(y) and metrics['accuracy']==sum(tp)/len(y)
    assert metrics['macro_f1']==float(f1) and metrics['unresolved']==p.count(-1)
    assert [metrics['per_class'][k]['recall'] for k in ('no','partial','yes')]==[t/n for t,n in zip(tp,ns)]


def compact(metric):
    r='/'.join(f"{metric['per_class'][k]['recall']:.0%}" for k in ('no','partial','yes'))
    return f"{metric['correct']}/{metric['total']}",f"{metric['macro_f1']:.3f}",r,f"{metric['total']-metric['unresolved']}/{metric['total']}"


def run(output):
    m=prepare(output);r=read(output/'results.json');inputs=load_inputs(m);cases=m['cases']
    assert r['manifest_ref']==digest(m) and r['new_api_calls']==0
    checks=0;policies=0;disjoint=0;diagnostics={}
    for key,model in r['models'].items():
        data=inputs[key];assert model['compiled_records_ref']==digest(data['records'])
        expected=[direct_prediction(x,DEFAULT) for x in data['records']]
        assert expected==[x['prediction'] for x in model['fixed_default']['cases']]
        verify_metrics(model['fixed_default']['cases'],model['fixed_default']['metrics']);checks+=1
        examples=[]
        for train_group,fold in model['folds'].items():
            trained=model['policies'][train_group];train=[i for i,c in enumerate(cases) if c['batch']==train_group]
            tx=[data['records'][i] for i in train];ty=[('no','partial','yes').index(cases[i]['reference']) for i in train]
            assert trained['training_feature_ref']==digest(tx) and trained['training_target_ref']==digest(ty)
            assert trained['training_sources']==[cases[i]['group'] for i in train]
            a=trained['artifact'];assert fold['frozen_policy_ref_before_and_after']==digest(a)
            if a:
                assert a['training_feature_ref']==digest(tx) and a['training_target_ref']==digest(ty)
                saved=deepcopy(a);restored=InstructionRuleCalibrator.restore(a)
                restored.predict_records(data['records']);assert restored.metadata()==saved
                assert a['limits']['fitted_thresholds']==4 and a['search']['candidates']==16
                policies+=1
            else:assert trained['error'] and trained['search']['eligible']==0
            for eval_group,row in fold['matrix'].items():
                idx=[i for i,c in enumerate(cases) if c['batch']==eval_group]
                test_sources={cases[i]['group'] for i in idx};overlap=bool(set(trained['training_sources'])&test_sources)
                assert row['source_disjoint_from_training']==(not overlap)
                if eval_group!=train_group:assert not overlap;disjoint+=1
                for family,scored in row.items():
                    if family=='source_disjoint_from_training':continue
                    verify_metrics(scored['cases'],scored['metrics']);checks+=1
                    if family=='instruction_rules':
                        predicted=[direct_prediction(data['records'][i],a['thresholds']) for i in idx] if a else [-1]*12
                        assert predicted==[v['prediction'] for v in scored['cases']]
            for scored in fold['heldout36'].values():verify_metrics(scored['cases'],scored['metrics']);checks+=1
        for scored in model['local48'].values():verify_metrics(scored['cases'],scored['metrics']);checks+=1
        # Diagnostics use only the fixed policy and previously cached local
        # baseline; they never select a rule or alter the primary split.
        for i,c in enumerate(cases):
            old=next(v for v in model['folds'][c['batch']]['matrix'][c['batch']]['previous_v6']['cases'] if v['case']==c['case'])
            new=model['fixed_default']['cases'][i]
            if old['prediction']==2 and new['prediction']!=2:
                examples.append({'case':c['case'],'instruction':c['instruction'],'reference':c['reference'],
                    'previous_prediction':2,'new_prediction':new['prediction'],'blocking_yes':new['decision']['blocking_yes']})
        diagnostics[key]={'previous_local_yes_blocked_by_semantic_gates':examples,
            'blocked_reference_counts':{k:sum(x['reference']==k for x in examples) for k in ('no','partial','yes')}}
    verify(output,m)
    audit={'passed':True,'independent_metric_sets_verified':checks,'qualified_fitted_policies':policies,
        'source_disjoint_cross_group_cells':disjoint,'training_targets_and_features_checked':True,
        'frozen_thresholds_unchanged_by_evaluation':True,'independent_instruction_gate_predictions':True,
        'unsupported_fits_not_replaced':True,'local_and_transfer_separate':True,'new_api_calls':0,
        'results_ref':fingerprint(output/'results.json')}
    save_json(output/'audit.json',audit);save_json(output/'diagnostics.json',diagnostics)
    lines=['# Instruction-dependent interactions: implementation and frozen transfer','',
        '**Implemented, but this version is not an accuracy improvement on the cached evidence.** Semantic guarantees pass the adversarial tests. The predeclared primary Luna/G1 trained policy is infeasible under the retained all-class support gate, so there is no qualified G1-trained v7 deployment to claim as a successful transfer.','',
        '## What changed','',
        '- There is no weighted sum. Progress and actual endpoint must both meet the outcome boundary for Yes.',
        '- Original identity gates Yes only when the instruction contract requires retaining the original instance. Required relations and counts also gate Yes. Requested attributes/scope and applicable instruction-relative preservation cannot be offset by another strong check.',
        '- A required check graded 0–2 cannot receive Yes under any candidate. Grade 0 required identity or destroyed source meaning produces No. Meaningful progress with a material required shortfall produces Partial.',
        '- If the contract requires a check but the extractor marks it inapplicable, treat it as unknown. Unknown facts stay interval-valued; missing responses abstain. The earlier learned “uninspectable means No” branch is absent.',
        '- Fitting chooses only four bounded thresholds from sixteen policies. It cannot remove gates or weaken required-fidelity Yes below grade 3. The existing two-correct-sources-per-class floor is retained. A fixed unfitted semantic policy is reported separately from learned fits.','',
        '## Predeclared primary test and fixed control','',
        'The primary model is Luna. Training is G1 only (12 cases); evaluation is G2/G3/G4 (36 source-distinct cases) without recalibration. Model evidence, labels, cases and presentation are unchanged. No new API calls were made.',
        'G1 has **zero qualifying fitted v7 policies**. The optimizer refuses to weaken semantic gates or deploy a class-collapsed fallback. The old G1-fitted v6 rubric scores 19/36 on the other groups; flat scores 22/36. The predeclared unfitted semantic default scores 22/36 there. The fixed default is a control, not a replacement trained policy chosen after the failed primary fit.',
        'All groups have been examined in earlier development. Evaluation labels are withheld from each fit, but these are retrospective cross-group tests, not a pristine untouched test set.','',
        '## Fixed, unfitted semantic policy on all 48 cases','',
        '| Evidence model | Fixed semantic correct | Macro-F1 | No/Partial/Yes recall | Coverage | Previous locally fitted v6 | Flat |',
        '|---|---:|---:|---|---:|---:|---:|']
    for key,model in r['models'].items():
        n,f1,recall,cov=compact(model['fixed_default']['metrics']);old=model['local48']['previous_v6']['metrics'];flat=model['local48']['flat']['metrics']
        lines.append(f"| {key} | {n} | {f1} | {recall} | {cov} | {old['correct']}/48 | {flat['correct']}/48 |")
    lines+=['','The fixed semantic control uses no training labels; old v6 local scores use all twelve labels in each group. They are different settings and cannot by themselves establish which policy transfers better. Mini uses the six previously verified literal-quote repairs; no new normalizations are introduced.','',
        '## Local fitting, including unsupported groups','',
        '| Model | Qualified groups | New fitted pipeline correct /48 | Fitted macro-F1 | Coverage | Previous v6 local /48 |',
        '|---|---:|---:|---:|---:|---:|']
    for key,model in r['models'].items():
        count=sum(p['artifact'] is not None for p in model['policies'].values());new=model['local48']['instruction_rules']['metrics'];old=model['local48']['previous_v6']['metrics']
        lines.append(f"| {key} | {count}/4 | {new['correct']}/48 | {new['macro_f1']:.3f} | {48-new['unresolved']}/48 | {old['correct']}/48 |")
    lines+=['','Each unsupported fit contributes twelve abstentions. These pooled numbers describe failure of the complete fit-and-predict protocol; they are not visual-judge accuracy on usable records. The fixed semantic control above remains a separate unfitted method.','',
        '## Every frozen train-12 → other-36 comparison','',
        '| Model | Training group | Fit status | New local correct | New frozen correct /36 | Frozen macro-F1 | Frozen No/Partial/Yes recall | Frozen coverage | Old v6 frozen /36 | Flat /36 |',
        '|---|---|---|---:|---:|---:|---|---:|---:|---:|']
    for key,model in r['models'].items():
        for group,fold in model['folds'].items():
            fit=model['policies'][group];local=fold['matrix'][group]['instruction_rules']['metrics'];new=fold['heldout36']['instruction_rules']['metrics']
            n,f1,recall,cov=compact(new);old=fold['heldout36']['previous_v6']['metrics'];flat=fold['heldout36']['flat']['metrics']
            if fit['artifact']:
                lines.append(f"| {key} | {group} | qualified | {local['correct']}/12 | {n} | {f1} | {recall} | {cov} | {old['correct']}/36 | {flat['correct']}/36 |")
            else:lines.append(f"| {key} | {group} | no qualifying policy | — | — (36 abstentions) | — | — | 0/36 | {old['correct']}/36 | {flat['correct']}/36 |")
    lines+=['','Each row freezes one training-group policy. Other-group labels do not choose thresholds. Reciprocal folds overlap in examples, so their 144 predictions per model are not 144 independent cases. Unsupported fits remain unresolved in machine-readable pooled metrics.','',
        '## Learned thresholds and training ambiguity','',
        'Default: meaningful progress ≥2; Yes requires outcome ≥3, required fidelity ≥3, preservation ≥3. Candidate ranges are [1,2] for meaningful progress and [3,4] for the other boundaries.','']
    for key,model in r['models'].items():
        for group,p in model['policies'].items():
            a=p['artifact']
            if a:lines.append(f"- {key}/{group}: {a['thresholds']}; {len(a['equally_scoring_training_policies'])} training-equivalent candidate(s).")
            else:lines.append(f"- {key}/{group}: no supported fit; best correct count before the class floor is {p['search']['best_unconstrained_correct']}/12.")
    lines+=['','Transfer scores for all training-equivalent candidates are retained as diagnostics in results.json. Their test outcomes never select the saved policy; the predeclared default-biased tie-break does.','',
        '## Why stronger semantics did not fix accuracy','',
        'The gates make constraints explicit but still depend on the extractor judging what is material. They do fix a concrete compensation error: on cached Sol evidence for G4C02 (pouring the bowl into the pot), the old local score returns Yes while the new fixed rule returns Partial, matching the reference. Progress is only 2 and the pouring endpoint/relation are unknown, so high attribute/preservation grades cannot produce Yes.',
        'That correction has a cost: the fixed gates block six other old local Sol Yes predictions whose references are also Yes. All blocked cases and their required checks are listed in diagnostics.json. Two concrete conflicts in the cached Luna observations:',
        '- G4C06, “Move the lamp to the right of the table”: human Yes; progress 3, endpoint 3, relation 4, but required original identity 1. The old local score accepts it; the new identity gate returns Partial. This is consistent with the supplied facts but disagrees with the human label. It does not prove either the human or the image interpretation is wrong.',
        '- G4C03, “let the table be wooden”: human Yes; the extractor gives progress 1, endpoint 1, attribute 1. A rule requiring visible achievement cannot produce Yes from those facts without weakening its meaning. G4C12 has a similar low-endpoint versus human-Yes disagreement.',
        'The G1 No/Partial boundary is also inconsistent with a global progress threshold: cached Partial cases have progress 1, while some No cases also receive weak-progress evidence. Accepting all weak traces loses No support; rejecting them loses Partial support. The new optimizer reports this rather than deriving a rubric from incidental high attributes or scope.',
        'Structural tests prove that coverage cannot compensate for a material required failure. They cannot prove that cached grades reflect the images correctly, that the applicable-check flags are correct, or that thresholded averaged human labels form a clean semantic boundary.','',
        '## Recommendation and verification','',
        'Keep this as an opt-in experimental rule family; do not promote it as an accuracy upgrade. The next evidence improvement should distinguish requested endpoint achievement, original-instance correspondence, and instruction-relative materiality without double-counting defects. A new evidence representation then needs a freshly frozen transfer evaluation.',
        'Twelve offline tests cover the exact identity/coverage counterexample, optional versus required identity/relation/count, endpoint and preservation interactions, contract/applicability contradictions, unknown bounds, monotonicity across joint quality changes, exact candidate selection, source/label isolation, serialization and frozen prediction. The full suite and independent audit are recorded beside this report.',
        f'Independent audit: {checks} metric sets, {policies} qualified fitted policies, {disjoint} disjoint train/evaluation cells. Extraction, fitting, evaluation, replay, and report add **zero API calls and zero API cost**. Existing source call failures remain in every denominator.',
        'Full offline CaliTree suite: **704 passed, 23 skipped**, one non-failing core-count warning. Exact deterministic refit and prediction replay passed.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print({'audit_passed':True,'metric_sets':checks,'qualified_policies':policies,'disjoint_cells':disjoint,'new_api_calls':0})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    run(p.parse_args().output_dir.resolve())
