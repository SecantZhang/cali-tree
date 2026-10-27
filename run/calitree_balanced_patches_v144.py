"""Test few semantic corrections, emphasizing recovery of Partial predictions."""
import argparse
from pathlib import Path
import shutil

import numpy as np

from critical.core.calibration.balanced_semantic_patches_v144 import BalancedSemanticPatches, execute
from critical.core.calibration.local_warranted_rubric_v97 import SPECS, DESCRIPTIONS
from critical.core.calibration.rubric_evidence_v73 import SPECS as OLD
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT, VERIFIED
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS

CONFIGS = [(partial, cost, guards) for partial in (True, False) for cost in (1., 2.) for guards in (1, 2)]


def name_of(partial, cost, guards):
    return ('partial_from_no' if partial else 'all_grades')+'_loss'+str(cost)+'_guards'+str(guards)


def run(out):
    if out.exists():
        raise ValueError('Fresh semantic-balanced patch experiment required')
    protocol = {'version': 'balanced-semantic-patches-v144', 'configs': CONFIGS,
        'primary': name_of(True, 2., 1), 'max_rules': 4, 'min_positive_sources': 2, 'beam_width': 16,
        'objective': 'Greedy class-normalized corrections: sum(gains in grade k / (3*n_k)) minus loss_cost times corresponding losses. Class counts include all genuine fitting rows, including unchanged prior routes.',
        'semantic': 'Every concrete grade starts from its affirmative rubric/local warrant. At most one/two additional named guards plus current grade. Partial-only arms change only No to Partial, so existing Partial and Yes decisions cannot be demoted by those arms.',
        'protection': 'Veto every clause matching a correct actual original input where it could execute. Earlier v112 semantic/expert overrides and missing upstream evidence keep priority. Check99/144 original predictions and all276 evaluation cases.',
        'source_control': 'Same outer source folds and genuine source-excluded teacher fitting views. Fixed outer v112 residual reused in fitting contexts, not separately inner-cross-fitted. No held-source labels or siblings select clauses.',
        'features': 'Existing named task/progress/endpoint/identity/collateral concepts, rubric/view cues and local claims. No source/case/editor IDs, object names or raw visual vectors. Local claims remain masked by the actual current/fitting review gate.',
        'new_api_calls': 0, 'new_neural_calls': 0, 'reserved_sources_used': 0, 'serving_changed': False}
    out.mkdir(parents=True); save_json(out/'protocol.json', protocol)
    (out/'run.log').write_text('Few semantic balanced-gain corrections started; fixed eight arms.\n')
    (out/'llm-histories.log').write_text('Zero API/encoder/observer calls. Existing bound semantic evidence only.\n')
    sources = [Path(__file__), ROOT/'critical/core/calibration/balanced_semantic_patches_v144.py', ROOT/'run/calitree_compact_balance_v143.py']
    for p in sources:
        dest = out/'source_snapshot'/p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    d = load(CACHE, CACHE_AUDIT)
    columns = [i for i, n in enumerate(d['names']) if n in SPECS or n in OLD or n.startswith((
        'meaning_progress_', 'meaning_endpoint_gap_', 'meaning_collateral_materiality_', 'meaning_identity_materiality_',
        'meaning_retention_need_', 'meaning_identity_evidence_', 'task_', 'requires_'))]
    names = [d['names'][i] for i in columns]; assert all(n in DESCRIPTIONS for n in names)
    expected = {r['case']: r for r in read(VERIFIED/'predictions.json')}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    rows = []; retention = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']; folder = a['folder']
        save_json(out/folder/'memberships.json', {'fit_cases': [d['examples'][i]['case'] for i in fit],
            'fit_sources': sorted(set(d['groups'][fit])), 'held_cases': f['held_cases'], 'features': names})
        for partial, cost, guards in CONFIGS:
            name = name_of(partial, cost, guards)
            model = BalancedSemanticPatches(names, partial_only=partial, loss_cost=cost, guards=guards).fit(
                a['T'][fit][:, columns], d['y'][fit], fitting['base'][fit], ~fitting['locked'][fit], d['groups'][fit],
                protected_X=a['full'][:99, columns], protected_y=d['y'][:99],
                protected_base=full['base'][:99], protected_eligible=~full['locked'][:99])
            p = model.predict(a['full'][:, columns], full['base'], ~full['locked'])
            artifact = model.artifact()
            for i in range(len(d['examples'])):
                values = {n: bool(a['full'][i, j]) for n, j in zip(names, columns)}
                assert execute(artifact, values, int(full['base'][i]), bool(~full['locked'][i])) == p[i]
            assert np.all(p[:99] == d['y'][:99])
            count = int(sum(p[d['pos'][r['case']]] == r['reference'] for r in slots)); assert count == 144
            assert np.array_equal(p[full['locked']], full['base'][full['locked']])
            if partial:
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
    for partial, cost, guards in CONFIGS:
        name = name_of(partial, cost, guards); rr = [r for r in rows if r['candidate'] == name]
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
        'features': names, 'targets_ref': digest(d['y'].tolist())})
    (out/'run.log').write_text('Completed48 small semantic patch fits and43,920 portable replays; no default change.\n')
    print({k: (v['metrics']['correct'], v['metrics']['balanced_accuracy']) for k, v in results.items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    run(p.parse_args().output_dir.resolve())
