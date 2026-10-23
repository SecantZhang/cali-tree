"""Frozen equal-vote ungated ablation on the completed 80-case pilot; offline."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from critical.core.decision.artifacts import digest, save_json
from critical.core.calibration import shared_regions_v27 as shared
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from run.calitree_aurora_pilot_v29 import read, fingerprint
from run.collect_calitree_aurora_pilot_v29r1 import verify_execution, metrics
from run.analyze_calitree_aurora_pilot_v29 import paired

VERSION = 'ungated-equal-expert-vote-v30'
PROTOCOL = {
    'version': VERSION,
    'vote': 'Exactly one equally weighted vote from each distinct deployed expert tree in a bank; no region-count, source-support or accuracy weighting.',
    'winner': 'Plurality of No=0, Partial=1, Yes=2.',
    'tie': 'Choose Partial when among the tied winners; otherwise choose No for a No/Yes tie. Do not invent a label outside the tied winners.',
    'invalid': 'Missing/invalid bound extraction, empty bank, or any invalid expert vote makes the bank unresolved (-1); no regular fallback.',
    'bypassed': 'All task-profile, evidence-region, semantic-support, counterexample, disagreement and merged-region coverage checks. Evidence-contract validation remains.',
    'denominator': 'All 80 outputs; unresolved counts incorrect. Also report 79 extraction-valid and 77 common-successful cases.',
    'comparison': 'Frozen regular response, v27 hybrid, ungated bank. Three banks separately, with source-cluster paired intervals.',
    'exploratory': 'Voting was fixed before this ablation was scored; pilot outcomes were already examined in prior work.',
    'new_model_calls': 0, 'fitting': False, 'tie_rule_sweep': False,
}


def vote(labels):
    labels=list(labels)
    if not labels or any(type(v) is not int or v not in (0,1,2) for v in labels):
        return {'prediction':-1,'reason':'missing_or_invalid_vote','counts':[labels.count(k) for k in range(3)],'tied':False,'unanimous':False}
    counts=[labels.count(k) for k in range(3)];winners=[k for k,c in enumerate(counts) if c==max(counts)]
    prediction=1 if 1 in winners else min(winners)
    return {'prediction':prediction,'reason':'fixed_tie_break' if len(winners)>1 else 'plurality',
            'counts':counts,'tied':len(winners)>1,'unanimous':len(set(labels))==1}


def predict_bank(experts, record):
    votes={ref:executor.predict_records([record])[0] for ref,executor in sorted(experts.items())}
    result=vote(v['prediction'] for v in votes.values())
    return {**result,'expert_votes':votes,'covered':result['prediction']>=0}


def load_banks(parent):
    result={}
    for i in (1,2,3):
        gate=shared.SharedRegionGate(read(parent/f'gates/v27_split{i}.json'))
        artifacts=shared.core.core_artifact(gate.previous)['previous_gate']['base_gate']['experts']
        result[i]=(gate,{ref:PortableRuleExecutor(artifact) for ref,artifact in artifacts.items()})
    return result


def score(parent):
    banks=load_banks(parent);records=[]
    for old in read(parent/'collection/predictions.json'):
        saved=read(parent/'collection/cases'/(old['case']+'.json'));record=None
        if saved['extraction_error'] is None:
            record=shared.evidence.project(saved['program'],saved['observation'],saved['pair_ref'],saved['interpretation'])
        row=deepcopy(old);row['votes']={}
        for i,(gate,experts) in banks.items():
            result=predict_bank(experts,record);arm=f'ungated_split{i}'
            row[arm]=result['prediction'];row['votes'][str(i)]=result;row['routes'][arm]=result
            # Reproduce original gate on successful evidence to guard against
            # comparing a changed input projection with the recorded v27 score.
            if record is not None:
                route=gate.select(saved['program'],record)
                before=old['routes'][f'v27_split{i}']
                assert (route['covered'],route['prediction'])==(before['covered'],before['prediction'])
        records.append(row)
    summaries=[]
    for i,(_,experts) in banks.items():
        ungated=f'ungated_split{i}';gated=f'v27_split{i}'
        accepted=[r for r in records if r['routes'][gated]['covered']]
        rejected=[r for r in records if not r['routes'][gated]['covered']]
        common=[r for r in records if not r['regular_error'] and not r['extraction_error']]
        extraction_valid=[r for r in records if not r['extraction_error']]
        slices={}
        for name,subset in (('v27_accepted',accepted),('v27_rejected',rejected),('extraction_valid',extraction_valid),('common_successful',common)):
            slices[name]={arm:metrics(subset,arm) for arm in ('regular',gated,ungated)}
        ties=[r for r in records if r['votes'][str(i)]['tied']]
        summaries.append({'bank':i,'experts':len(experts),'expert_refs':sorted(experts),
                          'metrics':{arm:metrics(records,arm)for arm in ('regular',gated,ungated)},
                          'versus_regular':paired(records,ungated), 'versus_v27':paired(records,ungated,gated),
                          'slices':slices,'ties':len(ties),'tie_correct':sum(r[ungated]==r['reference']for r in ties),
                          'unanimous':sum(r['votes'][str(i)]['unanimous']for r in records),
                          'prediction_distribution':dict(Counter(str(r[ungated])for r in records)),
                          'changes_on_v27_accepted':[r['case']for r in accepted if r[ungated]!=r[gated]]})
    return records,{'version':VERSION,'cases':len(records),'source_groups':len({r['source_group']for r in records}),
                    'regular':metrics(records,'regular'),'banks':summaries,'new_model_calls':0,
                    'always_no_accuracy':sum(r['reference']==0 for r in records)/len(records)}


def prepare(out,parent):
    if out.exists():raise ValueError('Use a fresh output directory')
    verify_execution(parent)
    if not read(parent/'collection/verification.json')['passed']:raise ValueError('Parent pilot is not audited')
    for name,expected in read(parent/'completion_seal.json')['files'].items():
        assert fingerprint(parent/name)==expected,name
    out.mkdir(parents=True)
    # Written before score() reads the pilot labels or computes the new votes.
    save_json(out/'protocol.json',PROTOCOL)
    source_files=[parent/'completion_seal.json',parent/'collection/predictions.json',parent/'ledger/budget.json']
    source_files+=sorted((parent/'collection/cases').glob('*.json'))+sorted((parent/'gates').glob('v27*.json'))
    manifest={'parent':str(parent),'protocol_ref':digest(PROTOCOL),
              'source_hashes':{str(p):fingerprint(p)for p in source_files},
              'code_hashes':{str(Path(__file__).resolve()):fingerprint(__file__)},
              'parent_execution_plan_sha256':fingerprint(parent/'execution_plan.json')}
    save_json(out/'manifest.json',manifest)
    records,result=score(parent)
    save_json(out/'predictions.json',records);save_json(out/'results.json',result)
    (out/'run.log').write_text('Voting protocol frozen before ablation scoring. Evaluated cached bound evidence only.\n')
    (out/'llm-histories.log').write_text('Zero model calls; no provider client constructed.\n')
    for bank in result['banks']:
        print({'bank':bank['bank'],'experts':bank['experts'],'metrics':bank['metrics'],'ties':bank['ties']},flush=True)


def audit(out):
    manifest=read(out/'manifest.json');parent=Path(manifest['parent'])
    assert read(out/'protocol.json')==PROTOCOL and digest(PROTOCOL)==manifest['protocol_ref']
    for p,h in {**manifest['source_hashes'],**manifest['code_hashes']}.items():assert fingerprint(p)==h,p
    assert fingerprint(parent/'execution_plan.json')==manifest['parent_execution_plan_sha256']
    verify_execution(parent)
    rows=read(out/'predictions.json');expert_decisions=0
    # Independent tree walk and explicit tie ordering; do not call vote() or the
    # portable executor when checking each exported vote and selected verdict.
    banks=load_banks(parent)
    for row in rows:
        saved=read(parent/'collection/cases'/(row['case']+'.json'));record=None
        if saved['extraction_error'] is None:
            record=shared.evidence.project(saved['program'],saved['observation'],saved['pair_ref'],saved['interpretation'])
        for i,(_,experts) in banks.items():
            actual=[]
            for ref,ex in experts.items():
                trace=[]
                if record is None or (ex.requires_interpretation and not record['features']['meaning_available']):label=-1
                else:
                    node=ex.artifact['tree']
                    while 'feature'in node:
                        value=record['features'][node['feature']];trace.append({'feature':node['feature'],'value':value})
                        node=node['true'if value else'false']
                    label=node['prediction']
                recorded=row['votes'][str(i)]['expert_votes'][ref]
                assert label==recorded['prediction'] and trace==recorded['trace'];actual.append(label);expert_decisions+=1
            if any(v not in(0,1,2)for v in actual):expected=-1
            else:
                counts=Counter(actual);expected=next(label for label in (1,0,2)if counts[label]==max(counts.values()))
            assert row[f'ungated_split{i}']==expected
    replayed,summary=score(parent)
    assert replayed==rows and summary==read(out/'results.json')
    report={'passed':True,'cases':len(rows),'expert_decisions_independently_checked':expert_decisions,
            'bank_predictions_checked':len(rows)*3,'rules_fixed_before_scoring':True,'no_gate_filter_in_voting':True,
            'parent_budget_unchanged':True,'new_model_calls':0,'new_fitting':False}
    save_json(out/'verification.json',report)
    save_json(out/'completion_seal.json',{'files':{str(p.relative_to(out)):fingerprint(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='completion_seal.json'},'auditor_sha256':fingerprint(__file__)})
    print(report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--parent-run',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:audit(a.output_dir.resolve())
    elif a.parent_run is None:p.error('--parent-run required')
    else:prepare(a.output_dir.resolve(),a.parent_run.resolve())
