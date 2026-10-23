"""Resolve deferred cases only with affirmative, requirement-level warrants.

The verified baseline preserves locally necessary exceptions. New decisions
require a strict semantic/physical certificate, a matching expert vote, and a
source-calibrated short support guard. No forced majority voting.
"""
from copy import deepcopy
from ..decision.artifacts import digest
from . import semantic_guarded_merge_v32 as fixed
from .semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor

VERSION='decision-warrant-gate-v33'
CONTRACT=digest({'version':VERSION,'verifier':fixed.CONTRACT,
    'yes':'Every requirement endpoint established, no central gap/material shortfall, coherent evidence, all physical outcomes satisfied.',
    'no':'Every requirement lacks meaningful progress with central gap/wrong target, coherent evidence, all physical outcomes directly unsatisfied.',
    'support':'At least two distinct correct sources and zero unseparated training errors for enabled warrant labels.',
    'new_decisions':'Only No or Yes, supported by an expert vote and a calibrated certificate guard; unknown and partial warrants defer.'})


def certificate(record):
    if record is None:return None
    fixed.shared.evidence.validate_record(record)
    f=record['features']
    if not f['meaning_available']:return None
    yes=(f['meaning_progress_requested_endpoint_all'] and f['meaning_endpoint_gap_none_all']
         and f['meaning_evidence_consistency_coherent_all'] and f['outcome_all_true_all']
         and not f['meaning_identity_materiality_material_shortfall_any']
         and not f['meaning_identity_materiality_uncertain_any']
         and not f['meaning_collateral_materiality_material_unrequested_change_any']
         and not f['meaning_collateral_materiality_uncertain_any']
         and any(f['meaning_identity_materiality_'+state+'_any']for state in('no_shortfall','immaterial_difference','not_relevant'))
         and (f['meaning_collateral_materiality_none_any']or f['meaning_collateral_materiality_minor_incidental_any']))
    # There is at least one requirement (bound-program validator), and each
    # progress/gap category must be individually in the allowed negative set.
    no=(not f['meaning_progress_requested_endpoint_any'] and not f['meaning_progress_toward_requested_goal_any']
        and not f['meaning_progress_uncertain_any'] and f['meaning_evidence_consistency_coherent_all']
        and not f['meaning_endpoint_gap_none_any'] and not f['meaning_endpoint_gap_minor_detail_any']
        and not f['meaning_endpoint_gap_uncertain_any'] and f['outcome_all_false_all']
        and (f['meaning_progress_none_any']or f['meaning_progress_incidental_change_only_any'])
        and (f['meaning_endpoint_gap_core_endpoint_missing_any']or f['meaning_endpoint_gap_wrong_direction_or_target_any']))
    if yes and no:raise ValueError('Contradictory semantic warrant')
    return 2 if yes else 0 if no else None


def experts(base):
    raw=base.base if isinstance(base,fixed.VerifiedRegionGate) else base
    executor=fixed.merging.unwrap(raw)
    artifacts=fixed.shared.core.core_artifact(executor.previous)['previous_gate']['base_gate']['experts']
    return {ref:PortableRuleExecutor(a)for ref,a in artifacts.items()}


def warrant_examples(base,examples):
    bank=experts(base);data=[]
    for e in examples:
        label=certificate(e['features'])
        if label is None:continue
        if not any(ex.predict_records([e['features']])[0]['prediction']==label for ex in bank.values()):continue
        data.append({'values':fixed.shared.evidence.feature_values(e['program'],e['features']),
                     'prediction':label,'reference':e['reference'],'source_group':e['source_group']})
    return data


def fit_support(base,protected_examples,calibration,config=fixed.Config()):
    # Unlike the legacy verifier, new-warrant positives need not preserve
    # contradictory legacy examples: those already have the baseline route.
    data=warrant_examples(base,protected_examples+calibration);clauses={};counts={};enabled={}
    for label in(0,2):
        positive=[e['values']for e in data if e['prediction']==label and e['reference']==label]
        negative=[e['values']for e in data if e['prediction']==label and e['reference']!=label]
        source_count=len({e['source_group']for e in data if e['prediction']==label and e['reference']==label})
        if len(positive)<2 or source_count<2:
            clauses[str(label)]=[];counts[str(label)]={'positive':len(positive),'negative':len(negative),'unseparated_training_errors':len(negative)};enabled[str(label)]=False
        else:
            clauses[str(label)],counts[str(label)]=fixed._fit_label(positive,negative,config.max_clauses)
            enabled[str(label)]=counts[str(label)]['unseparated_training_errors']==0
        counts[str(label)]['correct_sources']=source_count
    a={'version':VERSION,'contract_ref':CONTRACT,'clauses':clauses,'training_counts':counts,'enabled':enabled}
    a['artifact_ref']=digest(a)
    return a


class DecisionWarrantGate:
    def __init__(self,base,support):
        if (support['version']!=VERSION or support['contract_ref']!=CONTRACT
                or support['artifact_ref']!=digest({k:v for k,v in support.items()if k!='artifact_ref'})
                or set(support['clauses'])!={'0','2'} or set(support['enabled'])!={'0','2'}):raise ValueError('Changed warrant support')
        for label,clauses in support['clauses'].items():
            counts=support['training_counts'][label]
            if any(type(v)is not int or v<0 for v in counts.values()):raise ValueError('Invalid warrant counts')
            if support['enabled'][label]and(counts['correct_sources']<2 or counts['unseparated_training_errors']):
                raise ValueError('Unsupported warrant label')
            if type(support['enabled'][label])is not bool:raise ValueError('Invalid enable flag')
            for c in clauses:
                if not 1<=len(c)<=2:raise ValueError('Invalid warrant clause')
                for literal in c:
                    if set(literal)!={'feature','value'} or literal['feature']not in fixed.VERIFY_FEATURES or type(literal['value'])is not bool:
                        raise ValueError('Undeclared warrant literal')
        self.base,self.support=base,deepcopy(support);self.experts=experts(base)
        self.artifact={'version':VERSION,'contract_ref':CONTRACT,'base_gate':base.export(),'support':deepcopy(support)}
        self.artifact['artifact_ref']=digest(self.artifact)

    def export(self):return deepcopy(self.artifact)
    @classmethod
    def restore(cls,a):
        if a['version']!=VERSION or a['contract_ref']!=CONTRACT or a['artifact_ref']!=digest({k:v for k,v in a.items()if k!='artifact_ref'}):raise ValueError('Changed warrant gate')
        result=cls(fixed.VerifiedRegionGate.restore(a['base_gate']),a['support'])
        if result.export()!=a:raise ValueError('Noncanonical warrant gate')
        return result
    def accepts_task(self,program):
        try:fixed.shared.task_scope(program);return True
        except(ValueError,KeyError,TypeError):return False
    def select(self,program,record):
        baseline=self.base.select(program,record)
        if baseline['covered']:return baseline
        label=certificate(record)
        if label is None or not self.support['enabled'][str(label)]:return baseline
        values=fixed.shared.evidence.feature_values(program,record)
        if not fixed.passes(self.support['clauses'][str(label)],values):return baseline
        matched=[]
        for ref,ex in self.experts.items():
            result=ex.predict_records([record])[0]
            if result['prediction']==label:matched.append({'expert_ref':ref,**result})
        if not matched:return baseline
        return {'covered':True,'prediction':label,'reason':'certified_requirement_warrant','matches':matched,
                'warrant':'all_outcomes_satisfied'if label==2 else'all_outcomes_unsatisfied_without_progress',
                'support_ref':self.support['artifact_ref']}
    def select_bound(self,program,observation,pair_ref,interpretation):
        return self.select(program,fixed.shared.evidence.project(program,observation,pair_ref,interpretation))
