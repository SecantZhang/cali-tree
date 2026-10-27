"""Source-bound cached opinions with no compulsory uncertainty prefilter.

Regular-judge verdicts are explicit model opinions. Goal completion excludes
blanket preservation caps but requires coherent endpoints and physical outcomes.
No oracle/reference information enters these proposals.
"""
from .facet_selector_v162 import FacetSelector, LEGACY, PREFIXES, execute as execute_selector
from . import rubric_evidence_v73 as evidence
from .visual_semantic_policy_v69 import regular_label
from ..decision.bound_evidence_v2 import derive_record
from ..decision.artifacts import digest

LABELS = ('no', 'partial', 'yes')
SEEDS = {k: 'cached_'+label+'_expert_ready' for k, label in enumerate(LABELS)}
SPECS = {}
for label in LABELS:
    SPECS['cached_'+label+'_expert_ready'] = 'At least one bound existing goal/fidelity opinion or the explicit regular visual judge proposes '+label+'. Disagreement is eligible for learned selection without a compulsory uncertainty flag; this is not a physical certificate.'
    SPECS['cached_regular_'+label] = 'The existing regular visual judge explicitly proposes '+label+'.'
    SPECS['cached_goal_'+label] = ('The existing same-requirement failure warrant proposes No.' if label == 'no' else
        'The existing same-requirement progress/material-shortfall warrant proposes Partial.' if label == 'partial' else
        'Every interpreted requirement coherently achieves its endpoint with no endpoint gap and all applicable outcome-role physical checks true; source preservation is separate competing evidence.')
DESCRIPTIONS = {**LEGACY, **SPECS}
CONTRACT_REF = digest({'version': 'cached-goal-regular-opinions-v170', 'specs': SPECS,
    'limit': 'Model opinions are not certified image facts. No source/case/editor identifier, reference label or oracle choice enters a proposal.'})


def allowed(name):
    return name in SPECS or (name in LEGACY and name.startswith(PREFIXES))


def project(program, observation, pair_ref, interpretation, judgment):
    flags = dict.fromkeys(SPECS, False)
    regular = regular_label(judgment)
    opinions = [False, False, False]
    if observation is not None and interpretation is not None:
        old = evidence.project(program, observation, pair_ref, interpretation)
        bound = derive_record(program, observation, pair_ref)
        complete = []
        for key, meaning in interpretation['requirements'].items():
            states = [r['desired_state'] for r in bound['checks'].values() if r['role'] == 'outcome' and
                      key in r['requirement_ids'] and r['desired_state'] != 'not_applicable']
            complete.append(meaning['progress'] == 'requested_endpoint' and meaning['endpoint_gap'] == 'none' and
                meaning['evidence_consistency'] == 'coherent' and bool(states) and all(s == 'true' for s in states))
        opinions = [old['rubric_no_ready'], old['rubric_partial_ready'], bool(complete) and all(complete)]
    for k, label in enumerate(LABELS):
        flags['cached_regular_'+label] = regular == k
        flags['cached_goal_'+label] = bool(opinions[k])
        flags[SEEDS[k]] = bool(opinions[k] or regular == k)
    return flags


class CachedOpinionSelector(FacetSelector):
    version = 'source-bound-cached-opinion-selector-v170'
    seed_names = SEEDS
    descriptions = DESCRIPTIONS
    contract_ref = CONTRACT_REF
    accepts_feature = staticmethod(allowed)
    rubric_intro = ('Inside the validated covered input route, apply the first matching opinion-selection region; otherwise retain V112.',
        'Each change requires an explicit regular or goal/fidelity grade opinion. These are model claims, not certified physical truth. Uncertainty alone never creates a grade; local counterexamples veto unsafe regions.')


def execute(artifact, values, grade, eligible):
    return execute_selector(artifact, values, grade, eligible, contract_ref=CONTRACT_REF, seed_names=SEEDS)
