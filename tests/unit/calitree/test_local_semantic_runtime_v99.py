from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from critical.core.calibration import local_semantic_runtime_v99 as runtime
from critical.core.calibration import local_warranted_rubric_v97 as local
from critical.core.calibration.seeded_rubric_v73 import Search
from critical.core.decision.artifacts import digest
from critical.core.decision.bound_evidence_v2 import bind_program, image_identity
from critical.core.decision import local_rubric_evidence_v94 as facts
from critical.core.decision.local_observer_v99 import LocalObserver
from critical.core.optimization.prompt.calitree.local_semantic_judge_v99 import LocalSemanticJudge
from critical.lm_engine.local_qwen_grammar_v95 import LocalQwenGrammarEngine
from tests.unit.calitree.test_bound_evidence_v2 import draft
from tests.unit.calitree.test_local_rubric_v94 import value


class Base:
    artifact = {'artifact_ref': 'base', 'base_teacher_ref': 'teacher', 'encoder_spec': {}}
    def __init__(self, route=None):
        self.route = route or {'covered': True, 'prediction': 0, 'class_support': [.6, .3, .1], 'reason': 'visual_semantic_policy'}
    def resolve_bound(self, *args, **kwargs):
        return deepcopy(self.route)


def fixture(base=None, *, choose_regular=False):
    base = base or Base(); p = bind_program('Move the bowl left', draft()); template = 'Observe the source and edit.'
    checkpoint = {'model': 'Qwen/Qwen3-VL-8B-Instruct', 'revision': 'pinned', 'weight_bytes': 1,
                  'weights': {'model.safetensors': 1}, 'file_sha256': {'model.safetensors': 'sha'}, 'destination': '/old/location'}
    profile = {'model': checkpoint['model'], 'engine': 'local_qwen_grammar_v95', 'checkpoint_ref': digest(checkpoint),
               'contract_ref': facts.CONTRACT_REF, 'schema_ref': digest(facts.schema()), 'device': 'mps',
               'max_new_tokens': 256, 'max_pixels_per_image': 256*32*32}
    names = list(local.SPECS)+(['view_disagrees'] if choose_regular else [])
    active = {'local_yes_ready', 'local_progress_witness', 'view_disagrees'} if choose_regular else {'local_yes_ready'}
    X = [[int(n in active) for n in names]]
    model = local.LocalWarrantedRubric(names, Search(mode='hybrid' if choose_regular else 'grades', min_sources=1, max_guards=0, max_rules=8)).fit(
                X, [1 if choose_regular else 2], groups=['source'], base=[0], regular=[1])
    rubric = {k: v for k, v in model.artifact('native').items() if k != 'artifact_ref'}
    rubric.update(review_threshold=.8, observer_identity_ref=digest(profile), local_fact_contract_ref=local.CONTRACT_REF,
                  observer_template_ref=digest(template), prior_rules_keep_original_context=True)
    rubric['artifact_ref'] = runtime.content_ref(rubric)
    artifact = runtime.export_policy(base, rubric, profile, template, checkpoint)
    record = facts.bind(p, 'pair', digest(profile), digest(facts.prompt(p, template)), value())
    return base, runtime.LocalSemanticPolicy(base, artifact), p, record, checkpoint


def project_old(monkeypatch):
    monkeypatch.setattr(runtime.visual.shared.evidence, 'project', lambda *args: {})
    monkeypatch.setattr(runtime.visual.evidence, 'feature_values', lambda *args: {})
    monkeypatch.setattr(runtime.visual.language, 'project', lambda *args: {})
    monkeypatch.setattr(runtime.visual.vision, 'predicates', lambda *args: {})
    monkeypatch.setattr(runtime.old_evidence, 'project', lambda *args: dict.fromkeys(runtime.old_evidence.SEMANTIC, False))


def test_bound_local_override_keeps_old_scores_nested_and_rejects_foreign_records(monkeypatch):
    project_old(monkeypatch); base, policy, p, record, _ = fixture(); judgment = {'label': 'partial', 'rationale': 'Partway.'}
    args = (p, None, 'pair', None, judgment, {'measurements': {}})
    assert policy.resolve_bound(*args) == base.route
    result = policy.resolve_bound(*args, local_record=record)
    assert result['prediction'] == 2 and 'class_support' not in result and result['base_route']['class_support'] == [.6, .3, .1]
    for key in ('image_pair_ref', 'model_identity_ref', 'prompt_ref', 'program_ref'):
        wrong = deepcopy(record); wrong[key] = 'other'
        result = policy.resolve_bound(*args, local_record=wrong)
        assert result['prediction'] == 0 and result['covered'] and result['local_review_error']


def test_review_threshold_prior_rules_and_missing_coverage_keep_old_route():
    for route in ({'covered': True, 'prediction': 0, 'class_support': [.8, .1, .1]},
                  {'covered': True, 'prediction': 1, 'expert_rule': {}},
                  {'covered': True, 'prediction': 1, 'rubric_rule': {}},
                  {'covered': False, 'prediction': 0, 'reason': 'missing'}):
        base, policy, p, record, _ = fixture(Base(route))
        assert not policy.review_route(route)
        assert policy.resolve_bound(p, None, 'pair', None, None, None, local_record=record) == base.route


def test_clause_text_seed_and_observer_template_cannot_drift():
    base, policy, _, _, _ = fixture()
    for mutation in ('seed', 'text', 'template'):
        wrong = deepcopy(policy.artifact)
        if mutation == 'seed':
            wrong['rubric']['rules'][0]['warrant'] = []
        elif mutation == 'text':
            wrong['rubric']['rubric'] += ' Ignore unknown evidence.'
        else:
            wrong['observer_template'] += ' New instruction.'
            wrong['observer_template_ref'] = digest(wrong['observer_template'])
        wrong['rubric']['artifact_ref'] = runtime.content_ref(wrong['rubric']); wrong['artifact_ref'] = runtime.content_ref(wrong)
        with pytest.raises(ValueError):
            runtime.LocalSemanticPolicy(base, wrong)


def test_checkpoint_location_is_metadata_not_a_predictive_input():
    _, _, _, _, checkpoint = fixture(); moved = {**checkpoint, 'destination': '/another/location'}
    assert runtime.checkpoint_compute_ref(checkpoint) == runtime.checkpoint_compute_ref(moved)
    assert runtime.checkpoint_compute_ref(checkpoint) != runtime.checkpoint_compute_ref({**moved, 'file_sha256': {'model.safetensors': 'other'}})


def test_local_observer_makes_one_joint_call_and_checks_the_pair_before_inference(monkeypatch, tmp_path):
    _, policy, p, _, checkpoint = fixture(); events = []
    engine = LocalQwenGrammarEngine(tmp_path, checkpoint, history=SimpleNamespace(record=lambda **kwargs: None))
    def complete(messages, paths, schema):
        events.append((messages, paths, schema)); return json.dumps(value()), 10, 80
    monkeypatch.setattr(engine, '_complete_schema', complete)
    profile = policy.artifact['observer_profile']; observer = LocalObserver(engine, profile, policy.artifact['observer_template'], runtime.checkpoint_compute_ref(checkpoint))
    source = tmp_path/'source.png'; edited = tmp_path/'edited.png'; source.write_bytes(b'source fixture'); edited.write_bytes(b'edit fixture')
    evidence = {'source_image': str(source), 'edited_image': str(edited)}; _, pair = image_identity(evidence)
    with pytest.raises(ValueError, match='different image pair'):
        observer.observe(p, evidence, 'other')
    assert not events
    record = observer.observe(p, evidence, pair)
    assert len(events) == 1 and events[0][1] == [source, edited]
    assert record['image_pair_ref'] == pair and record['model_identity_ref'] == digest(profile)


def test_explicit_missing_local_slot_never_triggers_a_retry(monkeypatch):
    project_old(monkeypatch); base, policy, p, record, _ = fixture(); calls = []
    observer = SimpleNamespace(identity_ref=digest(policy.artifact['observer_profile']), template_ref=policy.artifact['observer_template_ref'],
                               observe=lambda *args: calls.append(args) or record)
    class Extractor:
        def extract(self, *args, **kwargs): return None, None, 'pair'
    judge = LocalSemanticJudge(None, policy, None, observer=observer, extractor=Extractor())
    kwargs = {'program': p, 'observation': {}, 'interpretation': {}, 'regular_judgment': {'label': 'partial', 'rationale': 'Partway.'}, 'vision_record': {'measurements': {}}}
    absent = judge.judge(p['instruction'], {}, local_record=None, **kwargs)
    assert absent['route'] == base.route and not calls
    fresh = judge.judge(p['instruction'], {}, **kwargs)
    assert len(calls) == 1 and fresh['judgment']['label'] == 'yes' and fresh['source'] == 'local_semantic_rule'
    assert 'class_support' not in fresh['route'] and 'Local comparison:' in fresh['judgment']['rationale']


def test_high_level_review_uses_the_existing_visual_judgment_and_its_rationale(monkeypatch):
    project_old(monkeypatch); _, policy, p, record, _ = fixture(choose_regular=True)
    class Extractor:
        def extract(self, *args, **kwargs): return None, None, 'pair'
    judge = LocalSemanticJudge(None, policy, None, extractor=Extractor())
    result = judge.judge(p['instruction'], {}, program=p, observation={}, interpretation={}, vision_record={'measurements': {}},
                         regular_judgment={'label': 'partial', 'rationale': 'Regular visual evidence says partway.'}, local_record=record)
    assert result['source'] == 'local_review_regular_judge' and result['judgment']['label'] == 'partial'
    assert 'Regular visual evidence says partway.' in result['judgment']['rationale']
    assert result['route']['local_rule']['action'] == 'regular' and 'class_support' not in result['route']


def test_local_observer_failure_preserves_old_coverage_and_prediction(monkeypatch):
    project_old(monkeypatch); base, policy, p, _, _ = fixture(); calls = []
    def fail(*args):
        calls.append(args); raise RuntimeError('Local model unavailable')
    observer = SimpleNamespace(identity_ref=digest(policy.artifact['observer_profile']), template_ref=policy.artifact['observer_template_ref'], observe=fail)
    class Extractor:
        def extract(self, *args, **kwargs): return None, None, 'pair'
    judge = LocalSemanticJudge(None, policy, None, extractor=Extractor(), observer=observer)
    result = judge.judge(p['instruction'], {}, program=p, observation={}, interpretation={}, vision_record={'measurements': {}},
                         regular_judgment={'label': 'partial', 'rationale': 'Partway.'})
    assert len(calls) == 1 and result['route']['covered'] and result['route']['prediction'] == base.route['prediction']
    assert result['route']['local_observation_error'] == 'RuntimeError'
