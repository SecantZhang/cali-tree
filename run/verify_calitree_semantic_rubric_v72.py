"""Audit source exclusions, re-induce rubrics and replay real bound inference."""
import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from catboost import CatBoostClassifier

from critical.core.calibration.semantic_rubric_v70 import Config
from critical.core.calibration.semantic_warrants_v71 import WarrantedRubric, warranted
from critical.core.calibration.semantic_rubric_compiler_v72 import simplify
from critical.core.calibration.semantic_rubric_runtime_v70 import SemanticRubricExecutor, SemanticRubricPolicy
from critical.core.calibration.visual_semantic_policy_v69 import VisualSemanticPolicy
from critical.core.optimization.prompt.calitree.semantic_rubric_judge_v70 import SemanticRubricJudge
from critical.core.decision.artifacts import digest, save_json
from critical.vision import paired_features_v69 as vision
from run.calitree_semantic_rubric_v70 import data, FROZEN, STUDY, VISION, ROOT, read, fingerprint
from run.calitree_warranted_rubric_v71 import TEACHERS, INNER
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS


def audit(study, out, candidate):
    if out.exists():
        raise ValueError('Fresh audit directory required')
    out.mkdir(parents=True)
    (out / 'run.log').write_text('Independent rubric/source-exclusion and bound-runtime audit in progress.\n')
    (out / 'llm-histories.log').write_text('Zero API calls; all regular/observer/interpreter stages supplied from immutable caches.\n')
    examples, names, X = data()
    y = np.asarray([r['reference'] for r in examples])
    groups = np.asarray([r['source_group'] for r in examples])
    positions = {e['case']: i for i, e in enumerate(examples)}
    columns = {n: i for i, n in enumerate(names)}
    valid = np.asarray([r['covered'] for r in examples])
    regular = np.asarray([r['regular'] for r in examples])
    manifest = read(study / 'manifest.json')
    assert digest(X.tolist()) == manifest['matrix_ref'] and digest(y.tolist()) == manifest['targets_ref']
    for file, expected in manifest['code_sha256'].items():
        snapshot = study / 'source_snapshot' / Path(file).relative_to(ROOT)
        assert fingerprint(snapshot) == expected
    reserved = read(ROOT / 'logs/exps/261020-validation-reservation-v39/inputs_without_labels.json')
    assert not set(groups) & {r['source_group'] for r in reserved}
    stored_rows = {r['case']: r for r in read(study / 'predictions.json') if r['candidate'] == candidate}
    baseline = {r['case']: r for r in read(STUDY / 'predictions.json') if r['candidate'] == 'boost_full_vision'}
    protections, rows, certificates, native_models = [], [], [], 0
    for f in (f for f in read(STUDY / 'folds.json') if f['candidate'] == 'boost_full_vision'):
        folder = study / ('fold' + str(f['fold']))
        membership = read(folder / 'memberships.json')
        train = [positions[c] for c in membership['train_cases']]
        held = [positions[c] for c in membership['held_cases']]
        assert membership['train_cases'] == f['train_cases'] and membership['held_cases'] == f['held_cases']
        assert train == [i for i in range(915) if groups[i] not in set(groups[held])]
        source = TEACHERS / folder.name
        info = read(source / 'teacher.json')['contract']
        cols = [columns[n] for n in info['columns']]
        assert info['rows'] == train and info['matrix_ref'] == digest(X[train][:, cols].tolist())
        model = CatBoostClassifier()
        model.load_model(str(source / 'teacher.cbm'))
        ps = model.predict_proba(X[:, cols], thread_count=2)
        saved = read(source / 'predictions.json')
        assert np.allclose(ps, saved['support'], atol=1e-12, rtol=0)
        native_models += 1
        proposed = np.argmax(ps, axis=1)
        proposed[~valid] = regular[~valid]
        assert np.all(proposed[:99] == y[:99])
        assert all(proposed[i] == baseline[examples[i]['case']]['direct'] for i in held)
        oof = proposed.copy()
        seen = set()
        for number, entry in enumerate(membership['inner_folds']):
            cache = INNER / folder.name / ('inner' + str(number))
            assert entry == read(cache / 'membership.json')
            outer_held, excluded = set(groups[held]), set(entry['held_sources'])
            expected_train = [i for i in train if groups[i] not in excluded]
            assert entry['train'] == expected_train
            assert entry['training_sources'] == sorted(set(groups[expected_train]))
            assert not set(groups[expected_train]) & (excluded | outer_held)
            assert not seen & excluded
            seen |= excluded
            meta = read(cache / 'teacher.json')['contract']
            cs = [columns[n] for n in meta['columns']]
            assert meta['rows'] == expected_train and meta['targets_ref'] == digest(y[expected_train].tolist())
            assert meta['matrix_ref'] == digest(X[expected_train][:, cs].tolist())
            inner_model = CatBoostClassifier()
            inner_model.load_model(str(cache / 'teacher.cbm'))
            inner_ps = inner_model.predict_proba(X[:, cs], thread_count=2)
            assert np.allclose(inner_ps, read(cache / 'predictions.json')['support'], atol=1e-12, rtol=0)
            native_models += 1
            indices = [i for i in train if groups[i] in excluded]
            oof[indices] = np.argmax(inner_ps[indices], axis=1)
        assert seen == set(groups[train]) - set(groups[:99])
        oof[~valid] = regular[~valid]
        original = read(folder / (candidate + '.json'))
        fit = [i for i in train if valid[i]]
        priority = {n: saved['priority'].get(n, 0.) + (1000. if n.startswith('meaning_') else 0.) for n in names}
        rebuilt = WarrantedRubric(names, Config(**original['config'])).fit(
            X[fit], y[fit], groups=groups[fit].tolist(), priority=priority, base_predictions=oof[fit],
            protected_X=X[:99], protected_y=y[:99], protected_base=proposed[:99])
        assert rebuilt.artifact(original['teacher_ref']) == original
        compiled, certificate = simplify(original)
        certificates.append(certificate)
        save_json(out / folder.name / 'rubric.json', compiled)
        save_json(out / folder.name / 'equivalence.json', certificate)
        (out / folder.name / 'rubric.txt').write_text(compiled['rubric'])
        executor, before = SemanticRubricExecutor(compiled), SemanticRubricExecutor(original)
        predictions = []
        needed = set(original['feature_names']) | set(compiled['feature_names'])
        for i in range(915):
            values = {n: bool(X[i, columns[n]]) for n in needed}
            after = executor.select(values, int(proposed[i]))['prediction'] if valid[i] else int(regular[i])
            previous = before.select(values, int(proposed[i]))['prediction'] if valid[i] else int(regular[i])
            assert after == previous
            predictions.append(after)
        assert predictions[:99] == y[:99].tolist()
        slots = 0
        for bank in (1, 2, 3):
            local = old_inputs(PREVIOUS, bank)[3]['local']
            assert len(local) == 48
            for item in local:
                assert predictions[positions[item['case']]] == item['reference']
                slots += 1
        assert slots == 144
        protections.append({'fold': f['fold'], 'original_correct': 99, 'training_slots_correct': slots})
        for i in held:
            case = examples[i]['case']
            assert predictions[i] == stored_rows[case]['prediction']
            rows.append({**examples[i], 'teacher': int(proposed[i]), 'prediction': predictions[i]})
        assert all(warranted(r['prediction'], r['conditions']) for r in compiled['rules'])
        if f['fold'] == 5:
            full_rubric, full_predictions = compiled, predictions
        print({'audited_fold': f['fold'], 'native_models_checked': native_models, 'slots_retained': slots}, flush=True)
    save_json(out / 'rubric.json', full_rubric)
    (out / 'rubric.txt').write_text(full_rubric['rubric'])
    teacher_artifact = read(FROZEN / 'policy.json')
    wrapper = SemanticRubricPolicy(VisualSemanticPolicy(teacher_artifact), full_rubric)
    def forbidden(*args, **kwargs):
        raise AssertionError('Audit must not call a model or encode new evidence')
    judge = SemanticRubricJudge(None, wrapper, SimpleNamespace(compute=forbidden))
    runtime_rows = []
    for i, raw in enumerate(read(FROZEN / 'replay_inputs_without_references.json')):
        assert raw['case'] == examples[i]['case']
        measured = read(VISION / 'cases' / (raw['case'] + '.json'))['measurements']
        visual = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
                  'program_ref': raw['program']['program_ref'],
                  'image_pair_ref': raw['observation']['image_pair_ref'] if raw['observation'] else None,
                  'encoder_spec_ref': digest(teacher_artifact['encoder_spec']), 'measurements': measured}
        result = judge.judge(raw['program']['instruction'], raw['evidence'], program=raw['program'],
                  observation=raw['observation'], interpretation=raw['interpretation'],
                  regular_judgment=raw['judgment'], vision_record=visual)
        predicted = ('no', 'partial', 'yes').index(result['judgment']['label']) if result['judgment']['label'] != 'unresolved' else -1
        assert predicted == full_predictions[i] and result['route']['covered'] == bool(valid[i]), raw['case']
        if result['route'].get('reason') == 'semantic_rubric_override':
            assert 'class_support' not in result['route'] and 'teacher_route' in result['route']
        runtime_rows.append({'case': raw['case'], 'prediction': predicted, 'covered': result['route']['covered'], 'source': result['source']})
        if (i + 1) % 100 == 0:
            print({'bound_runtime_cases': i + 1}, flush=True)
    correct = sum(r['prediction'] == r['reference'] for r in rows)
    result = {'passed': True, 'candidate': candidate, 'correct': correct, 'total': len(rows), 'accuracy': correct / len(rows),
              'teacher_correct': sum(r['teacher'] == r['reference'] for r in rows),
              'gains': sum(r['prediction'] == r['reference'] != r['teacher'] for r in rows),
              'losses': sum(r['teacher'] == r['reference'] != r['prediction'] for r in rows),
              'coverage': sum(r['covered'] for r in rows), 'native_teacher_models_checked': native_models,
              'reinduced_rubrics': len(protections), 'original_cases_retained_per_fit': 99,
              'original_slots_retained_per_fit': 144, 'runtime_replay_cases': len(runtime_rows),
              'all_any_equivalence_certificates': len(certificates), 'frozen_rules': len(full_rubric['rules']),
              'frozen_literals': sum(len(r['conditions']) for r in full_rubric['rules']),
              'new_paid_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False,
              'scope': 'Source-held development after model selection. Compact semantic correction layer with v69 fallback; not full-ensemble replacement or standalone prose-only LLM validation.'}
    save_json(out / 'verification.json', result)
    save_json(out / 'predictions.json', rows)
    save_json(out / 'runtime_predictions.json', runtime_rows)
    save_json(out / 'retention.json', protections)
    save_json(out / 'manifest.json', {'auditor_sha256': fingerprint(__file__), 'rubric_ref': full_rubric['artifact_ref'],
                                    'teacher_ref': teacher_artifact['artifact_ref'], 'study_manifest_sha256': fingerprint(study / 'manifest.json')})
    (out / 'run.log').write_text('Independently checked36 native models, re-induced six rubrics, certified semantic simplification, retained every original144-slot view, and replayed915 bound high-level judgments.\n')
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--candidate', default='auxiliary_correct')
    args = parser.parse_args()
    audit(args.study.resolve(), args.output_dir.resolve(), args.candidate)
