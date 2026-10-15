"""Label isolation, generic rich facts and constrained fitting without APIs."""
from copy import deepcopy
import json

from PIL import Image
import pytest

from critical.core.decision.calls import DurableCalls
from critical.core.decision.rich_evidence import COLLATERAL_FIELDS, RichEvidenceExtractor, base_observation, validate_rich
from critical.core.calibration.rich_local_rules import (
    DOMAIN, EDGES, LABELS, RichLocalRuleCalibrator, conflicts, decide, monotone, summarize, validate_tree,
)
from critical.core.calibration.local_evidence_rules import summarize as summarize_old


def record(*, integrity='material_deviation', loss='none', visibility='full'):
    instruction = 'Perform the requested edit'
    obs = {'instruction_scope': 'The requested transformation of the intended subject.',
           'target': {'state': 'matched', 'evidence': 'The intended subject is identifiable.'},
           'source_integrity': {'state': integrity, 'evidence': 'Source comparison observations.'},
           'requirements': [{'id': 'r', 'source_quote': instruction, 'question': 'Is the requested outcome realized?',
                             'role': 'core', 'state': 'complete', 'evidence': 'The requested outcome is visible.'}],
           'collateral': {k: {'state': 'none', 'evidence': 'No unauthorized change of this kind.'} for k in COLLATERAL_FIELDS},
           'verification_visibility': {'state': visibility, 'evidence': 'Relevant content visibility observation.'}}
    obs['collateral']['entity_loss']['state'] = loss
    obs['collateral']['appearance_drift']['state'] = 'present'
    return {'instruction': instruction, 'observations': obs}


def fitted():
    rows = [record(), record(), record(loss='present'), record(loss='present')]
    return RichLocalRuleCalibrator().fit(rows, [2, 2, 1, 1], source_groups=list('abcd'))


def test_richer_facts_separate_appearance_only_from_entity_loss_without_identity_rules():
    appearance, loss = record(), record(loss='present')
    assert summarize_old({**appearance, 'observations': base_observation(appearance['observations'])}) == summarize_old({**loss, 'observations': base_observation(loss['observations'])})
    assert summarize(appearance) != summarize(loss)
    assert fitted().predict([appearance, loss]) == [2., 1.]
    assert min(fitted().metadata()['leaf_support'].values()) >= 2


def test_visibility_can_distinguish_otherwise_complete_evidence_with_shared_support():
    full = record(integrity='preserved'); partial = record(integrity='preserved', visibility='partial')
    model = RichLocalRuleCalibrator().fit([full, full, partial, partial], [2, 2, 1, 1], source_groups=list('abcd'))
    assert model.predict([full, partial]) == [2., 1.]
    assert conflicts([full, partial], [2, 1])['feature_only_fitting_ceiling'] == 2


def test_known_evidence_improvements_never_lower_the_label():
    tree = fitted().metadata()['tree']; assert monotone(tree)
    scores = [LABELS.index(decide(tree, x)) for x in DOMAIN]
    assert len(DOMAIN) == 162 and all(scores[a] <= scores[b] for a, b in EDGES)


def test_unknown_new_facts_do_not_become_fitted_labels_and_decisive_no_is_preserved():
    unknown = record(); unknown['observations']['collateral']['entity_loss']['state'] = 'unknown'
    hidden = record(visibility='unobservable')
    wrong = deepcopy(unknown); wrong['observations']['target']['state'] = 'wrong_target'
    assert fitted().predict_records([unknown])[0]['label'] is None
    assert fitted().predict_records([hidden])[0]['label'] is None
    assert fitted().predict_records([wrong])[0]['label'] == 'no'


def test_text_and_identifier_renaming_cannot_change_rule_features():
    a = record(); b = deepcopy(a); b['instruction'] = 'A different instruction wording'
    o = b['observations']; o['instruction_scope'] = 'Renamed subjects and scene.'
    for fact in [o['target'], o['source_integrity'], *o['collateral'].values(), o['verification_visibility']]:
        fact['evidence'] = 'Entirely different descriptive vocabulary.'
    o['requirements'][0].update(id='renamed', source_quote=b['instruction'], question='Different wording?', evidence='New words.')
    assert summarize(a) == summarize(b)
    assert fitted().predict_records([a]) == fitted().predict_records([b])


@pytest.mark.parametrize('field', ['reference', 'human_score', 'case_id', 'task'])
def test_metadata_cannot_be_a_rule_input(field):
    value = record(); value[field] = 'forbidden'
    with pytest.raises(ValueError): summarize(value)


def test_missing_or_invalid_rich_facts_are_rejected():
    value = record(); del value['observations']['collateral']['entity_loss']
    with pytest.raises(ValueError): validate_rich(value['observations'], value['instruction'])
    value = record(); value['observations']['verification_visibility']['state'] = 'partial_means_target_label'
    with pytest.raises(ValueError): validate_rich(value['observations'], value['instruction'])


def test_portable_restore_and_forbidden_predicates():
    model = fitted(); restored = RichLocalRuleCalibrator.restore(json.loads(json.dumps(model.metadata())))
    assert restored.predict_records([record(), record(loss='present')]) == model.predict_records([record(), record(loss='present')])
    with pytest.raises(ValueError): validate_tree({'predicate': 'specific_object_name', 'when_true': {'label': 'yes'}, 'when_false': {'label': 'partial'}})


def test_extractor_makes_one_instruction_only_call_and_durable_replay(tmp_path):
    value = record(); evidence = {}
    for name in ('source_image', 'edited_image'):
        p = tmp_path / (name+'.png'); Image.new('RGB', (4, 4), 'red').save(p); evidence[name] = str(p)
    seen = []
    class Engine:
        def generate(self, prompt, **kwargs):
            seen.append((prompt, kwargs))
            return {'parsed': value['observations'], 'finishReason': 'stop', 'completionTokens': 100}
    calls = DurableCalls(tmp_path/'calls', lambda _: Engine(), identity={'model':'mock'}, max_calls=1, max_completion_tokens=2048)
    result = RichEvidenceExtractor(calls).extract(value['instruction'], evidence, max_tokens=2048)
    assert len(seen) == 1 and calls.budget['calls'] == 1
    assert seen[0][0].endswith('INPUT_JSON: '+json.dumps({'instruction': value['instruction']}))
    assert 'label' not in seen[0][1]['schema']['properties']
    assert [m['text'] for m in seen[0][1]['media_inputs'] if m['type']=='text'] == ['SOURCE image','EDITED image']
    def forbidden(_): raise AssertionError('Replay called the provider')
    replay = DurableCalls(tmp_path/'calls', forbidden, identity={'model':'mock'}, max_calls=1, max_completion_tokens=2048)
    assert RichEvidenceExtractor(replay).extract(value['instruction'], evidence, max_tokens=2048) == result
