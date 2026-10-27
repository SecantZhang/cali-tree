"""Optional, request-bound independent judge selected by explicit review rules.

This module makes no model calls. Missing/invalid independent evidence retains
the existing semantic hybrid, including its coverage and regular fallback.
"""
from copy import deepcopy

from .seeded_rubric_v73 import SeededRubric,Search,seeds
from . import rubric_evidence_v73 as evidence
from . import visual_semantic_policy_v69 as visual
from .semantic_rubric_v70 import allowed_feature
from ..decision.artifacts import digest
from ..decision.bound_evidence_v2 import validate_program

VERSION='bound-independent-expert-hybrid-v87'
RECORD_VERSION='bound-generic-visual-judge-record-v87'
LABELS=('no','partial','yes')


def content_ref(value):return digest({k:v for k,v in value.items() if k!='artifact_ref'})


class ExpertGate:
    def __init__(self,artifact):
        if artifact.get('artifact_ref')!=content_ref(artifact) or artifact.get('version')!=SeededRubric.version or artifact.get('evidence_contract_ref')!=evidence.CONTRACT_REF:
            raise ValueError('Changed or incompatible expert gate')
        config=Search(**artifact['config'])
        if config.mode!='routes' or artifact.get('selected_expert')!='gpt-6.1-sol':raise ValueError('Independent Sol routing rules required')
        names=artifact['feature_names']
        if len(artifact['rules'])>config.max_rules or any(n not in evidence.SPECS and not allowed_feature(n,config.family) for n in names):raise ValueError('Gate exceeds its declared semantic vocabulary')
        self.model=SeededRubric(names or ['view_disagrees'],config);self.model.rules=deepcopy(artifact['rules'])
        used=set()
        for rule in self.model.rules:
            if rule['action']!='regular' or rule['teacher_grade'] not in (0,1,2):raise ValueError('Gate cannot invent a grade')
            conditions=rule['conditions'];terms={(t['feature'],t['value']) for t in conditions}
            if len(terms)!=len(conditions) or any(type(t['value']) is not bool or t['feature'] not in names for t in conditions):raise ValueError('Invalid gate condition')
            seed=tuple((t['feature'],t['value']) for t in rule['warrant'])
            if seed not in seeds('regular') or not set(seed)<=terms or len(conditions)>len(seed)+config.max_guards:raise ValueError('A positive semantic review seed is required')
            support=rule['support']
            if any(type(support[k]) is not int or support[k]<0 for k in ('gain_sources','gains','losses')) or support['gain_sources']<config.min_sources or support['gains']<support['gain_sources']:raise ValueError('Invalid source support')
            used.update(t['feature'] for t in conditions)
        if sorted(used)!=names or self.model.render()!=artifact['rubric']:raise ValueError('Rendered gate differs from its executable rules')
        self.artifact=deepcopy(artifact)

    def select(self,values,teacher,expert):
        if type(teacher) is not int or teacher not in (0,1,2) or type(expert) is not int or expert not in (0,1,2):raise ValueError('Available judge labels required')
        if any(type(values.get(n)) is not bool for n in self.artifact['feature_names']):raise ValueError('Named Boolean gate evidence required')
        for index,rule in enumerate(self.model.rules):
            if rule['teacher_grade']==teacher and all(values[t['feature']]==t['value'] for t in rule['conditions']):
                return {'prediction':expert,'rule_index':index,'conditions':deepcopy(rule['conditions'])}
        return None


def validate_record(program,pair_ref,record,contract):
    validate_program(program)
    if not isinstance(record,dict) or set(record)!={'version','program_ref','image_pair_ref','request','execution_ref','judgment'} or record['version']!=RECORD_VERSION or record['program_ref']!=program['program_ref'] or record['image_pair_ref']!=pair_ref:raise ValueError('Independent judgment binding mismatch')
    request=record['request']
    if set(request)!={'identity','case_id','stage','payload','schema','template','media_identity','slot','max_tokens'} or request['stage']!='flat_judge' or request['payload']!={'instruction':program['instruction']} or request['identity'] not in contract['identities'] or request['schema']!=contract['schema'] or request['template']!=contract['template']:raise ValueError('Changed independent judge request contract')
    if type(request['max_tokens']) is not int or request['max_tokens']<=0 or not isinstance(request['slot'],str) or not request['slot'] or not isinstance(request['case_id'],str):raise ValueError('Invalid independent request slot')
    media=request['media_identity']
    if len(media)!=4 or media[0]!={'type':'text','text':'SOURCE image'} or media[2]!={'type':'text','text':'EDITED image'} or any(set(media[i])!={'type','sha256'} or media[i]['type']!='image' or not isinstance(media[i]['sha256'],str) or len(media[i]['sha256'])!=64 for i in (1,3)):raise ValueError('Ordered source/edited image identity required')
    if digest(['bound-physical-evidence-v2','source_first',media[1]['sha256'],media[3]['sha256']])!=pair_ref:raise ValueError('Independent judgment images differ')
    ref=digest([request[k] for k in ('identity','case_id','stage','payload','schema','template','media_identity','slot','max_tokens')])
    if ref!=record['execution_ref']:raise ValueError('Independent request hash mismatch')
    judgment=record['judgment']
    if not isinstance(judgment,dict) or set(judgment)!={'label','rationale'} or judgment['label'] not in LABELS or not isinstance(judgment['rationale'],str) or not judgment['rationale'].strip():raise ValueError('Valid independent judgment required')
    return LABELS.index(judgment['label'])


def record_from_job(program,pair_ref,identity,job,schema,template):
    if job.get('outcome')!='completed' or not isinstance(job.get('parsed'),dict):return None
    return {'version':RECORD_VERSION,'program_ref':program['program_ref'],'image_pair_ref':pair_ref,
        'request':{'identity':deepcopy(identity),**{k:deepcopy(job[k]) for k in ('case_id','stage','payload','media_identity','slot','max_tokens')},'schema':deepcopy(schema),'template':template},
        'execution_ref':job['execution_ref'],'judgment':deepcopy(job['parsed'])}


def export_expert_policy(base,gate,contract):
    # The exporter/auditor proves native/full teacher equivalence before rebinding
    # a fit-contract identity to the portable v69 classifier identity.
    compiled=deepcopy(gate);compiled['native_teacher_ref']=compiled['teacher_ref'];compiled['teacher_ref']=base.teacher.artifact['artifact_ref'];compiled['artifact_ref']=content_ref(compiled)
    artifact={'version':VERSION,'base_ref':base.artifact['artifact_ref'],'base_teacher_ref':base.teacher.artifact['artifact_ref'],
        'gate':compiled,'expert_contract':deepcopy(contract),'evidence_contract_ref':evidence.CONTRACT_REF,'encoder_spec':base.artifact['encoder_spec']}
    artifact['artifact_ref']=content_ref(artifact)
    IndependentExpertPolicy(base,artifact)
    return artifact


class IndependentExpertPolicy:
    def __init__(self,base,artifact):
        if artifact.get('artifact_ref')!=content_ref(artifact) or artifact.get('version')!=VERSION or artifact.get('evidence_contract_ref')!=evidence.CONTRACT_REF or artifact['base_ref']!=base.artifact['artifact_ref'] or artifact['base_teacher_ref']!=base.teacher.artifact['artifact_ref'] or artifact['gate']['teacher_ref']!=artifact['base_teacher_ref']:raise ValueError('Expert gate belongs to a different base')
        contract=artifact['expert_contract']
        if set(contract)!={'identities','schema','template'} or not contract['identities'] or any(i.get('model')!='gpt-6.1-sol' or i.get('provider')!='openai' for i in contract['identities']):raise ValueError('Declared independent Sol request profiles required')
        self.base,self.artifact,self.gate=base,deepcopy(artifact),ExpertGate(artifact['gate'])

    def _values(self,program,observation,pair_ref,interpretation,judgment,vision_record,base,expert):
        projected=visual.shared.evidence.project(program,observation,pair_ref,interpretation)
        semantic=evidence.project(program,observation,pair_ref,interpretation)
        if semantic is None:raise ValueError('Missing semantic gate evidence')
        regular=visual.regular_label(judgment)
        return {**visual.evidence.feature_values(program,projected),**visual.language.project(program,judgment),
            **visual.vision.predicates(vision_record['measurements']),'evidence_missing':False,
            **{'judge_predicts_'+name:regular==label for name,label in zip(('unresolved',*LABELS),(-1,0,1,2))},
            **semantic,**evidence.views(semantic,base['class_support'],expert)}

    def review_bound(self,program,observation,pair_ref,interpretation,judgment,vision_record):
        """Identify a review region without inventing the independent verdict."""
        base=self.base.resolve_bound(program,observation,pair_ref,interpretation,judgment,vision_record)
        result={'review_needed':False,'possible_independent_labels':[],'base_route':base}
        if not base['covered'] or base.get('rubric_rule') is not None:return result
        try:
            for label in range(3):
                values=self._values(program,observation,pair_ref,interpretation,judgment,vision_record,base,label)
                rule=self.gate.select(values,int(base['prediction']),label)
                if rule is not None and rule['prediction']!=base['prediction']:result['possible_independent_labels'].append(LABELS[label])
        except (ValueError,KeyError,TypeError):return {**result,'possible_independent_labels':[],'independent_expert_error':'invalid_semantic_gate_evidence'}
        result['review_needed']=bool(result['possible_independent_labels'])
        return result

    def resolve_bound(self,program,observation,pair_ref,interpretation,judgment,vision_record,*,expert_record=None):
        base=self.base.resolve_bound(program,observation,pair_ref,interpretation,judgment,vision_record)
        if not base['covered'] or base.get('rubric_rule') is not None or expert_record is None:return base
        try:
            expert=validate_record(program,pair_ref,expert_record,self.artifact['expert_contract'])
            values=self._values(program,observation,pair_ref,interpretation,judgment,vision_record,base,expert)
            rule=self.gate.select(values,int(base['prediction']),expert)
        except (ValueError,KeyError,TypeError):return {**base,'independent_expert_error':'invalid_or_unbound_record'}
        if rule is None:return base
        return {'covered':True,'prediction':expert,'reason':'independent_expert_override','expert_rule':rule,
            'expert_execution_ref':expert_record['execution_ref'],'expert_identity':deepcopy(expert_record['request']['identity']),'base_route':base}
