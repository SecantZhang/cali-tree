"""Independent, API-free audit of the frozen semantic transfer benchmark."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def read(p):
    return json.loads(p.read_text())


def hash_file(p):
    return sha256(p.read_bytes()).hexdigest()


def execute(policy, record):
    if record is None:
        return -1, {'missing_evidence': True}
    traces = {}
    bounds = {}
    for boundary in ('yes', 'partial'):
        traces[boundary] = []
        for clause in policy[boundary]:
            atoms = [{'fact': a['fact'], 'expected': a['test'], 'observed': record['facts'][a['fact']]}
                     for a in clause]
            definite = all(a['observed'] == a['expected'] for a in atoms)
            possible = all(a['observed'] in (a['expected'], 'unknown') for a in atoms)
            traces[boundary].append({'atoms': atoms, 'definite': definite, 'possible': possible})
        bounds[boundary] = (any(c['definite'] for c in traces[boundary]),
                            any(c['possible'] for c in traces[boundary]))
    low = 2 if bounds['yes'][0] else 1 if bounds['partial'][0] else 0
    high = 2 if bounds['yes'][1] else 1 if bounds['partial'][1] else 0
    return low if low == high else -1, {'clauses': traces, 'lower_label': low, 'upper_label': high}


def audit(output):
    from PIL import Image
    m, r = read(output / 'manifest.json'), read(output / 'results.json')
    obs, saved = read(output / 'observations.json'), read(output / 'predictions.json')
    labels = ('no', 'partial', 'yes')
    assert len(obs) == len(m['cases']) == 12
    assert Counter(c['reference'] for c in m['cases']) == dict.fromkeys(labels, 4)
    groups = []
    for c in m['cases']:
        for role, path in c['evidence'].items():
            assert hash_file(Path(path)) == c['image_hashes'][role]
        with Image.open(c['evidence']['source_image']) as im:
            rgb = im.convert('RGB')
            group = sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        assert group == c['group'] and group not in m['excluded_groups']
        groups.append(group)
    assert len(set(groups)) == 12
    traces, counts = {}, {}
    for g in ('G1', 'G2', 'G3', 'G4'):
        path = output / 'policies' / g / 'policy.json'
        assert hash_file(path) == hash_file(Path(m['policies'][g]['source'])) == m['policies'][g]['sha256']
        policy = read(path); decisions = []
        traces[g] = []
        for c, o, s in zip(m['cases'], obs, saved[g]):
            assert c['case'] == o['case']
            p, t = execute(policy, o['record']); decisions.append(p)
            assert p == s['prediction']
            traces[g].append({'case': c['case'], 'instruction': c['instruction'],
                              'reference': c['reference'], 'prediction': labels[p] if p >= 0 else 'unresolved', **t})
        targets = [labels.index(c['reference']) for c in m['cases']]
        correct = sum(p == y for p, y in zip(decisions, targets))
        metric = r['policies'][g]['metrics']; cls = r['policies'][g]['class_metrics']
        assert metric['correct'] == cls['correct'] == correct
        assert metric['accuracy'] == cls['accuracy'] == correct / 12
        assert metric['resolved'] == 12 - decisions.count(-1)
        assert cls['unresolved'] == decisions.count(-1)
        f1 = []
        for j, label in enumerate(labels):
            tp = sum(p == y == j for p, y in zip(decisions, targets))
            f1.append(2 * tp / (4 + decisions.count(j)))
            assert metric['per_class_recall'][label] == cls['per_class'][label]['recall'] == tp / 4
            confusion = Counter(labels[p] if p >= 0 else 'unresolved' for p, y in zip(decisions, targets) if y == j)
            assert dict(confusion) == metric['confusion'][label]
        assert abs(cls['macro_f1'] - sum(f1) / 3) < 1e-12
        counts[g] = {'correct': correct, 'total': 12, 'unresolved': decisions.count(-1)}
    summary = {'passed': True, 'independent_predictions_checked': 48, 'policies_unchanged': 4,
               'image_hashes_verified': 24, 'distinct_source_pixel_hashes': 12,
               'excluded_source_overlap': 0, 'metrics': counts, 'new_model_calls': 0}
    for name, value in [('execution_traces.json', traces), ('independent_audit.json', summary)]:
        text = json.dumps(value, indent=2)
        target = output / name
        if target.exists():
            assert read(target) == value
        else:
            target.write_text(text)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    audit(parser.parse_args().output_dir.resolve())
