"""Export a credential-free, offline advisor demo from existing development artifacts.

Run from the repository root: .venv/bin/python demos/calitree_meeting/build_demo.py
No calls, fitting, final-test records, or mutations of experiment artifacts.
"""
from pathlib import Path
import base64
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from critical.core.calibration.semantic_hierarchy.portable_features_v8 import project
from critical.core.calibration.semantic_hierarchy.portable_runtime_v8 import PortableRuleExecutor
from critical.core.decision.bound_evidence_v2 import derive_record, diagnostic_readout


def read(relative):
    return json.loads((ROOT / relative).read_text())


def export():
    evidence_path = 'logs/exps/261014-m1-bound-evidence-development12-v2'
    policy_path = 'logs/exps/261014-m2-portable-semantic-v8'
    meaning_path = 'logs/exps/261014-m2-semantic-interpretation-dev12-v5'
    manifest = read(evidence_path + '/manifest.json')
    raw = {r['case']: r for r in read(evidence_path + '/observations.json')}
    meanings = {r['case']: r for r in read(meaning_path + '/interpretations.json')}
    artifact = read(policy_path + '/deployment_policy.json')
    runtime = PortableRuleExecutor(artifact)
    train = read(policy_path + '/data.json')['train']
    training_sources = {r['source_group'] for r in train}
    cases = []
    (OUT / 'media').mkdir(exist_ok=True)
    for c in manifest['cases']:
        assert c['group'] not in training_sources
        r = raw[c['case']]
        program = r['compilation']['program']
        observation = r['observation']['observation']
        record = derive_record(program, observation, r['record']['image_pair_ref'])
        assert record == r['record']
        assert diagnostic_readout(record) == r['diagnostic']
        interpretation = meanings[c['case']]['interpretation']
        features = project(program, observation, record['image_pair_ref'], interpretation)
        prediction = runtime.predict_records([features])[0]
        images = {}
        for role, path in c['evidence'].items():
            source = Path(path)
            # Existing local public benchmark assets only; no downloads.
            assert hashlib.sha256(source.read_bytes()).hexdigest() == c['image_hashes'][role]
            target = OUT / 'media' / f'{c["case"]}-{role}{source.suffix}'
            shutil.copyfile(source, target)
            images[role] = str(target.relative_to(OUT))
        cases.append(dict(case=c['case'], instruction=c['instruction'], reference=c['reference'],
                          human_score=c['human_score'], source_group=c['group'], images=images,
                          image_hashes=c['image_hashes'], program=program, record=record,
                          interpretation=interpretation, features=features, prediction=prediction,
                          diagnostic=r['diagnostic']))
    assert len(cases) == 12 and len({c['source_group'] for c in cases}) == 12
    assert all(sum(c['reference'] == label for c in cases) == 4 for label in ('no', 'partial', 'yes'))
    reviewed = read(policy_path + '/reviewed_result.json')
    replay = runtime.predict_records([r['features'] for r in train])
    assert [p['prediction'] for p in replay] == [p['prediction'] for p in reviewed['cases']]
    historical = read('logs/exps/261014-instruction-semantic-distillation-v16/results.json')
    groups = []
    for name, group in historical['groups'].items():
        arm = group['teacher_distilled']
        groups.append({'name': name, 'metrics': arm['metrics'],
                       'policy': {k: arm['policy'][k] for k in ('yes', 'partial')},
                       'limits': arm['policy']['limits']})
    data = dict(version='advisor-demo-2026-10-15', cases=cases, policy=artifact,
                training_metrics=reviewed['metrics'], candidates=read(policy_path + '/results.json')['candidate_metrics'],
                selected_profile=read(policy_path + '/results.json')['selected_profile'],
                local_groups=groups,
                training_batch_counts={g: sum(r['batch'] == g for r in train) for g in ('G1','G2','G3','G4')},
                provenance=[evidence_path + '/manifest.json', evidence_path + '/observations.json',
                            meaning_path + '/interpretations.json', policy_path + '/deployment_policy.json',
                            policy_path + '/reviewed_result.json', policy_path + '/results.json',
                            'docs/calitree_structure.md', 'docs/calitree_hierarchical_semantic_calibration_roadmap.md',
                            'docs/calitree_m2_portable_semantic_v8.md', 'docs/calitree_local_evidence_calibration.md',
                            'docs/calitree_batch_evidence_calibration.md',
                            'logs/exps/261014-instruction-semantic-distillation-v16/results.json',
                            'logs/exps/261014-frozen-semantic-transfer12-v1/report.md'],
                scope='12 historically exposed development sources; offline v8 replay for this demo. No new model calls, fitting, or reserved-final predictions.')
    data['source_hashes'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in data['provenance']}
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    (OUT / 'data.js').write_text('window.CALITREE_DATA = ' + payload + ';\n')
    # A single portable file works by double-click, even without a server.
    standalone = json.loads(payload)
    for c in standalone['cases']:
        for role, path in c['images'].items():
            mime = 'image/jpeg' if Path(path).suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
            c['images'][role] = 'data:' + mime + ';base64,' + base64.b64encode((OUT / path).read_bytes()).decode()
    html = (OUT / 'index.html').read_text()
    html = html.replace('<link rel="stylesheet" href="style.css">', '<style>' + (OUT / 'style.css').read_text() + '</style>')
    html = html.replace('<script src="data.js"></script>', '<script>window.CALITREE_DATA=' + json.dumps(standalone, ensure_ascii=False).replace('</', '<\\/') + ';</script>')
    html = html.replace('<script src="app.js"></script>', '<script>' + (OUT / 'app.js').read_text() + '</script>')
    (OUT / 'calitree-demo.html').write_text(html)
    correct = sum(c['prediction']['prediction'] == ('no','partial','yes').index(c['reference']) for c in cases)
    print(json.dumps({'cases': len(cases), 'checks': sum(len(c['program']['checks']) for c in cases),
                      'v8_demo_correct': correct, 'training_replay_correct': reviewed['metrics']['correct'],
                      'new_model_calls': 0, 'final_test_records_read': 0,
                      'standalone': str(OUT / 'calitree-demo.html')}))


if __name__ == '__main__':
    export()
