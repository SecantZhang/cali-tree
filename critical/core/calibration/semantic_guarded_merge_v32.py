"""Conditional evidence verification and semantics-preserving region merges.

Training uses declared semantic predicates and local/cross-fit calibration labels.
Runtime contains short Boolean clauses only. Merges cannot weaken goal,
materiality, uncertainty or outcome obligations across task scopes.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import combinations

from ..decision.artifacts import digest
from . import semantic_region_merge_v28 as merging
from . import shared_regions_v27 as shared

VERSION = 'semantic-guarded-region-merge-v32'
FEATURES = shared.evidence.FEATURES
VERIFY_FEATURES = tuple(sorted(k for k in FEATURES if (k.startswith('meaning_') and k!='meaning_available')
                            or k.startswith(('task_','outcome_','identity_all_','preservation_all_'))))
OBLIGATIONS = frozenset(k for k in FEATURES if (k.startswith('meaning_') and k!='meaning_available') or k.startswith('outcome_'))
CONTRACT = digest({'version':VERSION,'features':shared.evidence.CONTRACT_REF,'verify_features':VERIFY_FEATURES,
                   'merge_obligations':sorted(OBLIGATIONS),'semantics':'Per-verdict conjunction of one/two-literal support clauses; preserve protected positives; no new labels.'})


@dataclass(frozen=True)
class Config:
    max_clauses: int = 8
    max_rounds: int = 32
    max_candidates_per_round: int = 64
    min_literal_similarity: float = .5

    def __post_init__(self):
        if any(type(v)is not int or v<1 for v in (self.max_clauses,self.max_rounds,self.max_candidates_per_round)):
            raise ValueError('Positive search bounds required')
        if type(self.min_literal_similarity)not in(int,float) or not 0<self.min_literal_similarity<=1:
            raise ValueError('Invalid similarity')


def priority(literal):
    f,value=literal
    prefixes=('meaning_progress_requested_endpoint','meaning_endpoint_gap','meaning_identity_materiality',
              'meaning_collateral_materiality','meaning_evidence_consistency','meaning_progress',
              'outcome_all','identity_all','preservation_all','task_')
    return (next((i for i,p in enumerate(prefixes)if f.startswith(p)),len(prefixes)),f,value)


def _fit_label(positive,negative,max_clauses):
    if not positive:raise ValueError('Each verdict needs protected correct evidence')
    if not negative:return [],{'positive':len(positive),'negative':0,'rejected_training_errors':0,'unseparated_training_errors':0}
    full=(1<<len(positive))-1;allneg=(1<<len(negative))-1;options={}
    for f in VERIFY_FEATURES:
        for value in(False,True):
            pm=sum(1<<i for i,r in enumerate(positive)if r[f]==value)
            nm=sum(1<<i for i,r in enumerate(negative)if r[f]==value)
            key=(pm,nm);literal=(f,value)
            if key not in options or priority(literal)<priority(options[key]):options[key]=literal
    candidates={}
    def add(mask,clause):
        if not mask:return
        clause=tuple(sorted(clause,key=priority))
        if mask not in candidates or (len(clause),tuple(map(priority,clause)))<(len(candidates[mask]),tuple(map(priority,candidates[mask]))):
            candidates[mask]=clause
    items=sorted(options.items(),key=lambda item:priority(item[1]))
    for (pm,nm),literal in items:
        if pm==full:add(allneg^nm,(literal,))
    for ((pa,na),la),((pb,nb),lb)in combinations(items,2):
        if (pa|pb)==full:add(allneg^(na|nb),(la,lb))
    remaining=allneg;chosen=[]
    while remaining and len(chosen)<max_clauses:
        available=[(mask,c)for mask,c in candidates.items()if mask&remaining]
        if not available:break
        mask,clause=min(available,key=lambda mc:(-(mc[0]&remaining).bit_count(),len(mc[1]),tuple(map(priority,mc[1]))))
        chosen.append(clause);remaining&=~mask
    clauses=[[{'feature':f,'value':v}for f,v in c]for c in chosen]
    assert all(passes(clauses,v)for v in positive)
    return clauses,{'positive':len(positive),'negative':len(negative),
                   'rejected_training_errors':len(negative)-remaining.bit_count(),'unseparated_training_errors':remaining.bit_count()}


def fit_verifier(protected,calibration,config=Config()):
    """Examples contain feature values, frozen-core prediction and reference.

    protected examples must already be correct. Calibration references are used
    only here, never by the gate or candidate scheduler at inference.
    """
    clauses={};counts={}
    for label in(0,1,2):
        base=[e['values']for e in protected if e['prediction']==label]
        if any(e['prediction']!=e['reference']for e in protected):raise ValueError('Incorrect protected example')
        correct=[e['values']for e in calibration if e['prediction']==label and e['reference']==label]
        errors=[e['values']for e in calibration if e['prediction']==label and e['reference']!=label]
        clauses[str(label)],counts[str(label)]=_fit_label(base+correct,errors,config.max_clauses)
    artifact={'version':VERSION,'contract_ref':CONTRACT,'clauses':clauses,'training_counts':counts,'max_clauses':config.max_clauses}
    artifact['artifact_ref']=digest(artifact)
    validate_verifier(artifact)
    return artifact


def passes(clauses,values):
    return values is not None and all(any(values[c['feature']]==c['value']for c in clause)for clause in clauses)


def validate_verifier(a):
    if (set(a)!={'version','contract_ref','clauses','training_counts','max_clauses','artifact_ref'} or a['version']!=VERSION
            or a['contract_ref']!=CONTRACT or a['artifact_ref']!=digest({k:v for k,v in a.items()if k!='artifact_ref'})
            or set(a['clauses'])!={'0','1','2'} or set(a['training_counts'])!={'0','1','2'}
            or type(a['max_clauses'])is not int or a['max_clauses']<1):raise ValueError('Changed verifier contract')
    for label,clauses in a['clauses'].items():
        if len(clauses)>a['max_clauses']:raise ValueError('Verifier exceeds clause budget')
        for clause in clauses:
            if not 1<=len(clause)<=2 or len({c['feature']for c in clause})!=len(clause):raise ValueError('Invalid support clause')
            for c in clause:
                if set(c)!={'feature','value'} or c['feature']not in VERIFY_FEATURES or type(c['value'])is not bool:raise ValueError('Undeclared support predicate')
        counts=a['training_counts'][label]
        if (set(counts)!={'positive','negative','rejected_training_errors','unseparated_training_errors'}
                or any(type(v)is not int or v<0 for v in counts.values()) or not counts['positive']
                or counts['rejected_training_errors']+counts['unseparated_training_errors']!=counts['negative']):raise ValueError('Invalid verification support')


class VerifiedRegionGate:
    def __init__(self,base,verifier):
        validate_verifier(verifier)
        self.base,self.verifier=base,deepcopy(verifier)
        self.artifact={'version':VERSION,'contract_ref':CONTRACT,'base_gate':base.export(),'verifier':deepcopy(verifier)}
        self.artifact['artifact_ref']=digest(self.artifact)

    @classmethod
    def restore(cls,a):
        if (set(a)!={'version','contract_ref','base_gate','verifier','artifact_ref'} or a['version']!=VERSION or a['contract_ref']!=CONTRACT
                or a['artifact_ref']!=digest({k:v for k,v in a.items()if k!='artifact_ref'})):raise ValueError('Changed verified gate')
        b=a['base_gate']
        if b['version']==shared.VERSION:base=shared.SharedRegionGate(b)
        elif b['version']==merging.VERSION:base=merging.SemanticMergedRegionGate(b)
        else:raise ValueError('Unsupported gate base')
        result=cls(base,a['verifier'])
        if result.export()!=a:raise ValueError('Noncanonical verified gate')
        return result

    def export(self):return deepcopy(self.artifact)
    def accepts_task(self,program):return self.base.accepts_task(program)
    def shortlist(self,program):return self.base.shortlist(program)
    def definition(self,ref):return {**self.base.definition(ref),'conditional_support_clauses':deepcopy(self.verifier['clauses'])}
    def select(self,program,record):
        route=self.base.select(program,record)
        if not route['covered']:return route
        values=shared.evidence.feature_values(program,record)
        clauses=self.verifier['clauses'][str(route['prediction'])]
        if not passes(clauses,values):
            return {'covered':False,'prediction':-1,'reason':'outside_verdict_support','matches':[],
                    'rejected_prediction':route['prediction'],'failed_support_clauses':[c for c in clauses if not any(values[x['feature']]==x['value']for x in c)]}
        return {**route,'verdict_support_ref':self.verifier['artifact_ref']}
    def select_bound(self,program,observation,pair_ref,interpretation):
        return self.select(program,shared.evidence.project(program,observation,pair_ref,interpretation))


def preserve_obligations(children,parent):
    """Symbolic implication in protected semantic space, per task and verdict.

    Semantic similarity or known-case retention cannot authorize deletion of a
    goal/materiality/uncertainty distinction. Nonprotected conditions may relax.
    """
    checks=states=0;projected=frozenset(c for c in parent['term']if c[0]in OBLIGATIONS)
    for task in sorted(parent['tasks']):
        alternatives=[frozenset(c for c in child['term']if c[0]in OBLIGATIONS)for child in children
                      if task in child['tasks']and child['prediction']==parent['prediction']]
        passed,used=shared.implies_union(projected,alternatives);checks+=1;states+=used
        if not passed:return {'passed':False,'scope_checks':checks,'proof_states':states,'failed_scope':task}
    return {'passed':True,'scope_checks':checks,'proof_states':states}


def check_bank(bank,verifier,examples,*,retained=None):
    checked=[];failures=[]
    for i,e in enumerate(examples):
        core=e['core_route'];label=core['prediction']
        accepted=any(merging.applicable(r,e)for r in bank.values())
        accepted=accepted and passes(verifier['clauses'][str(label)],e['values']) if accepted else False
        before=e['baseline']
        if before['covered']and not accepted:failures.append({'index':i,'reason':'lost_coverage'})
        if accepted and 'reference'in e and label!=e['reference']:
            # Existing baseline errors are allowed to remain; new false coverage
            # is never rewarded just because the regular judge was also wrong.
            if not before['covered']:failures.append({'index':i,'reason':'new_false_acceptance'})
        checked.append({'covered':bool(accepted),'prediction':label if accepted else -1})
    return {'passed':not failures,'checked':len(checked),'failures':failures}


def develop(baseline,rows,programs,verifier,regression_examples,calibration_examples,config=Config()):
    """Merge only after semantic proof and independent local/training checks.

    Calibration examples must exclude the outer validation source group. Labels
    only reject erroneous newly accepted training examples; no held-out labels.
    """
    local=[{'program':programs[r['source_group']],'features':r['features'],'reference':r['reference']}for r in rows]
    local_probes=merging.prepared(baseline,local)
    for e,r in zip(local_probes,rows):e['reference']=r['reference']
    original=VerifiedRegionGate(baseline,verifier)
    for e,source in zip(local_probes,local):e['baseline']=original.select(source['program'],source['features'])
    if any(not e['baseline']['covered']or e['baseline']['prediction']!=e['reference']for e in local_probes):
        raise ValueError('Verifier lost protected local accuracy')
    regress=merging.prepared(baseline,regression_examples)
    for e,source in zip(regress,regression_examples):
        e['baseline']=original.select(source['program'],source['features'])
    calibration=merging.prepared(baseline,calibration_examples)
    for e,source in zip(calibration,calibration_examples):
        e['baseline']=original.select(source['program'],source['features']);e['reference']=source['reference']
    bank=merging.definitions(baseline);current=baseline;events=[];trials=[];config0=merging.Config(
        max_rounds=config.max_rounds,max_candidates_per_round=config.max_candidates_per_round,min_literal_similarity=config.min_literal_similarity)
    for round_index in range(config.max_rounds):
        winners=[]
        for c in merging.pair_candidates(bank,config0)[:config.max_candidates_per_round]:
            children=[bank[k]for k in c['children']];proof=preserve_obligations(children,c['parent'])
            entry={k:v for k,v in c.items()if k!='parent'};entry.update(round=round_index,obligation_proof=proof)
            if not proof['passed']:
                trials.append({**entry,'status':'rejected','reasons':['semantic_obligation_loss']});continue
            key=digest([c['parent']['prediction'],shared.conditions(c['parent']['term']),sorted(c['parent']['tasks']),sorted(c['parent']['experts'])])
            proposed={k:v for k,v in bank.items()if k not in c['children']};proposed[key]=c['parent']
            checks={'local':check_bank(proposed,verifier,local_probes),'regression':check_bank(proposed,verifier,regress),
                    'calibration':check_bank(proposed,verifier,calibration)}
            reasons=[name+'_retention_or_false_acceptance'for name,r in checks.items()if not r['passed']]
            retention=[]
            _,_,parent_sources=merging.support(c['parent'],rows,programs,local_probes)
            for child in children:
                _,_,sources=merging.support(child,rows,programs,local_probes);retention.append({'before':len(sources),'retained':len(sources&parent_sources)})
            if any(r['before']!=r['retained']for r in retention):reasons.append('child_support_loss')
            entry.update(status='rejected'if reasons else'qualified',reasons=reasons,checks=checks,child_retention=retention,
                         parent={'prediction':c['parent']['prediction'],'conditions':shared.conditions(c['parent']['term']),
                                 'scope_refs':sorted(c['parent']['tasks']),'expert_refs':sorted(c['parent']['experts'])})
            trials.append(entry)
            if not reasons:
                rank=(len(proposed),sum(len(r['term'])for r in proposed.values()),-len(parent_sources),-c['literal_similarity'],tuple(c['children']))
                winners.append((rank,entry,proposed))
        if not winners:break
        _,winner,proposal=min(winners,key=lambda v:v[0])
        candidate=merging.pack(baseline,proposal,rows,programs,local_probes)
        if merging.metrics(candidate)['regions']>=merging.metrics(current)['regions']:break
        current=candidate;bank=merging.definitions(current)
        events.append({'round':round_index,'children':winner['children'],'parent':winner['parent'],'gate_ref':current.artifact['artifact_ref']})
    final=VerifiedRegionGate(current,verifier)
    for source,e in zip(local+regression_examples,local_probes+regress):
        before=e['baseline'];after=final.select(source['program'],source['features'])
        if before['covered']and (not after['covered']or after['prediction']!=before['prediction']):raise AssertionError('Packed gate lost retained route')
    return final,{'version':VERSION,'before':merging.metrics(baseline),'after':merging.metrics(current),
                  'accepted':events,'trials':trials,'config':asdict(config),'new_model_calls':0,
                  'semantic_obligation_rejections':sum('semantic_obligation_loss'in t['reasons']for t in trials)}
