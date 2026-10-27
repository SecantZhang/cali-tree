"""Re-induce sparse conditional gates and replay their shared semantic terms."""
import argparse
from pathlib import Path
import shutil
import warnings

import numpy as np
from sklearn.metrics import balanced_accuracy_score, accuracy_score, f1_score

from critical.core.calibration.conditional_rubric_v149 import ConditionalRubric, evaluate
from critical.core.calibration.local_warranted_rubric_v97 import DESCRIPTIONS
from critical.core.calibration.semantic_residual_runtime_v104 import SUPPORT
from critical.core.calibration.class_balance_v141 import classification_metrics
from critical.core.decision.artifacts import digest, save_json
from critical.lm_engine.local_qwen_v94 import file_hash
from run.calitree_conditional_rubric_v149 import CONFIGS, name_of, term_pool, design
from run.calitree_compact_balance_v143 import contexts, CACHE, CACHE_AUDIT
from run.verify_calitree_semantic_residual_v105 import load
from run.calitree_semantic_rubric_v70 import ROOT, STUDY, read
from run.calitree_fallback_routing_v34 import old_inputs, PREVIOUS


def audit(study, out):
    if out.exists():
        raise ValueError('Fresh conditional-rubric audit required')
    m, protocol = read(study/'manifest.json'), read(study/'protocol.json')
    assert m['protocol_ref'] == digest(protocol)
    for p, sha in m['code_sha256'].items():
        assert file_hash(p) == file_hash(study/'source_snapshot'/Path(p).relative_to(ROOT)) == sha
    d = load(CACHE, CACHE_AUDIT); desc = {**DESCRIPTIONS, **SUPPORT}
    slots = [r for bank in (1, 2, 3) for r in old_inputs(PREVIOUS, bank)[3]['local']]
    out.mkdir(parents=True); (out/'run.log').write_text('Sparse gate re-induction and exact shared-predicate execution started.\n')
    (out/'llm-histories.log').write_text('Zero neural/API calls. Existing cached semantic views only.\n')
    rows = []; checks = []
    for f in [f for f in read(STUDY/'folds.json') if f['candidate'] == 'boost_full_vision']:
        a, c, fit = contexts(d, f); full, fitting = c['actual'], c['fitting']
        assert not set(d['groups'][fit]) & set(d['groups'][a['held']])
        for family in ('concepts', 'merged'):
            terms = term_pool(d, a, family); actual_X = design(d, a['full'], terms); fitting_X = design(d, a['T'], terms)
            X = np.concatenate([fitting_X[fit], actual_X[:99]]); y = np.r_[d['y'][fit], d['y'][:99]]
            original = np.r_[np.zeros(len(fit), dtype=bool), np.ones(99, dtype=bool)]
            for cap, C in [(cap, C) for cap in (32, 96) for C in (.1, 1., 10.)]:
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', message="'penalty' was deprecated.*", category=FutureWarning)
                    warnings.filterwarnings('ignore', message='Inconsistent values: penalty=l1.*', category=UserWarning)
                    model = ConditionalRubric(C=C, max_terms=cap).fit(X, y, original).select(fitting_X[fit], d['y'][fit],
                        fitting['base'][fit], fitting['locked'][fit], actual_X[:99], d['y'][:99], full['base'][:99], full['locked'][:99])
                name = name_of(family, cap, C); artifact = read(study/a['folder']/(name+'.json'))
                assert model.artifact(terms, desc, artifact['parent_ref']) == artifact
                p = model.predict(actual_X, full['base'], full['locked'])
                assert p.tolist() == read(study/a['folder']/(name+'-predictions.json'))
                for i in range(len(p)):
                    values = {n: float(a['full'][i, j]) for j, n in enumerate(d['names'])}
                    assert evaluate(artifact, values, int(full['base'][i]), bool(full['locked'][i])) == p[i]
                assert np.all(p[:99] == d['y'][:99])
                assert sum(p[d['pos'][r['case']]] == r['reference'] for r in slots) == 144
                checks.append({'candidate': name, 'fold': f['fold'], 'original_correct': 99, 'slots_correct': 144,
                    'shared_terms': len(artifact['terms']), 'portable_rows': len(p)})
                for i in a['held']:
                    rows.append({**d['examples'][i], 'candidate': name, 'fold': f['fold'], 'prediction': int(p[i]), 'baseline': int(full['base'][i])})
        print({'fold': f['fold'], 'reinduced_gate_pairs': len(checks)}, flush=True)
    assert sorted(rows, key=lambda r: (r['candidate'], r['case'])) == sorted(read(study/'predictions.json'), key=lambda r: (r['candidate'], r['case']))
    results = read(study/'results.json')
    for name, result in results.items():
        rr = [r for r in rows if r['candidate'] == name]
        assert len(rr) == len({r['case'] for r in rr}) == 276
        metric = classification_metrics(rr); assert metric == result['metrics']
        y, p = [r['reference'] for r in rr], [r['prediction'] for r in rr]
        assert abs(metric['accuracy']-accuracy_score(y, p)) < 1e-14
        assert abs(metric['balanced_accuracy']-balanced_accuracy_score(y, p)) < 1e-14
        assert abs(metric['macro_f1']-f1_score(y, p, labels=[0, 1, 2], average='macro')) < 1e-14
        assert result['coverage'] == 273
    result = {'passed': True, 'reinduced_gate_pairs': len(checks), 'portable_rows': sum(c['portable_rows'] for c in checks),
        'results': results, 'new_api_or_neural_calls': 0, 'reserved_sources_used': 0, 'selected_default_changed': False}
    save_json(out/'verification.json', result); save_json(out/'checks.json', checks)
    save_json(out/'manifest.json', {'auditor_sha256': file_hash(__file__), 'study_manifest_sha256': file_hash(study/'manifest.json')})
    dest = out/'source_snapshot/run'/Path(__file__).name; dest.parent.mkdir(parents=True); shutil.copyfile(__file__, dest)
    (out/'run.log').write_text('All72 sparse progress/completion pairs re-induced;65,880 shared-term rows and protected decisions match.\n')
    print({'passed': True, 'gate_pairs': len(checks)}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--study', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); audit(a.study.resolve(), a.output_dir.resolve())
