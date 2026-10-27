"""Reconstruct two meaningful grade gates from shared named predicates."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.conditional_rubric_v149 import ConditionalRubric, evaluate
from critical.core.calibration.semantic_polynomial_v111 import compile_polynomial
from critical.core.calibration.semantic_residual_runtime_v104 import f32, SUPPORT
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS, SPECS
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, SOURCE, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

CONFIGS = [(family, cap, C) for family in ('concepts', 'merged') for cap in (32, 96) for C in (.1, 1., 10.)]


def name_of(family, cap, C):
    return family+'_terms'+str(cap)+'_C'+str(C)


def term_pool(d, a, family):
    names = [n for n in d['names'] if n in DESCRIPTIONS and (n in SPECS or n.startswith((
        'meaning_', 'task_', 'requires_', 'intent_', 'rationale_', 'rubric_', 'view_')))]
    terms = {( (n, .5, True), ) for n in names}
    if family == 'merged':
        metadata = read(SOURCE/a['folder']/'contextual_depth2.json')
        parent = compile_polynomial(read(SOURCE/a['folder']/'contextual_depth2-native.json'), metadata)
        terms.update(tuple(sorted((c['feature'], f32(c['border']), c['greater']) for c in row['conditions']))
                     for row in parent['clauses'] if row['conditions'])
    return [[{'feature': n, 'border': b, 'greater': g} for n, b, g in row] for row in sorted(terms)]


def design(d, matrix, terms):
    positions = {n: i for i, n in enumerate(d['names'])}
    result = []
    for term in terms:
        mask = np.ones(len(matrix), dtype=bool)
        for condition in term:
            column = matrix[:, positions[condition['feature']]].astype(np.float32)
            mask &= (column > np.float32(condition['border'])) == condition['greater']
        result.append(mask)
    return np.asarray(result, dtype=bool).T


def run(out):
    if out.exists():
        raise ValueError('Fresh conditional-rubric reconstruction run required')
    protocol = {'version': 'conditional-rubric-reconstruction-v149', 'configs': CONFIGS,
        'primary': name_of('merged', 32, 1.),
        'meaning': 'Predict meaningful human-recognized fulfillment first; then full fulfillment CONDITIONAL on at least partial fulfillment. No examples enter the completion fit. Partial mass is progress times one minus conditional completion.',
        'reconstruction': 'Sparse named-concept logistic gates; merged family shares exact Boolean/numeric conjunctions from the previously fitted shallow semantic model. One shared predicate carries two gate weights. No raw embeddings or case/source/editor IDs.',
        'training': 'Genuine source-excluded teacher fitting views plus the protected99 as explicit actual-view anchors. Class-normalized weights with anchor multiplier5. Each gate ranks fitting concepts, then fits sparse L1 logistic coefficients.',
        'readout': 'Progress/completion cutoffs and minimum joint class mass selected only on genuine fitting rows, with hard actual-original99 veto. Prior v112 overrides and missing-evidence routes keep priority; low-mass regions retain v112.',
        'evaluation': 'Same five outer source folds and276 reviewed cases; full-fit fold5 is not headline evaluation. All held-source siblings excluded. Parent model uses outer-training data, not separate inner cross-fitting.',
        'new_api_or_neural_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Shared semantic progress/conditional-completion reconstruction started.\n')
    (out/'llm-histories.log').write_text('Zero API/encoder/observer calls; existing named bound evidence only.\n')
    files = [Path(__file__), ROOT/'critical/core/calibration/conditional_rubric_v149.py', ROOT/'run/calitree_compact_balance_v143.py']
    hashes = {str(p): file_hash(p) for p in files}
    for p in files:
        target = out/'source_snapshot'/p.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, target)
    d = load(CACHE, CACHE_AUDIT); desc = {**DESCRIPTIONS, **SUPPORT}
    expected = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']; folder = a['folder']
        assert not set(d['groups'][fit]) & set(d['groups'][a['held']])
        for family in ('concepts', 'merged'):
            terms = term_pool(d, a, family); actual_X = design(d, a['full'], terms); fitting_X = design(d, a['T'], terms)
            train_X = np.concatenate([fitting_X[fit], actual_X[:99]])
            train_y = np.r_[d['y'][fit], d['y'][:99]]
            original = np.r_[np.zeros(len(fit), dtype=bool), np.ones(99, dtype=bool)]
            for cap, C in [(cap, C) for cap in (32, 96) for C in (.1, 1., 10.)]:
                model = ConditionalRubric(C=C, max_terms=cap).fit(train_X, train_y, original).select(
                    fitting_X[fit], d['y'][fit], fitting['base'][fit], fitting['locked'][fit],
                    actual_X[:99], d['y'][:99], full['base'][:99], full['locked'][:99])
                p = model.predict(actual_X, full['base'], full['locked'])
                artifact = model.artifact(terms, desc, read(ROOT/'examples/calitree_weighted_semantic_v112/policy.json')['artifact_ref'])
                for i in range(len(p)):
                    values = {n: float(a['full'][i, j]) for j, n in enumerate(d['names'])}
                    assert evaluate(artifact, values, int(full['base'][i]), bool(full['locked'][i])) == p[i]
                name = name_of(family, cap, C)
                assert np.all(p[:99] == d['y'][:99])
                assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
                assert np.array_equal(p[full['locked']], full['base'][full['locked']])
                save_json(out/folder/(name+'.json'), artifact); save_json(out/folder/(name+'-predictions.json'), p.tolist())
                save_json(out/folder/(name+'-selection.json'), {'trials': model.trials, 'selected': model.selected,
                    'fit_cases': [d['examples'][i]['case'] for i in fit], 'anchor_cases': [e['case'] for e in d['examples'][:99]]})
                retention.append({'candidate': name, 'fold': f['fold'], 'terms': len(artifact['terms']),
                    'features': len(artifact['features']), 'original_correct': 99, 'slots_correct': 144})
                for i in a['held']:
                    e = d['examples'][i]; assert full['base'][i] == expected[e['case']]['prediction']
                    rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(full['base'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention)
        print({'fold': f['fold'], 'configs': len(CONFIGS)}, flush=True)
    results = {}
    for family, cap, C in CONFIGS:
        name = name_of(family, cap, C); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'coverage': sum(r['covered'] for r in rr), 'all_original_cases_and_slots_retained': True}
        assert results[name]['coverage'] == 273
    save_json(out/'results.json', results)
    assert all(file_hash(p) == sha for p, sha in hashes.items())
    save_json(out/'manifest.json', {'code_sha256': hashes, 'protocol_ref': digest(protocol),
        'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json')})
    (out/'run.log').write_text('Completed72 two-gate reconstructions and65,880 exact shared-term replays. Selected v112 unchanged.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy']) for k, v in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
