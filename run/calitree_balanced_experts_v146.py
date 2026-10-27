"""Fit few semantic mixed-judge rules for final class-balanced accuracy."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.balanced_semantic_experts_v146 import (
    BalancedSemanticExperts, EXPERT_SPECS, DESCRIPTIONS, expert_flags, execute, REVIEW_REASONS)
from critical.core.calibration.local_warranted_rubric_v97 import SPECS
from critical.core.calibration.rubric_evidence_v73 import SPECS as OLD
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

CONFIGS = [(style, cost, guards) for style in ('partial_review', 'regular_review', 'mixed')
           for cost in (1., 2.) for guards in (1, 2)]


def name_of(style, cost, guards):
    return style+'_loss'+str(cost)+'_guards'+str(guards)


def matrices(d, a, c):
    columns = [i for i, n in enumerate(d['names']) if n in SPECS or n in OLD or n.startswith((
        'meaning_progress_', 'meaning_endpoint_gap_', 'meaning_collateral_materiality_', 'meaning_identity_materiality_',
        'meaning_retention_need_', 'meaning_identity_evidence_', 'task_', 'requires_', 'intent_', 'rationale_'))]
    names = [d['names'][i] for i in columns]+list(EXPERT_SPECS)
    assert all(n in DESCRIPTIONS for n in names)
    result = {}
    for key, source in (('actual', a['full']), ('fitting', a['T'])):
        old = source[:, columns].astype(bool)
        extra = [expert_flags(dict(zip(names, map(bool, old[i]))), int(c[key]['base'][i]), int(d['regular'][i]))
                 for i in range(len(old))]
        result[key] = np.concatenate([old, np.asarray([[e[n] for n in EXPERT_SPECS] for e in extra], dtype=bool)], axis=1)
    return names, result


def run(out):
    if out.exists():
        raise ValueError('Fresh balanced semantic-expert study required')
    protocol = {'version': 'balanced-semantic-experts-v146', 'configs': CONFIGS,
        'primary': name_of('mixed', 2., 1), 'review_reasons': REVIEW_REASONS,
        'expert_routing': 'A review seed requires an available independent regular judgment, disagreement with the current grade and a named semantic/view/rationale review cue. Selecting that opinion does not assert a new physical grade. Direct grades still require their affirmative warrant.',
        'capacity': 'At most four ordered rules; every rule has one seed plus up to one/two guards and a current-grade region. At least two distinct positive fitting pixel sources. Partial-review arms change only current No to the existing regular Partial opinion.',
        'objective': 'Class-normalized accuracy gains minus cost-weighted class-normalized losses, using all genuine-source fitting rows as denominators. Same protected original99/144 veto.',
        'fitting': 'Same outer source folds and genuine excluded-source teacher views. Earlier v112 overrides keep priority. The fixed outer-fit semantic residual is reused in fitting contexts, not independently inner-cross-fitted.',
        'features': 'Closed task/intent/regular-rationale language cues, bound physical semantic claims and local facts masked by the original review gate. No IDs, object lookup rules, raw visual vectors or human references at inference.',
        'scope': 'Exploratory development comparison following the v143/v144 diagnostics. The earlier primary arms did not improve. All twelve expert arms fixed before this run.',
        'new_api_calls': 0, 'new_neural_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Class-balanced semantic independent-judge routing started.\n')
    (out/'llm-histories.log').write_text('No new API/encoder/observer calls; the independent judge is the existing cached regular judgment.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/balanced_semantic_experts_v146.py', ROOT/'run/calitree_compact_balance_v143.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    d = load(CACHE, CACHE_AUDIT)
    expected = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']; folder = a['folder']
        names, X = matrices(d, a, c)
        save_json(out/folder/'memberships.json', {'fit_cases': [d['examples'][i]['case'] for i in fit],
            'fit_sources': sorted(set(d['groups'][fit])), 'held_cases': f['held_cases'], 'features': names})
        for style, cost, guards in CONFIGS:
            name = name_of(style, cost, guards)
            model = BalancedSemanticExperts(names, style=style, loss_cost=cost, guards=guards).fit(
                X['fitting'][fit], d['y'][fit], fitting['base'][fit], ~fitting['locked'][fit], d['groups'][fit],
                protected_X=X['actual'][:99], protected_y=d['y'][:99],
                protected_base=full['base'][:99], protected_eligible=~full['locked'][:99])
            p = model.predict(X['actual'], full['base'], ~full['locked']); artifact = model.artifact()
            for i in range(len(d['examples'])):
                values = dict(zip(names, map(bool, X['actual'][i])))
                assert execute(artifact, values, int(full['base'][i]), bool(~full['locked'][i]), int(d['regular'][i])) == p[i]
            assert np.all(p[:99] == d['y'][:99])
            count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots)); assert count == 144
            assert np.array_equal(p[full['locked']], full['base'][full['locked']])
            if style == 'partial_review':
                assert np.array_equal(p[full['base'] != 0], full['base'][full['base'] != 0])
            save_json(out/folder/(name+'.json'), artifact); (out/folder/(name+'.txt')).write_text(artifact['rubric'])
            save_json(out/folder/(name+'-predictions.json'), p.tolist())
            retention.append({'candidate': name, 'fold': f['fold'], 'original_correct': 99,
                              'slots_correct': count, 'rules': len(model.rules), 'portable_rows': len(p)})
            for i in a['held']:
                e = d['examples'][i]; assert full['base'][i] == expected[e['case']]['prediction']
                rows.append({**e, 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]),
                             'baseline': int(full['base'][i]), 'changed': bool(p[i] != full['base'][i])})
        save_json(out/'predictions.json', rows); save_json(out/'retention.json', retention)
        print({'fold': f['fold'], 'features': len(names), 'fit_rows': len(fit), 'arms': len(CONFIGS)}, flush=True)
    results = {}
    for style, cost, guards in CONFIGS:
        name = name_of(style, cost, guards); rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == 276 and len({r['case'] for r in rr}) == 276
        results[name] = {'metrics': classification_metrics(rr), 'baseline': classification_metrics(rr, 'baseline'),
            'gains': sum(r['prediction'] == r['reference'] != r['baseline'] for r in rr),
            'losses': sum(r['baseline'] == r['reference'] != r['prediction'] for r in rr),
            'changes': sum(r['changed'] for r in rr), 'coverage': sum(r['covered'] for r in rr),
            'all_original_cases_and_slots_retained': True}
        assert results[name]['coverage'] == 273 and results[name]['baseline']['correct'] == 227
    save_json(out/'results.json', results)
    save_json(out/'manifest.json', {'code_sha256': {str(p): file_hash(p) for p in sources},
        'protocol_ref': digest(protocol), 'cache_audit_manifest_sha256': file_hash(CACHE_AUDIT/'manifest.json'),
        'targets_ref': digest(d['y'].tolist())})
    (out/'run.log').write_text('Completed72 small semantic expert fits and65,880 portable replays. Selected default unchanged.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy']) for k, v in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
