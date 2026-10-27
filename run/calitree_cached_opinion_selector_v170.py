"""Learn source-held cached-expert routing with no new neural measurements."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.cached_opinion_selector_v170 import CachedOpinionSelector, SPECS, allowed, project, execute
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, FROZEN, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS
from run.calitree_semantic_context_projection_v171 import project_context

CONFIGS = [(priority, guards, loss) for priority in ('retain_prior_priority', 'learned_semantic_precedence')
           for guards in (1, 2) for loss in (1., 2.)]
PRIMARY = ('learned_semantic_precedence', 2, 2.)


def name_of(priority, guards, loss):
    return priority+'_guards'+str(guards)+'_loss'+str(loss)


def run(out):
    if out.exists():
        raise ValueError('Fresh cached-opinion study required')
    protocol = {'version': 'source-held-cached-opinion-selection-v170', 'configs': CONFIGS, 'primary': PRIMARY,
        'hypothesis': 'An explicit regular verdict is already a distinct model opinion; do not require an extra uncertainty/progress cue before learned expert selection. Add physical goal completion independent of blanket identity/preservation caps.',
        'adaptation': 'Motivated by fitting-only v160 rubric errors and reference-informed v169 proposal ceilings. Those oracle choices/labels never enter inference features. This remains repeated source-held development research, not an untouched final test.',
        'capacity': 'At most4 rules, one explicit opinion seed plus1/2 named guards, at least3 supporting sources; class-normalized gain minus1/2 times loss; actual99-original veto and144-slot recheck.',
        'data': 'Existing915 cached inputs only. Genuine fold-training teacher views; every held-source sibling excluded. Earlier V112 residual fitting views reused, not independently inner-cross-fitted.',
        'coverage': 'Existing valid/covered route only; every276-case prediction including fallback remains counted. Missing opinions retain V112.',
        'projection': 'Only new-selector fitting copies zero old local fields outside the executable old review route, including prior-locked rows. Frozen parent fitting views/predictions are unchanged.',
        'new_api_calls': 0, 'new_neural_or_encoder_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Source-held cached opinion selection started; no new image observations or model calls.\n')
    (out/'llm-histories.log').write_text('Zero API/observer/encoder calls. Frozen cached program/physical/interpretation/regular data only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/cached_opinion_selector_v170.py',
        ROOT/'critical/core/calibration/facet_selector_v162.py', ROOT/'run/calitree_compact_balance_v143.py',
        ROOT/'run/calitree_semantic_context_projection_v171.py']
    hashes = {str(p): file_hash(p) for p in files}
    for p in files:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    d = load(CACHE, CACHE_AUDIT); raw = {r['case']: r for r in read(FROZEN/'replay_inputs_without_references.json')}
    extra_names = list(SPECS); extra = []
    for e in d['examples']:
        r = raw[e['case']]; pair = r['observation']['image_pair_ref'] if r['observation'] else None
        values = project(r['program'], r['observation'], pair, r['interpretation'], r['judgment'])
        extra.append([values[n] for n in extra_names])
    extra = np.asarray(extra, dtype=bool)
    legacy = [n for n in d['names'] if allowed(n)]; columns = [d['names'].index(n) for n in legacy]
    names = legacy+extra_names; assert len(names) == len(set(names))
    protected_slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    expected = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    rows = []; memberships = []; retained = []; scalar_replays = 0
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, context, fit = contexts(d, f); full, fitting = context['actual'], context['fitting']
        assert not set(d['groups'][fit])&set(d['groups'][a['held']])
        actual_legacy, fitting_legacy, projection = project_context(d, a, legacy)
        actual_X = np.c_[actual_legacy, extra]; fitting_X = np.c_[fitting_legacy, extra]
        memberships.append({'fold': f['fold'], 'fit_cases': [d['examples'][i]['case'] for i in fit],
            'fit_source_groups': sorted(set(d['groups'][fit])), 'held_cases': f['held_cases'],
            'projection_changed_rows': projection['changed_fitting_rows'],
            'projection_changed_indicators': projection['changed_fitting_indicators']})
        for priority, guards, loss in CONFIGS:
            name = name_of(priority, guards, loss)
            actual_eligible = d['valid'] & (~full['locked'] if priority == 'retain_prior_priority' else True)
            fit_eligible = d['valid'] & (~fitting['locked'] if priority == 'retain_prior_priority' else True)
            model = CachedOpinionSelector(names, guards=guards, loss_cost=loss).fit(fitting_X[fit], d['y'][fit],
                base=fitting['base'][fit], eligible=fit_eligible[fit], groups=d['groups'][fit],
                protected_X=actual_X[:99], protected_y=d['y'][:99], protected_base=full['base'][:99], protected_eligible=actual_eligible[:99])
            p = model.predict(actual_X, base=full['base'], eligible=actual_eligible)
            assert np.array_equal(p, model._predict(actual_X, full['base'], actual_eligible, model.native_rules))
            artifact = model.artifact(); used = artifact['feature_names']; used_columns = [names.index(n) for n in used]
            for i in range(len(p)):
                values = {n: bool(actual_X[i, j]) for n, j in zip(used, used_columns)}
                assert execute(artifact, values, int(full['base'][i]), bool(actual_eligible[i])) == p[i]
            scalar_replays += len(p)
            assert np.all(p[:99] == d['y'][:99])
            assert sum(p[d['pos'][r['case']]] == r['reference'] for r in protected_slots) == 144
            assert np.array_equal(p[~actual_eligible], full['base'][~actual_eligible])
            save_json(out/a['folder']/(name+'.json'), artifact)
            save_json(out/a['folder']/(name+'-native.json'), {'rules': model.native_rules})
            save_json(out/a['folder']/(name+'-predictions.json'), p.tolist())
            retained.append({'candidate': name, 'fold': f['fold'], 'original_correct': 99,
                'local_slots_correct': 144, 'rules': len(model.rules), 'training': model.training})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == expected[e['case']]['prediction']
                rows.append({**e, 'fold': f['fold'], 'candidate': name, 'prediction': int(p[i]),
                    'baseline': int(full['base'][i]), 'regular': int(d['regular'][i]), 'changed': bool(p[i] != full['base'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'memberships.json', memberships); save_json(out/'retention.json', retained)
        print({'fold': f['fold'], 'genuine_fit_cases': len(fit), 'selector_configs': len(CONFIGS)}, flush=True)
    results = {}
    for config in CONFIGS:
        name = name_of(*config); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'coverage': sum(r['covered'] for r in rr), 'all_original_cases_and_slots_retained': True}
        assert results[name]['baseline']['correct'] == 227 and results[name]['coverage'] == 273
    save_json(out/'results.json', results)
    assert all(file_hash(path) == sha for path, sha in hashes.items())
    save_json(out/'manifest.json', {'protocol_ref': digest(protocol), 'code_sha256': hashes,
        'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json'), 'scalar_replays': scalar_replays})
    (out/'run.log').write_text('Completed48 cached opinion selectors,43920 scalar/native/merged replays,99/144 retention and273 coverage. V112 remains selected.\n')
    print({name: (r['metrics']['correct'], r['metrics']['balanced_accuracy']) for name, r in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); run(a.output_dir.resolve())
