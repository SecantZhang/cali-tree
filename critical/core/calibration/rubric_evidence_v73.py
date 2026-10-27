"""Requirement-aligned rubric warrants and explicitly named judge-view cues.

Readiness predicates are shared logical rubric definitions, not learned quality
scores. A routing cue never asserts a physical failure from uncertainty alone.
"""
import math

from ..decision.artifacts import digest
from ..decision.bound_evidence_v2 import derive_record
from ..decision.semantic_interpretation_v5 import make_input, validate

SPECS = {
    'rubric_no_ready': 'Every requested requirement has coherent failure evidence: no goal-directed progress, only incidental change, a wrong endpoint/target, or loss of an essential instance, with an explicitly failed outcome/identity witness.',
    'rubric_partial_ready': 'At least one same requirement has coherent goal-directed progress with a known goal witness, or an achieved endpoint with a witnessed shortfall; complete success is not established for every requirement.',
    'rubric_yes_ready': 'Every same requirement has an achieved endpoint, all applicable physical outcome witnesses established, no endpoint gap, accepted identity, at most incidental collateral changes, and coherent evidence.',
    'rubric_uncertainty_any': 'At least one requirement has uncertain progress, endpoint gap, identity, collateral effects, or incoherent/insufficient evidence.',
    'rubric_endpoint_contradiction_any': 'One requirement simultaneously claims its requested endpoint and a missing or wrong core endpoint.',
    'rubric_physical_semantic_mismatch_any': 'For one requirement, its physical outcome witnesses and its interpreted progress disagree; this requests review, not a failure verdict.',
    'rubric_goal_witness_missing_any': 'For one requirement, the interpreter claims an achieved endpoint but no applicable physical outcome check establishes it.',
    'rubric_partial_witness_any': 'The same requirement has an established requested outcome or intermediate witness alongside a missing endpoint.',
    'rubric_identity_objection_to_authorized_change_any': 'A requirement authorizes replacement or a transformed counterpart but its interpretation records a material identity objection; review its scope.',
    'rubric_material_collateral_with_endpoint_any': 'The same requirement achieves its endpoint and records a material unauthorized collateral change.',
    'rubric_material_identity_with_endpoint_any': 'The same requirement achieves its endpoint and records a material identity shortfall.',
    'rubric_all_outcomes_false_any': 'A requirement has a nonempty applicable outcome family whose desired-state checks all explicitly fail.',
    'rubric_outcome_unknown_any': 'A requirement has an applicable physical outcome whose desired state is unknown.',
    'rubric_progress_without_endpoint_any': 'A requirement shows goal-directed progress without claiming the requested endpoint.',
    'rubric_duplicate_conflict_any': 'Exact duplicate bound physical checks disagree and are conservatively treated as unknown; review rather than vote over the duplicates.',
}

for label in ('no', 'partial', 'yes'):
    SPECS['view_regular_' + label] = 'The independent regular visual judge proposes ' + label + '; this is a model opinion, not an image fact.'
SPECS.update({
    'view_disagrees': 'The boosted and regular visual judges propose different available grades.',
    'view_teacher_unwarranted': 'The explicit semantic rubric does not establish the boosted proposal; this does not prove it wrong.',
    'view_regular_warranted': 'The explicit semantic rubric establishes the regular judge proposal.',
})
for threshold in (.5, .65, .8, .9):
    SPECS['view_top_support_lt_' + str(threshold)] = 'The boosted proposal has normalized model support below ' + str(threshold) + '; support is not calibrated correctness.'
for threshold in (.1, .2, .4, .6):
    SPECS['view_regular_margin_lt_' + str(threshold)] = 'The boosted proposal exceeds the regular proposal in normalized support by less than ' + str(threshold) + '; this is a model comparison.'

SEMANTIC = tuple(n for n in SPECS if n.startswith('rubric_'))
VIEWS = tuple(n for n in SPECS if n.startswith('view_'))
CONTRACT_REF = digest({'version': 'same-requirement-rubric-evidence-v73', 'specs': SPECS,
                       'binding': 'Existing authenticated program, observation and interpretation; same requirement IDs.',
                       'prohibited': 'Case/source/editor identities, object-name flags, reference labels, learned text vocabulary.'})


def project(program, observation, pair_ref, interpretation):
    if observation is None or interpretation is None:
        return None
    payload = make_input(program, observation, pair_ref)
    validate(payload, interpretation)
    bound = derive_record(program, observation, pair_ref)
    definitions={c['id']:c for c in program['checks']}
    requirement_definitions={r['id']:{k:v for k,v in r.items() if k not in ('id','check_ids')} for r in program['requirements']}
    memo={}
    def definition_ref(key):
        if key not in memo:
            c=definitions[key]
            body={k:v for k,v in c.items() if k not in ('id','check_ref','requirement_ids','dependencies')}
            body['requirements']=sorted({digest(requirement_definitions[r]) for r in c['requirement_ids']})
            body['dependencies']=sorted({definition_ref(k) for k in c['dependencies']})
            memo[key]=digest(body)
        return memo[key]
    flags = dict.fromkeys(SEMANTIC, False)
    failures, partials, successes = [], [], []
    for key, row in interpretation['requirements'].items():
        buckets={}
        for c in bound['checks'].values():
            if key in c['requirement_ids']:buckets.setdefault(definition_ref(c['id']),[]).append(c)
        checks=[]
        for rows in buckets.values():
            states={c['desired_state'] for c in rows}
            state=next(iter(states)) if len(states)==1 else 'unknown'
            flags['rubric_duplicate_conflict_any'] |= len(states)>1
            checks.append({'role':rows[0]['role'],'desired_state':state})
        outcome = [c['desired_state'] for c in checks if c['role'] == 'outcome' and c['desired_state'] != 'not_applicable']
        intermediate = [c['desired_state'] for c in checks if c['role'] == 'intermediate' and c['desired_state'] != 'not_applicable']
        identity_checks=[c['desired_state'] for c in checks if c['role']=='identity']
        endpoint = row['progress'] == 'requested_endpoint'
        coherent = row['evidence_consistency'] == 'coherent'
        identity = row['identity_materiality'] in ('no_shortfall', 'immaterial_difference', 'not_relevant')
        collateral = row['collateral_materiality'] in ('none', 'minor_incidental')
        success = endpoint and row['endpoint_gap'] == 'none' and identity and collateral and coherent and bool(outcome) and all(s=='true' for s in outcome)
        lost_essential = row['retention_need'] == 'same_instance_essential' and row['identity_evidence'] == 'replacement_or_loss'
        failure = coherent and (((row['progress'] in ('none', 'incidental_change_only') or row['endpoint_gap']=='wrong_direction_or_target') and 'false' in outcome) or
                                (lost_essential and 'false' in identity_checks))
        shortfall = (row['endpoint_gap'] in ('minor_detail', 'core_endpoint_missing', 'wrong_direction_or_target') or
                     row['identity_materiality'] == 'material_shortfall' or row['collateral_materiality'] == 'material_unrequested_change')
        partial = coherent and ((row['progress']=='toward_requested_goal' and any(s in ('true','false') for s in outcome+intermediate)) or
                                (endpoint and shortfall and 'true' in outcome))
        failures.append(failure); partials.append(partial); successes.append(success)
        uncertain = (row['progress'] == 'uncertain' or row['endpoint_gap'] == 'uncertain' or
                     row['identity_materiality'] == 'uncertain' or row['collateral_materiality'] == 'uncertain' or not coherent)
        flags['rubric_uncertainty_any'] |= uncertain
        flags['rubric_endpoint_contradiction_any'] |= endpoint and row['endpoint_gap'] in ('core_endpoint_missing', 'wrong_direction_or_target')
        flags['rubric_physical_semantic_mismatch_any'] |= bool(outcome) and ((endpoint and all(s == 'false' for s in outcome)) or
                                                (row['progress'] in ('none', 'incidental_change_only') and 'true' in outcome))
        flags['rubric_goal_witness_missing_any'] |= endpoint and 'true' not in outcome
        flags['rubric_partial_witness_any'] |= ('true' in outcome or 'true' in intermediate) and row['endpoint_gap'] in ('minor_detail', 'core_endpoint_missing')
        flags['rubric_identity_objection_to_authorized_change_any'] |= row['retention_need'] in ('replacement_authorized', 'recognizable_counterpart_sufficient') and row['identity_materiality'] == 'material_shortfall'
        flags['rubric_material_collateral_with_endpoint_any'] |= endpoint and row['collateral_materiality'] == 'material_unrequested_change'
        flags['rubric_material_identity_with_endpoint_any'] |= endpoint and row['identity_materiality'] == 'material_shortfall'
        flags['rubric_all_outcomes_false_any'] |= bool(outcome) and all(s == 'false' for s in outcome)
        flags['rubric_outcome_unknown_any'] |= 'unknown' in outcome
        flags['rubric_progress_without_endpoint_any'] |= row['progress'] == 'toward_requested_goal'
    flags['rubric_no_ready'] = bool(failures) and all(failures)
    flags['rubric_yes_ready'] = bool(successes) and all(successes)
    flags['rubric_partial_ready'] = any(partials) and not flags['rubric_yes_ready']
    return {n: bool(v) for n, v in flags.items()}


def views(semantic, support, regular):
    if len(support) != 3 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in support) or not math.isclose(sum(support), 1., abs_tol=1e-6):
        raise ValueError('Three normalized teacher supports required')
    if type(regular) is not int or regular not in (-1, 0, 1, 2):
        raise ValueError('Invalid independent judge grade')
    teacher = max(range(3), key=lambda c: (support[c], -c))
    flags = {'view_regular_' + name: regular == i for i, name in enumerate(('no', 'partial', 'yes'))}
    flags['view_disagrees'] = regular >= 0 and teacher != regular
    flags['view_teacher_unwarranted'] = not semantic['rubric_' + ('no', 'partial', 'yes')[teacher] + '_ready']
    flags['view_regular_warranted'] = regular >= 0 and semantic['rubric_' + ('no', 'partial', 'yes')[regular] + '_ready']
    for threshold in (.5, .65, .8, .9):
        flags['view_top_support_lt_' + str(threshold)] = support[teacher] < threshold
    for threshold in (.1, .2, .4, .6):
        flags['view_regular_margin_lt_' + str(threshold)] = regular >= 0 and support[teacher] - support[regular] < threshold
    return flags
