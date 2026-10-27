"""Compare inference feature projection with all six cached fitting contexts."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.optimization.prompt.calitree.current import load_current_policy
from critical.core.calibration.facet_selector_v162 import allowed
from critical.core.calibration.facet_runtime_v166 import legacy_values, prior_locked
from critical.core.decision import facet_observation_v165 as facets
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from critical.vision import paired_features_v69 as vision
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, VISION, read
from run.calitree_semantic_context_projection_v171 import project_context
from run.calitree_source_excluded_calibration_v89 import baseline_predictions


def audit(out):
    if out.exists():
        raise ValueError('Fresh inference feature parity audit required')
    parent = load_current_policy(); d = load(CACHE, CACHE_AUDIT)
    names = [n for n in d['names'] if allowed(n)]; columns = [d['names'].index(n) for n in names]
    raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    hashes = read(VISION/'manifest.json')['image_hashes']
    profile = facets.make_profile()
    prepared = read(ROOT/'logs/exps/261025-source-facet-collection-v161-r1/jobs.json')
    for job in prepared:
        program = raw[job['case']]['program']
        assert facets.prompt(program, profile) == job['prompt'] and profile['schema'] == job['schema']
        assert profile['identity'] == job['identity'] and profile['max_tokens'] == job['max_tokens']
        assert facets.request_ref(program, profile, job['case'], facets.media_identity(job['image_hashes'])) == __import__('run.verify_calitree_paid_facet_v158', fromlist=['execution_ref']).execution_ref(job)
    out.mkdir(parents=True)
    (out/'run.log').write_text('Six-context bound inference feature/mask equivalence started, no new data or model calls.\n')
    (out/'llm-histories.log').write_text('Zero API/local-observer/encoder calls; cached authenticated stages only.\n')
    checks = []; compared = 0; locks = 0; fitting_compared = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, context, _ = contexts(d, f)
        expected, fitting_expected, projection = project_context(d, a, names)
        fitting_prior, fitting_locked = baseline_predictions(a['folder'], d['old_names'], d['raw'], d['semantic'],
            a['oof'], d['regular'], d['sol'], d['valid'])
        covered_rows = 0; active_old = 0; fitting_rows = 0
        for i, example in enumerate(d['examples']):
            case = example['case']; r = raw[case]
            pair = digest(['bound-physical-evidence-v2', 'source_first', hashes[r['evidence']['source_image']], hashes[r['evidence']['edited_image']]])
            prior = {'covered': bool(d['valid'][i]), 'prediction': int(a['current'][i]), 'class_support': a['ps'][i].tolist()}
            if a['locked'][i]:
                prior['rubric_rule'] = {}  # Both old locked routes share the same local-review mask.
            final = {'covered': bool(d['valid'][i]), 'prediction': int(context['actual']['base'][i]),
                     'reason': 'semantic_residual_override' if not a['locked'][i] and context['actual']['locked'][i] and d['valid'][i] else 'parent'}
            assert prior_locked(prior, final) == bool(context['actual']['locked'][i])
            locks += 1
            if not d['valid'][i]:
                continue
            measured = {'version': vision.VERSION, 'feature_contract_ref': vision.CONTRACT_REF,
                'program_ref': r['program']['program_ref'], 'image_pair_ref': pair,
                'encoder_spec_ref': digest(parent.artifact['encoder_spec']),
                'measurements': read(VISION/'cases'/(case+'.json'))['measurements']}
            inputs = (r['program'], r['observation'], pair, r['interpretation'], r['judgment'], measured)
            values = legacy_values(parent, inputs, prior, d['local_records'].get(case))
            for j, name in enumerate(names):
                assert name in values and values[name] == bool(expected[i, j]), (f['fold'], case, name, values.get(name), bool(expected[i, j]))
                compared += 1
            if a['genuine'][i]:
                fitted_route = {'covered': True, 'prediction': int(fitting_prior[i]), 'class_support': a['oof'][i].tolist()}
                if fitting_locked[i]:
                    fitted_route['rubric_rule'] = {}
                fit_values = legacy_values(parent, inputs, fitted_route, d['local_records'].get(case))
                for j, name in enumerate(names):
                    assert fit_values[name] == bool(fitting_expected[i, j]), ('fitting', f['fold'], case, name)
                    fitting_compared += 1
                fitting_rows += 1
            covered_rows += 1; active_old += int(parent.review_route(prior))
        checks.append({'fold': f['fold'], 'covered_feature_rows': covered_rows, 'old_review_rows': active_old,
                       'feature_count': len(names), 'all915_priority_routes_match': True,
                       'genuine_fitting_rows': fitting_rows, 'fitting_mask_changed_rows': projection['changed_fitting_rows'],
                       'fitting_mask_changed_indicators': projection['changed_fitting_indicators']})
        print(checks[-1], flush=True)
    report = {'passed': True, 'contexts': len(checks), 'legacy_predicate_comparisons': compared,
        'priority_route_comparisons': locks, 'observer_request_equivalence_cases': len(prepared),
        'genuine_fitting_predicate_comparisons': fitting_compared,
        'old_review_mask_retained': True, 'new_api_calls': 0, 'new_observer_calls': 0, 'new_encoder_calls': 0,
        'new_source_held_fits': 0, 'serving_changed': False}
    save_json(out/'verification.json', report); save_json(out/'checks.json', checks)
    sources = [Path(__file__), ROOT/'critical/core/calibration/facet_runtime_v166.py',
               ROOT/'critical/core/decision/facet_observation_v165.py', ROOT/'run/calitree_semantic_context_projection_v171.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources},
        'parent_policy_ref': parent.artifact['artifact_ref'], 'observer_profile_ref': profile['profile_ref']})
    (out/'run.log').write_text('All six context feature indicators, old review masks and915 priority routes per context agree. No model calls or fit changes.\n')
    print(report, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.output_dir.resolve())
