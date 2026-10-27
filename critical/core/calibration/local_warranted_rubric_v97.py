"""Compact local-observer policies with task-relevant preservation warrants.

These are warrants from bound model claims, not certificates about pixels. The
global local-observer record cannot mix evidence across separate requirements:
only single-requirement inputs can justify a new grade through these warrants.
"""
from .seeded_rubric_v73 import SeededRubric, Search, DESCRIPTIONS as PREVIOUS
from .semantic_rubric_v70 import allowed_feature
from ..decision import local_rubric_evidence_v94 as facts
from ..decision.artifacts import digest

LABELS = ('no', 'partial', 'yes')
SPECS = {**facts.DESCRIPTIONS,
    'local_observation_available': 'A complete local observation is bound to this exact program, image pair, prompt and model profile.',
    'local_single_requirement': 'The compiled instruction contains exactly one requested requirement; global local-model claims therefore cannot borrow witnesses across different requirements.',
    'local_claim_conflict': 'The local model reports incompatible endpoint/progress, target/endpoint, or identity/authorized-replacement states. This requests fallback, not failure.',
    'local_any_uncertainty': 'At least one local observation state is uncertain; uncertainty alone never justifies No.',
    'local_progress_witness': 'The local model reports goal-directed progress on a corresponding/authorized target without contradictory claims; this can inform independent review, not a particular grade.',
    'local_view_teacher_unwarranted': 'The local observation does not establish an affirmative warrant for the current teacher proposal; this does not prove the proposal wrong.',
    'local_view_regular_warranted': 'The local observation supplies an affirmative warrant for the independent regular visual judge proposal.',
    'local_no_ready': 'For one requirement, the bound local model explicitly reports an absent or opposite endpoint, no goal-directed progress, and a known target state, without conflicting claims.',
    'local_partial_ready': 'For one requirement and a corresponding/authorized target, the bound local model reports goal-directed progress while the endpoint remains partly achieved or absent, or an achieved endpoint plus a known collateral change that affects the requested goal; claims are consistent.',
    'local_yes_ready': 'For one requirement, the bound local model reports a corresponding/authorized target, achieved endpoint and goal-directed progress; collateral is known and explicitly does not affect the goal, preservation scope and identity needs are known, and claims are consistent. Unrelated collateral is not an automatic cap.',
}
DESCRIPTIONS = {**PREVIOUS, **SPECS}
CONTRACT_REF = digest({'version': 'local-task-relevant-warrants-v97', 'observer_contract_ref': facts.CONTRACT_REF, 'specs': SPECS,
                       'limit': 'Concrete local grades require affirmative single-requirement warrants. Review clauses may select an existing independent visual judgment from disagreement/uncertainty; they do not invent a grade.'})


def claims(program, value):
    facts.validate(value)
    single = len(program['requirements']) == 1
    endpoint = value['endpoint']; progress = value['progress']; target = value['target']
    accepted = target in ('corresponding', 'authorized_replacement')
    conflict = ((endpoint in ('achieved', 'partly_achieved') and progress in ('none', 'incidental_only')) or
                (endpoint == 'opposite' and progress == 'goal_directed') or
                (target == 'wrong_or_missing' and endpoint == 'achieved') or
                (value['collateral'] == 'none' and value['collateral_affects_goal'] == 'yes') or
                (target == 'authorized_replacement' and value['same_instance_essential'] == 'yes'))
    no = (single and not conflict and target != 'uncertain' and endpoint in ('absent', 'opposite')
          and progress in ('none', 'incidental_only'))
    partial = (single and not conflict and accepted and progress == 'goal_directed' and
               (endpoint in ('partly_achieved', 'absent') or (endpoint == 'achieved' and value['collateral'] not in ('none', 'uncertain') and value['collateral_affects_goal'] == 'yes')))
    yes = (single and not conflict and accepted and endpoint == 'achieved' and progress == 'goal_directed' and
           value['collateral'] != 'uncertain' and value['collateral_affects_goal'] == 'no' and
           value['preservation_explicit'] != 'uncertain' and value['same_instance_essential'] != 'uncertain')
    flags = {f'local_{key}_{state}': value[key] == state for key, states in facts.FIELDS.items() for state in states}
    return {**dict.fromkeys(SPECS, False), **flags, 'local_observation_available': True,
            'local_single_requirement': single, 'local_claim_conflict': conflict,
            'local_progress_witness': accepted and progress == 'goal_directed' and not conflict,
            'local_any_uncertainty': any(value[k] == 'uncertain' for k in facts.FIELDS),
            'local_no_ready': bool(no), 'local_partial_ready': bool(partial), 'local_yes_ready': bool(yes)}


def view_flags(flags, teacher, regular):
    if type(teacher) is not int or teacher not in (0, 1, 2) or type(regular) is not int or regular not in (-1, 0, 1, 2):
        raise ValueError('Available teacher and optional regular labels required')
    if not flags.get('local_observation_available'):
        return {'local_view_teacher_unwarranted': False, 'local_view_regular_warranted': False}
    return {'local_view_teacher_unwarranted': not flags['local_'+LABELS[teacher]+'_ready'],
            'local_view_regular_warranted': regular >= 0 and flags['local_'+LABELS[regular]+'_ready']}


def project(program, pair_ref, model_ref, prompt_ref, record):
    facts.project(program, pair_ref, model_ref, prompt_ref, record)
    return claims(program, record['observation'])


class LocalWarrantedRubric(SeededRubric):
    version = 'local-task-preservation-rubric-v97'
    descriptions = DESCRIPTIONS
    evidence_specs = SPECS
    evidence_contract_ref = CONTRACT_REF

    def __init__(self, feature_names, config=None):
        config = config or Search(mode='grades', max_rules=8, min_sources=2)
        super().__init__(feature_names, config)

    def accepts_feature(self, name):
        return (name in SPECS or (name.startswith('view_') and name in PREVIOUS) or
                allowed_feature(name, self.config.family))

    def rule_seeds(self, action):
        if action == 'regular':
            return [(('view_disagrees', True), (reason, True)) for reason in
                    ('local_claim_conflict', 'local_any_uncertainty', 'local_progress_witness')] + [
                    (('view_disagrees', True), ('local_view_teacher_unwarranted', True), ('local_view_regular_warranted', True))]
        if action not in (0, 1, 2):
            raise ValueError('Local warrant required for a concrete grade')
        return [((f'local_{LABELS[action]}_ready', True),)]

    def render(self):
        lines = ['Apply these learned task/preservation clauses only inside the fixed review region, after existing v72/v87 rules.',
                 'Every concrete grade starts from a bound local-model warrant; every review clause selects the existing independent regular visual judgment. Otherwise retain the existing prediction.',
                 'Warrants describe model claims, not certified physical truth. Multi-requirement summaries and uncertainty alone cannot establish a concrete local grading warrant; review may select an existing visual judgment.']
        for label in LABELS:
            name = 'local_'+label+'_ready'; lines.append(name+': '+SPECS[name])
        for i, rule in enumerate(self.rules, 1):
            terms = ['the existing teacher proposes '+LABELS[rule['teacher_grade']]]
            terms += [self.descriptions[t['feature']] if t['value'] else 'Not established: '+self.descriptions[t['feature']] for t in rule['conditions']]
            action = 'use the independent regular visual judgment' if rule['action'] == 'regular' else 'grade '+LABELS[rule['action']]
            lines.append(str(i)+'. IF '+' AND '.join(terms)+' THEN '+action+'.')
        return '\n'.join(lines)+'\n'
