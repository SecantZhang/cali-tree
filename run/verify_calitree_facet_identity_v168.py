"""Replay an identity overlay through real915-case inference with no new calls.

This is an inference-equivalence probe, never an accuracy experiment or a
trained replacement policy. Its empty rule set must preserve every parent result.
"""
import argparse
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from critical.core.optimization.prompt.calitree.current import CaliTreeJudge
from critical.core.optimization.prompt.calitree.facet_semantic_judge_v166 import FacetSemanticJudge
from critical.core.calibration.facet_runtime_v166 import FacetRegionPolicy
from critical.core.calibration.facet_selector_v162 import FacetSelector, allowed
from critical.core.calibration.independent_expert_v87 import record_from_job
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, VISION, read


def audit(out):
    if out.exists():
        raise ValueError('Fresh identity-overlay probe required')
    def forbidden(*args, **kwargs):
        raise AssertionError('Identity probe cannot call any observer, encoder or API')
    baseline = CaliTreeJudge(encoder=SimpleNamespace(compute=forbidden))
    d = load(CACHE, CACHE_AUDIT)
    f = next(f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision' and f['fold'] == 5)
    a, context, _ = contexts(d, f)
    names = [n for n in d['names'] if allowed(n)]; columns = [d['names'].index(n) for n in names]
    expected = np.asarray(a['full'][:, columns], dtype=np.float32) > np.float32(.5)
    # Explicit empty-rule probe, not a data-fitted selector. No policy file is
    # exported or selected, and the report contains no generalized accuracy.
    empty = FacetSelector(['facet_'+label+'_outcome_ready' for label in ('no', 'partial', 'yes')])
    empty.native_rules = []; empty.training = {'identity_equivalence_probe_only': True}
    selector = empty.artifact()
    binding = {'fold': 5, 'deployment_parent_artifact_ref': baseline.policy.artifact['artifact_ref'],
        'selector_artifact_ref': selector['artifact_ref'], 'priority': 'learned_semantic_precedence', 'legacy_float32_border': .5}
    policy = FacetRegionPolicy(baseline.policy, FacetRegionPolicy.export(baseline.policy, selector,
        'learned_semantic_precedence', training_binding=binding))
    class Capture(FacetSemanticJudge):
        last_values = None
        def _legacy_values(self, *args):
            self.last_values = super()._legacy_values(*args)
            return self.last_values
    overlay = Capture(policy, encoder=SimpleNamespace(compute=forbidden))
    raw = read(FROZEN/'replay_inputs_without_references.json'); hashes = read(VISION/'manifest.json')['image_hashes']
    expert_cache = {r['case']: r for r in read(ROOT/'logs/exps/261023-cached-sol-router-v85-r3/expert_provenance.json')}
    old_expected = {r['case']: r for r in read(ROOT/'logs/exps/261023-verified-semantic-compression-v112-r2/runtime_predictions.json')}
    rows = []; compared = 0; groups_by_pixel = {}
    out.mkdir(parents=True); (out/'run.log').write_text('Identity-overlay high-level cached replay started; no new model fits or calls.\n')
    (out/'llm-histories.log').write_text('No model/encoder calls; all old stages explicitly cached, empty facet regions.\n')
    for i, r in enumerate(raw):
        case = r['case']; assert case == d['examples'][i]['case']
        groups_by_pixel.setdefault(hashes[r['evidence']['source_image']], set()).add(d['examples'][i]['source_group'])
        pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']], hashes[r['evidence']['edited_image']]])
        expert = None
        if case in expert_cache:
            slot = expert_cache[case]['selected_slot']; contract = baseline.policy.base.artifact['expert_contract']
            assert file_hash(slot['job']) == slot['job_sha256']
            expert = record_from_job(r['program'], pair, slot['identity'], read(slot['job']), contract['schema'], contract['template'])
        measured = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
            'program_ref': r['program']['program_ref'], 'image_pair_ref': pair,
            'encoder_spec_ref': digest(baseline.policy.artifact['encoder_spec']),
            'measurements': read(VISION/'cases'/(case+'.json'))['measurements']}
        request = {'program': r['program'], 'observation': r['observation'], 'interpretation': r['interpretation'],
            'regular_judgment': r['judgment'], 'vision_record': measured,
            'expert_record': expert, 'local_record': d['local_records'].get(case)}
        original = baseline.judge(r['program']['instruction'], r['evidence'], **request)
        overlay.last_values = None
        # The unused invalid placeholder exercises the legacy pre-gate without
        # ever requesting or validating a new observation in an empty region.
        wrapped = overlay.judge(r['program']['instruction'], r['evidence'], facet_record={}, **request)
        for field in ('judgment', 'route', 'source', 'regular_execution_ref', 'regular_error', 'extraction_error'):
            assert wrapped[field] == original[field], (case, field)
        prediction = ('no', 'partial', 'yes').index(wrapped['judgment']['label']) if wrapped['judgment']['label'] != 'unresolved' else -1
        assert prediction == old_expected[case]['prediction'] == int(context['actual']['base'][i])
        assert wrapped['route']['covered'] == old_expected[case]['covered']
        if wrapped['route']['covered']:
            assert overlay.last_values is not None
            for j, name in enumerate(names):
                assert overlay.last_values[name] == bool(expected[i, j]), (case, name)
                compared += 1
        else:
            assert overlay.last_values is None
        rows.append({'case': case, 'prediction': prediction, 'covered': wrapped['route']['covered'], 'source': wrapped['source']})
        if (i+1)%150 == 0:
            print({'cached_requests_replayed': i+1}, flush=True)
    assert len(rows) == 915
    assert all(rows[i]['prediction'] == d['y'][i] for i in range(99))
    assert all(len(groups) == 1 for groups in groups_by_pixel.values())
    report = {'passed': True, 'probe_type': 'empty-rule inference identity, not a trained policy',
        'bound_requests_replayed': len(rows), 'judgments_routes_sources_unchanged': True,
        'actual_inference_legacy_predicate_comparisons': compared, 'original99_replayed_correct': 99,
        'distinct_source_pixels': len(groups_by_pixel), 'pixel_sources_split_across_groups': 0,
        'new_api_calls': 0, 'new_observer_calls': 0, 'new_encoder_calls': 0, 'real_selector_fits': 0,
        'new_accuracy_result': None, 'selected_policy_changed': False}
    save_json(out/'verification.json', report); save_json(out/'predictions.json', rows)
    sources = [Path(__file__), ROOT/'critical/core/optimization/prompt/calitree/facet_semantic_judge_v166.py',
        ROOT/'critical/core/calibration/facet_runtime_v166.py', ROOT/'critical/core/decision/facet_observation_v165.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources}, 'parent_policy_ref': baseline.policy.artifact['artifact_ref']})
    (out/'run.log').write_text('All915 judgments, routes, rationales and sources match selected v112; covered legacy features match native full-fit context. No trained model or accuracy improvement claimed.\n')
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.output_dir.resolve())
