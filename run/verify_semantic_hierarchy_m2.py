"""M2 scaling and exact-reference certificate; no model calls or image claims."""
import argparse
from fractions import Fraction
from pathlib import Path
import time
import tracemalloc

from critical.core.calibration.semantic_hierarchy.rule_search_v3 import SemanticRuleCalibrator
from critical.core.calibration.semantic_hierarchy.rule_search_v2 import SemanticRuleCalibrator as PriorCalibrator
from critical.core.decision.artifacts import save_json
from run.calitree_single_call import read
from tests.unit.calitree.test_semantic_hierarchy_m2_v3 import samples, complementary_partial_samples


def reference_optimum(model, X, y):
    """Independent scalar bit-mask scoring of every retained region pair."""
    space = model.search_space; n = len(X); available = sum(1 << i for i, x in enumerate(X) if x is not None)
    targets = [sum(1 << i for i, v in enumerate(y) if v == k) for k in range(3)]
    support = [y.count(k) for k in range(3)]; atom_masks = []
    for atom in space['atoms']:
        low = high = 0
        for i, x in enumerate(X):
            if x is not None:
                v = x['features'][atom['feature']]
                low |= int(v == atom['test']) << i
                high |= int(v in (atom['test'], 'unknown')) << i
        atom_masks.append((low, high))
    term_masks = []
    for term in space['terms']:
        low = high = available
        for k in term:
            low &= atom_masks[k][0]; high &= atom_masks[k][1]
        term_masks.append((low, high))
    def build(regions):
        result = []
        for region in regions:
            low = high = 0
            for k in region:
                low |= term_masks[k][0]; high |= term_masks[k][1]
            result.append((low, high, sum(len(space['terms'][k]) for k in region), len(region)))
        return result
    yes, partial = build(space['yes_regions']), build(space['partial_regions'])
    best = winner = None; cache = {}; checked = 0
    for i, a in enumerate(yes):
        for j, b in enumerate(partial):
            checked += 1
            masks = (available & ~(a[1] | b[1]), available & b[0] & ~a[1], a[0])
            tp = tuple((masks[k] & targets[k]).bit_count() for k in range(3))
            if min(tp) < model.limits['min_correct_per_class']:
                continue
            count = tuple(m.bit_count() for m in masks); key = (tp, count)
            if key not in cache:
                macro = sum((Fraction(2 * tp[k], support[k] + count[k]) for k in range(3)), Fraction()) / 3
                worst = min(Fraction(tp[k], support[k]) for k in range(3))
                cache[key] = macro, worst, sum(tp)
            rank = (*cache[key], -(a[2] + b[2]), -(a[3] + b[3]))
            if best is None or rank > best:
                best, winner = rank, (i, j)
    def clauses(regions, index):
        return [[space['atoms'][a] for a in space['terms'][t]] for t in regions[index]]
    assert clauses(space['yes_regions'], winner[0]) == model.metadata()['yes']
    assert clauses(space['partial_regions'], winner[1]) == model.metadata()['partial']
    return {'pairs_scored': checked, 'winner_matches': True,
            'exact_macro_f1': str(best[0]), 'exact_worst_recall': str(best[1]), 'correct': best[2]}


def main(output, actual_data=None):
    output.mkdir(parents=True, exist_ok=True); benchmark = []
    for n in (12, 24, 48, 96):
        X, y, groups, batches = samples(n)
        tracemalloc.start(); start = time.monotonic()
        model = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
        elapsed = time.monotonic() - start; _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        restored = SemanticRuleCalibrator.restore(model.metadata())
        assert restored.predict_records(X) == model.predict_records(X)
        assert [r['prediction'] for r in model.predict_records(X)] == y
        certificate = reference_optimum(model, X, y)
        benchmark.append({'rows': n, 'packed_words': model.search_diagnostic['packed_words_per_mask'],
                          'elapsed_seconds': elapsed, 'peak_traced_bytes': peak, 'certificate': certificate})
        print({'rows': n, 'seconds': round(elapsed, 3), 'peak_mib': round(peak / 2**20, 2)}, flush=True)
    X, y, groups, batches = complementary_partial_samples()
    old = PriorCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    fixed = SemanticRuleCalibrator().fit(X, y, source_groups=groups, source_batches=batches)
    assert old.metadata()['training']['metrics']['correct'] == 80
    assert fixed.metadata()['training']['metrics']['correct'] == 96
    regression = {'synthetic_rows': 96, 'prior_correct': 80, 'corrected_correct': 96,
                  'known_rule_atoms': 3, 'selected_atoms': fixed.metadata()['capacity']['atoms']}
    actual = None
    if actual_data is not None:
        rows = read(actual_data)['train']
        model = SemanticRuleCalibrator().fit([r['features'] for r in rows], [r['reference'] for r in rows],
                    source_groups=[r['source_group'] for r in rows], source_batches=[r['batch'] for r in rows])
        actual = reference_optimum(model, [r['features'] for r in rows], [r['reference'] for r in rows])
    result = {'passed': True, 'scaling': benchmark, 'complementary_partial_regression': regression,
              'actual_full_training_reference_certificate': actual, 'new_model_calls': 0,
              'scope': 'Synthetic figures establish computational behavior, not image accuracy. Exact scoring is certified within the bounded candidate space, not all possible rules.'}
    save_json(output / 'm2_verification.json', result)
    print(result)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--actual-data', type=Path)
    args = p.parse_args(); main(args.output_dir.resolve(), args.actual_data)
