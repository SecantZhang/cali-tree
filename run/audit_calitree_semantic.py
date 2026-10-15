"""Independently recompute the fixed-group result and write its review report."""
from collections import Counter
from pathlib import Path
from fractions import Fraction

from critical.core.decision.artifacts import save_json
from critical.core.decision.semantic_evidence import QUALITIES,DESCRIPTORS,feature_record
from critical.core.calibration.semantic_calibration import SemanticRouter
from run.calitree_single_call import ROOT,read,fingerprint
from run.calitree_semantic_evidence import prepare

EVIDENCE=ROOT/'logs/exps/261014-semantic-contract-evidence-v5'
BASE=ROOT/'logs/exps/261014-semantic-cluster-calibration-v5-r1'
OUTPUT=ROOT/'logs/exps/261014-semantic-visibility-calibration-v6'


def audit():
    m=prepare(EVIDENCE); cases=m['cases']; observed=read(EVIDENCE/'results.json')
    result=read(OUTPUT/'results.json'); rows={r['case']:r for r in observed['observations']}
    old=read(ROOT/'logs/exps/261013-four-groups-local-v4/results.json')
    assert m['judge_identity']==old['model']
    assert len(cases)==48 and len({c['group'] for c in cases})==48
    assert len({c['editing_model'] for c in cases})==1
    assert len(rows)==48 and set(rows)=={c['case'] for c in cases}
    assert observed['attempts']==48 and observed['outcomes']=={'transport_error':4,'completed':44}
    original_manifest=read(ROOT/'logs/exps/261013-four-groups-local-v4/manifest.json')
    assert cases==original_manifest['cases']
    router=SemanticRouter.restore(read(BASE/'router.json')['router'])
    seal=read(OUTPUT/'fit_seal.json')
    assert seal['results_ref']==fingerprint(OUTPUT/'results.json') and seal['plan_ref']==fingerprint(OUTPUT/'plan.json')
    for rel,h in seal['code_hashes'].items():
        assert fingerprint(ROOT/rel)==h and fingerprint(OUTPUT/'source_snapshot'/rel)==h
    features={}
    for c in cases:
        r=rows[c['case']];assert r['id']==c['id'] and r['instruction']==c['instruction']
        jobs=list((EVIDENCE/'ledgers'/c['case']/'jobs').glob('*.json'));assert len(jobs)==1
        j=read(jobs[0]);assert j['payload']=={'instruction':c['instruction']}
        assert j['slot']=='once' and j['stage']=='semantic_evidence_v5'
        assert j['media_identity']==[{'type':'text','text':'SOURCE image'},
            {'type':'image','sha256':c['image_hashes']['source_image']},
            {'type':'text','text':'EDITED image'},{'type':'image','sha256':c['image_hashes']['edited_image']}]
        budget=read(EVIDENCE/'ledgers'/c['case']/'budget.json')
        assert budget['limits']['identity']==m['judge_identity']
        features[c['case']]=feature_record(r['extraction']['observations'],c['instruction']) if r['extraction'] else None
    valid=[f['descriptor'] for f in features.values() if f is not None]
    assert SemanticRouter().fit(valid).metadata()==router.metadata()
    # Input permutation invariance also rules out case-position routing.
    assert SemanticRouter().fit(list(reversed(valid))).metadata()==router.metadata()
    checks=[]
    for group,arms in result['groups'].items():
        part=[c for c in cases if c['batch']==group]
        assert len(part)==12 and Counter(c['reference'] for c in part)=={'no':4,'partial':4,'yes':4}
        for family,a in arms.items():
            policy=a['policy'];w=policy['weights'];o=policy['offsets'];lo,hi=policy['cutpoints'];g=policy['uninspectable_label']
            assert sum(v!=0 for v in w+o)+(g is not None)==policy['active_coefficients']<=4
            assert policy['shared_cutpoints']==2 and all(v>=0 for v in w)
            assert all(not v or policy['cluster_support'][i]>=2 for i,v in enumerate(o))
            assert (not any(o)) if family=='unclustered' else True
            if g is not None:assert policy['uninspectable_support']>=2 and policy['uninspectable_correct_support']>=2
            predictions=[];targets=[]
            assert [c['case'] for c in part]==[r['case'] for r in a['cases']]
            for c,r in zip(part,a['cases']):
                f=features[c['case']];target=('no','partial','yes').index(c['reference']);targets.append(target)
                if f is None:p=-1
                else:
                    cluster=router.predict([f['descriptor']])[0];offset=o[cluster]
                    scores=[sum(x*y for x,y in zip(w,f[k]))+offset for k in ('lower','upper')]
                    labels=[int(s>=lo)+int(s>=hi) for s in scores];p=labels[0] if labels[0]==labels[1] else -1
                    raw=rows[c['case']]['extraction']['observations']['qualities']
                    # Raw null flags, not the fitted implementation's guard helper.
                    if g is not None and raw['progress']['grade'] is None and raw['endpoint']['grade'] is None:p=g
                assert p==r['prediction'] and r['reference']==target
                predictions.append(p)
            n=12;tp=[sum(a==b==k for a,b in zip(predictions,targets)) for k in range(3)]
            f1=sum((Fraction(2*t,4+predictions.count(k)) for k,t in enumerate(tp)),Fraction())/3
            metrics=a['metrics'];assert sum(tp)==metrics['correct']>=10 and predictions.count(-1)==metrics['unresolved']
            assert float(f1)==metrics['macro_f1'] and metrics['accuracy']==sum(tp)/n
            assert min(tp)>=2
            for k,name in enumerate(('no','partial','yes')):assert metrics['per_class'][name]['recall']==tp[k]/4
            checks.append({'group':group,'family':family,'correct':sum(tp),'macro_f1':float(f1),
                           'recall':[t/4 for t in tp],'coverage':(12-predictions.count(-1))/12})
    receipt={'all_requirements_passed':True,'fixed_cases':48,'balanced_groups':4,'source_distinct':True,
             'same_judge_and_editor':True,'single_source_first_response_per_case':True,
             'extraction_payloads_label_blind':True,'router_inputs_instruction_only':list(DESCRIPTORS),
             'router_order_invariant':True,'prediction_feature_whitelist':list(QUALITIES),
             'matched_supervised_budget':'four nonzero terms including cluster offsets and visibility verdict, two shared thresholds',
             'failures_retained':4,'independent_metrics_and_predictions':checks,'new_calls_in_fit_and_audit':0,
             'no_heldout_or_repeat_robustness_claim':True}
    save_json(OUTPUT/'audit.json',receipt)
    report=['# Fixed AURORA groups: richer checks, observability, and clustering','',
        'The requested near-perfect LOCAL threshold was met in every fixed group: 10/12, 12/12, 10/12, 10/12. Both shared and clustered policies reach these counts. No cases or labels were replaced.',
        'These are local training results: each policy uses all twelve labels in its group. They do not establish generalization or repeated-model robustness.','',
        '| Group | Cached flat correct | Shared policy correct | Shared macro-F1 | Clustered correct | Clustered macro-F1 |',
        '|---|---:|---:|---:|---:|---:|']
    for b,g in result['groups'].items():
        shared=g['unclustered']['metrics'];cluster=g['clustered']['metrics'];flat=old['batches'][b]['flat_metrics']
        report.append(f"| {b} | {flat['correct']}/12 | {shared['correct']}/12 | {shared['macro_f1']:.3f} | {cluster['correct']}/12 | {cluster['macro_f1']:.3f} |")
    report+=['','The richer evidence and explicit observability policy drive the improvement. Clustering adds zero correct cases; it modestly improves G4 macro-F1 through an abstention. Prefer the shared policy until clusters show a repeatable benefit.','',
        '## Recall, coverage, and matched resolved comparisons','',
        '| Group | Policy | No recall | Partial recall | Yes recall | Resolved / 12 | Common resolved | Flat correct on common | Policy correct on common |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for b,g in result['groups'].items():
        for name,a in g.items():
            m=a['metrics'];r=[m['per_class'][k]['recall'] for k in ('no','partial','yes')];common=a['common_resolved']
            report.append(f"| {b} | {name} | {r[0]:.0%} | {r[1]:.0%} | {r[2]:.0%} | {12-m['unresolved']}/12 | {common['total']} | {common['flat_correct']} | {common['calibrated_correct']} |")
    report+=['','Flat results reuse the original same-model, same-case calls. Transport failures differ between runs; common-resolved counts are reported to expose that confound. Flat was not fitted to each group; these gains measure local calibration capacity, not held-out superiority.','',
        '## Reusable learned rules','',
        'All quality grades range from 0 to 4. A score below the first cut means No, between cuts means Partial, and at or above the second cut means Yes. Interval-valued evidence resolves only when both bounds give the same label.',
        'A failed model response always remains unresolved. In G1 only, a supported learned branch maps a completed extraction with both progress and endpoint uninspectable to No. The original facts remain null: this calibrates an evaluation verdict rather than inventing a failed physical outcome. Two separate source cases support the branch.','']
    for b,g in result['groups'].items():
        for name,a in g.items():
            p=a['policy'];terms=' + '.join(f'{v} × {k}' for k,v in zip(QUALITIES,p['weights']) if v)
            report.append(f"- {b} {name}: score = {terms}; offsets {p['offsets']}; cuts {p['cutpoints']}; visibility label {p['uninspectable_label']}; {p['active_coefficients']}/4 fitted terms plus two cuts.")
    report+=['','Both families have the same maximum supervised budget: four nonzero terms including cluster offsets and the visibility verdict, plus two shared cuts. All learned classes recognize at least two distinct sources; active cluster adjustments require at least two local source cases.','',
        'The label-blind router has three clusters: spatial moves (14 cases), state/action edits (11), and mixed appearance/addition/background/orientation edits (19). It uses 13 fixed instruction-contract booleans, excludes evidence grades and labels, and is fitted once on the 44 completed contracts before supervised fitting. It does not cluster optimized label rules, exact instructions, object names, case IDs, or image hashes.',
        'These broad clusters may be too coarse to help. G2 and G3 select zero cluster offsets. G1 replaces identity weighting with a cluster adjustment at equal local accuracy; that is a different representation, not evidence of improved generalization.','',
        '## Remaining failures and uncertainty','',
        '- Four transport failures remain in every denominator: G1C01, G1C02, G3C04, G4C07. They were not retried or replaced.',
        '- G3C09, the inverted bottle: reference Yes, predicted No. The extractor observes inversion but penalizes identity/label drift in endpoint and preservation. This can double-count deviations. Separating the physical endpoint from identity/collateral penalties is the next reusable evidence improvement; it requires new validation rather than a bottle exception.',
        '- G4C02, pouring the bowl into the pot: reference Partial. The shared policy predicts Yes because its selected attribute/preservation terms miss the unverified pouring endpoint. The clustered policy abstains because endpoint is unknown. Its better macro-F1 trades coverage for avoiding a false Yes.',
        '- The 44 completed responses therefore yield 42 correct under the shared method; the official denominator remains 48. Under the clustered method, 42/43 resolved verdicts are correct, with an additional semantic abstention. Neither figure is 100% on all 48.',
        '- The evidence prompt and visibility proposal were designed after earlier error inspection, and each local group is fitted separately. The four groups are replications of local fit, not held-out testing. One response per case does not measure sampling robustness.','',
        '## Evidence and cost','',
        f"48 new source-first image calls with gpt-6.1-sol/high; 44 completed and 4 SSL errors. Returned usage: {observed['input_tokens']:,} input tokens and {observed['completion_tokens']:,} completion tokens. At the experiment rates of $2/M input and $10/M output, the usage estimate is ${result['evidence_cost']['usage_list_price_usd']:.4f}; failed requests can have unreturned usage, so this is not an invoice. Fitting, clustering, replay, and auditing made zero new API calls.",
        'The first v5 fit artifact is retained but invalidated: centroid floating-point drift broke restore validation. The repaired v5-r1 fit and v6 results have exact offline replay. V5 shared G1 had no qualifying interval-safe policy; it was not silently replaced with a collapsed classifier.',
        'The extractor, prompt, request ledgers, original failed slots, frozen fixed groups, original flat calls, v5 comparison, v6 policies, source snapshots, and independent audit are preserved in their experiment directories.']
    (OUTPUT/'report.md').write_text('\n'.join(report)+'\n')
    print({'audited':True,'fixed_cases':48,'local_correct':[result['groups'][g]['unclustered']['metrics']['correct'] for g in sorted(result['groups'])],'new_api_calls':0})


if __name__=='__main__':audit()
