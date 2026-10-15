"""Bounded semantic DNF learning with packed, sample-linear coverage storage."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import combinations
import math
import time

import numpy as np

from ..base import Calibrator
from ..evidence_rules_v4 import classification_metrics
from ...decision.artifacts import digest
from .features_v2 import CONTRACT_REF, FEATURES, SPECS, validate_record

VERSION = 'scalable-semantic-dnf-v3-conditional-partial'
LIMITS = {'atoms_per_clause': 3, 'clauses_per_boundary': 3, 'terms_per_boundary': 128,
          'regions_per_boundary': 2048, 'min_clause_sources': 2, 'min_correct_per_class': 2,
          'min_clause_batches': 1, 'retained_candidates': 2}
MASK64 = (1 << 64) - 1


class UnsupportedPolicyError(ValueError):
    pass


def atom_bounds(record, atom):
    state = record['features'][atom['feature']]
    if state == 'unknown':
        return False, True
    value = state == atom['test']
    return value, value


def boundary_bounds(record, clauses):
    bounds = [[atom_bounds(record, a) for a in clause] for clause in clauses]
    return (any(all(a for a, _ in term) for term in bounds),
            any(all(b for _, b in term) for term in bounds))


def predict_program(record, yes, partial):
    if record is None:
        return -1
    y, p = boundary_bounds(record, yes), boundary_bounds(record, partial)
    low = 2 if y[0] else 1 if p[0] else 0
    high = 2 if y[1] else 1 if p[1] else 0
    return low if low == high else -1


def pack_masks(values, n):
    words = max(1, (n + 63) // 64)
    return np.asarray([[(int(v) >> (64 * j)) & MASK64 for j in range(words)] for v in values], dtype=np.uint64)


def popcount(values):
    if hasattr(np, 'bitwise_count'):
        return np.bitwise_count(values).sum(axis=-1, dtype=np.int64)
    table = np.asarray([i.bit_count() for i in range(256)], dtype=np.uint8)
    raw = np.ascontiguousarray(values).view(np.uint8)
    return table[raw].sum(axis=-1, dtype=np.int64)


def exact_rank(tp, predicted, supports, cost, clauses):
    macro = sum((Fraction(2 * int(t), int(n + p)) for t, n, p in zip(tp, supports, predicted)), Fraction()) / 3
    worst = min(Fraction(int(t), int(n)) for t, n in zip(tp, supports))
    return macro, worst, sum(int(t) for t in tp), -int(cost), -int(clauses)


def validate_limits(limits):
    if set(limits) != set(LIMITS) or any(type(v) is not int or v < 1 for v in limits.values()):
        raise ValueError('Invalid bounded-search limits')
    if limits['atoms_per_clause'] > 3 or limits['clauses_per_boundary'] > 3 or limits['retained_candidates'] > 2:
        raise ValueError('This version supports at most three atoms/clauses and two alternatives')


class SemanticRuleCalibrator(Calibrator):
    version = VERSION

    def __init__(self, *, limits=None):
        self.limits = dict(LIMITS if limits is None else limits); validate_limits(self.limits)
        self._artifact = None; self._candidates = []; self.search_space = None

    def fit(self, X, y, *, sample_weight=None, source_groups=None, source_batches=None):
        start = time.monotonic(); X, y = list(X), list(y); n = len(y)
        groups = list(source_groups or []); batches = list(source_batches or [])
        floor = self.limits['min_correct_per_class']
        if (sample_weight is not None or n < 3 * floor or len(X) != n or len(groups) != n or len(set(groups)) != n
                or len(batches) != n or any(not isinstance(v, str) or not v for v in groups + batches)
                or any(type(v) is not int or v not in (0, 1, 2) for v in y) or any(y.count(k) < floor for k in range(3))):
            raise ValueError('Distinct sources, explicit originating batches, and all three supported labels required')
        for r in X:
            validate_record(r)
        # Canonical source ordering affects only reproducibility and support
        # accounting. No source/batch identifier becomes a prediction feature.
        order = sorted(range(n), key=lambda i: groups[i])
        X, y, groups, batches = ([v[i] for i in order] for v in (X, y, groups, batches))
        available = sum(1 << i for i, r in enumerate(X) if r is not None)
        supports = [y.count(k) for k in range(3)]
        targets = [sum(1 << i for i, label in enumerate(y) if label == k) for k in range(3)]
        batch_masks = {b: sum(1 << i for i, v in enumerate(batches) if v == b) for b in sorted(set(batches))}
        atoms = []
        for feature in FEATURES:
            tests = ('true', 'false') if SPECS[feature]['role'] == 'context' else ('true',)
            for test in tests:
                atom = {'feature': feature, 'test': test}; lo = hi = 0
                for i, r in enumerate(X):
                    if r is not None:
                        a, b = atom_bounds(r, atom); lo |= int(a) << i; hi |= int(b) << i
                if lo.bit_count() >= self.limits['min_clause_sources']:
                    atoms.append((atom, lo, hi))
        unique = {}
        for arity in range(1, self.limits['atoms_per_clause'] + 1):
            for indices in combinations(range(len(atoms)), arity):
                if len({atoms[i][0]['feature'] for i in indices}) != arity:
                    continue
                lo = hi = available
                for i in indices:
                    lo &= atoms[i][1]; hi &= atoms[i][2]
                if lo.bit_count() < self.limits['min_clause_sources'] or sum(bool(lo & mask) for mask in batch_masks.values()) < self.limits['min_clause_batches']:
                    continue
                role = max((2 if SPECS[atoms[i][0]['feature']]['role'] == 'core' and atoms[i][0]['test'] == 'true'
                            else 1 if SPECS[atoms[i][0]['feature']]['role'] == 'support' and atoms[i][0]['test'] == 'true' else 0) for i in indices)
                # Do not replace a requested witness with an incidental feature
                # merely because they cover the same finite fitting examples.
                key = (lo, hi, role); rank = (arity, indices)
                if key not in unique or rank < unique[key][1]:
                    unique[key] = (indices, rank)
        terms = [(lo, hi, role, value[0]) for (lo, hi, role), value in unique.items()]
        terms.sort(key=lambda t: (len(t[3]), t[3]))

        def regions(positive, min_role, neutral=0):
            def rank(lo, hi, clauses):
                tp = (lo & positive).bit_count(); fp = (hi & available & ~(positive | neutral)).bit_count()
                return (2 * tp / (positive.bit_count() + (hi & ~neutral).bit_count()), tp, -fp,
                        -sum(len(terms[j][3]) for j in clauses), -len(clauses), tuple(-j for j in clauses))
            eligible = [j for j, (lo, hi, role, _) in enumerate(terms) if role >= min_role and lo & positive]
            ranked = sorted(eligible, key=lambda j: rank(terms[j][0], terms[j][1], (j,)), reverse=True)
            # Preserve the primitive witness basis. Ranking a clause in isolation
            # can otherwise delete a necessary complementary Partial subtype.
            primitive = [j for j in ranked if len(terms[j][3]) == 1]
            cap = self.limits['terms_per_boundary']
            if len(primitive) > cap:
                raise ValueError('Term budget cannot preserve the primitive witness basis')
            eligible = primitive + [j for j in ranked if j not in set(primitive)][:cap - len(primitive)]
            pool = {(0, 0): ()}
            for _ in range(self.limits['clauses_per_boundary']):
                updated = dict(pool)
                for (a, b), old in list(pool.items()):
                    for j in eligible:
                        if j in old or len(old) >= self.limits['clauses_per_boundary']:
                            continue
                        lo, hi, _, _ = terms[j]; key = (a | lo, b | hi); clauses = tuple(sorted((*old, j)))
                        prior = updated.get(key)
                        cost = lambda c: (sum(len(terms[k][3]) for k in c), len(c), c)
                        if prior is None or cost(clauses) < cost(prior):
                            updated[key] = clauses
                if len(updated) > self.limits['regions_per_boundary']:
                    updated = dict(sorted(updated.items(), key=lambda item: rank(*item[0], item[1]), reverse=True)[:self.limits['regions_per_boundary']])
                if updated == pool:
                    break
                pool = updated
            result = [(lo, hi, clauses) for (lo, hi), clauses in pool.items() if clauses and (lo & positive).bit_count() >= floor]
            result.sort(key=lambda t: (sum(len(terms[j][3]) for j in t[2]), len(t[2]), t[2]))
            return result

        yes = regions(targets[2], 2)
        # Partial is evaluated after Yes. Rewarding coverage of Yes during its
        # proposal stage preferentially keeps complete-outcome clauses and can
        # discard genuine incomplete-progress clauses. The final paired scorer
        # still charges every Yes incorrectly left as Partial.
        partial = regions(targets[1], 1, neutral=targets[2])
        trace = {'rows': n, 'available_rows': available.bit_count(), 'packed_words_per_mask': max(1, (n + 63) // 64),
                 'coverage_storage': 'packed_uint64_and_python_integer_bitsets; no 2**n lookup',
                 'atoms': len(atoms), 'supported_terms': len(terms), 'yes_regions': len(yes), 'partial_regions': len(partial),
                 'pairs_considered': len(yes) * len(partial), 'class_supported_pairs': 0, 'exact_score_count': 0,
                 'max_pair_block_rows': 64, 'search_claim': 'Best exact-ranked candidates within a bounded region search; not global optimality over all rules.'}
        trace.update(partial_proposal_target='Partial positive; Yes neutral; final paired scoring evaluates all labels',
                     primitive_witness_basis_preserved=True)
        self.search_space = {'atoms': [a[0] for a in atoms], 'terms': [list(t[3]) for t in terms],
                             'yes_regions': [list(r[2]) for r in yes], 'partial_regions': [list(r[2]) for r in partial]}
        self.search_diagnostic = trace
        if not yes or not partial:
            raise UnsupportedPolicyError('No class-supported positive regions; no collapsed fallback')
        ylo, yhi = pack_masks([r[0] for r in yes], n), pack_masks([r[1] for r in yes], n)
        plo, phi = pack_masks([r[0] for r in partial], n), pack_masks([r[1] for r in partial], n)
        observed = pack_masks([available], n)[0]; target_words = pack_masks(targets, n)
        costs = lambda rs: np.asarray([sum(len(terms[j][3]) for j in r[2]) for r in rs], dtype=np.int64)
        ycost, pcost = costs(yes), costs(partial)
        yn = np.asarray([len(r[2]) for r in yes]); pn = np.asarray([len(r[2]) for r in partial])
        score_cache = {}; best = {}
        K = self.limits['retained_candidates']
        for start_index in range(0, len(yes), 64):
            a = ylo[start_index:start_index + 64, None, :]; b = yhi[start_index:start_index + 64, None, :]
            shape = (len(a), len(partial), len(observed))
            masks = [~(b | phi[None, :, :]) & observed,
                     (plo[None, :, :] & ~b) & observed,
                     np.broadcast_to(a & observed, shape)]
            tp = np.stack([popcount(mask & target_words[k]) for k, mask in enumerate(masks)], axis=-1)
            predicted = np.stack([popcount(mask) for mask in masks], axis=-1)
            valid = np.all(tp >= floor, axis=-1)
            trace['class_supported_pairs'] += int(valid.sum())
            if not valid.any():
                continue
            macro = np.mean(2 * tp / (np.asarray(supports) + predicted), axis=-1)
            worst = np.min(tp / np.asarray(supports), axis=-1); correct = tp.sum(axis=-1)
            cost = ycost[start_index:start_index + len(a), None] + pcost[None, :]
            clause_count = yn[start_index:start_index + len(a), None] + pn[None, :]
            ii, jj = np.nonzero(valid)
            ranking = np.lexsort((jj, ii, clause_count[ii, jj], cost[ii, jj], -correct[ii, jj], -worst[ii, jj], -macro[ii, jj]))
            ii, jj = ii[ranking], jj[ranking]
            signature = np.ascontiguousarray(np.concatenate([mask[ii, jj, :] for mask in masks], axis=-1))
            packed_signature = signature.view(np.dtype((np.void, signature.dtype.itemsize * signature.shape[1]))).reshape(-1)
            _, unique_positions = np.unique(packed_signature, return_index=True)
            unique_positions.sort(); ii, jj = ii[unique_positions], jj[unique_positions]
            cutoff = macro[ii[min(K - 1, len(ii) - 1)], jj[min(K - 1, len(jj) - 1)]] - 1e-12
            for i, j in zip(ii, jj):
                if macro[i, j] < cutoff:
                    break
                counts = tuple(int(v) for v in (*tp[i, j], *predicted[i, j]))
                if counts not in score_cache:
                    score_cache[counts] = exact_rank(counts[:3], counts[3:], supports, 0, 0)[:3]
                rank = (*score_cache[counts], -int(cost[i, j]), -int(clause_count[i, j]))
                global_i = start_index + int(i); j = int(j)
                key = tuple(tuple(int(v) for v in mask[i, j]) for mask in masks)
                candidate = (rank, (global_i, j))
                if key not in best or rank > best[key][0] or rank == best[key][0] and candidate[1] < best[key][1]:
                    best[key] = candidate
            # Keeping K best distinct predictions is sufficient across blocks;
            # a later block can replace the canonical representative of a tie.
            best = dict(sorted(best.items(), key=lambda item: (*(-v for v in item[1][0]), item[1][1]))[:K])
        trace['exact_score_count'] = len(score_cache)
        if not best:
            raise UnsupportedPolicyError('No bounded rule recognizes the required distinct sources in all three labels')
        def clauses(rs, index):
            return [[deepcopy(atoms[k][0]) for k in terms[j][3]] for j in rs[index][2]]
        candidates = []
        for rank, (i, j) in sorted(best.values(), key=lambda item: (*(-v for v in item[0]), item[1])):
            yclauses, pclauses = clauses(yes, i), clauses(partial, j)
            predictions = [predict_program(x, yclauses, pclauses) for x in X]
            metric, macro, worst = classification_metrics(predictions, y)
            assert (macro, worst, metric['correct']) == rank[:3]
            support = {}
            for name, terms_ in (('yes', yclauses), ('partial', pclauses)):
                support[name] = []
                for clause in terms_:
                    indices = [k for k, x in enumerate(X) if x is not None and all(atom_bounds(x, atom)[0] for atom in clause)]
                    support[name].append({'distinct_sources': len(indices),
                                          'originating_batches': dict(sorted(Counter(batches[k] for k in indices).items()))})
            artifact = {'version': VERSION, 'feature_contract_ref': CONTRACT_REF, 'limits': deepcopy(self.limits),
                        'yes': yclauses, 'partial': pclauses, 'support': support,
                        'training': {'metrics': metric, 'source_groups': groups, 'source_batches': batches,
                                     'feature_ref': digest(X), 'target_ref': digest(y)},
                        'search': deepcopy(trace), 'capacity': {'atoms': -rank[3], 'clauses': -rank[4]},
                        'scope': 'Training fit only; deployment scope requires separate out-of-source validation.'}
            artifact['artifact_ref'] = digest(artifact); candidates.append(artifact)
        self._candidates = candidates; self._artifact = candidates[0]; self.elapsed_seconds = time.monotonic() - start
        return self

    def predict_records(self, X):
        if self._artifact is None:
            raise ValueError('No fitted policy')
        result = []
        for x in X:
            validate_record(x)
            p = predict_program(x, self._artifact['yes'], self._artifact['partial'])
            result.append({'prediction': p, 'reason': 'missing_evidence' if x is None else 'frozen_semantic_dnf'})
        return result

    def predict(self, X):
        return [math.nan if r['prediction'] < 0 else float(r['prediction']) for r in self.predict_records(X)]

    def metadata(self):
        return deepcopy(self._artifact) if self._artifact else {'version': VERSION}

    def candidates(self):
        return deepcopy(self._candidates)

    def render(self):
        if self._artifact is None:
            raise ValueError('No fitted policy')
        lines = []
        for name in ('yes', 'partial'):
            lines.append(('Yes' if name == 'yes' else 'Otherwise Partial') + ' when any clause is established:')
            for c in self._artifact[name]:
                lines.append('- ' + ' AND '.join(('' if a['test'] == 'true' else 'NOT ') + SPECS[a['feature']]['text'] for a in c))
        lines.append('Otherwise No. Unknown evidence is unresolved when its admissible bounds change the label; missing records stay unresolved.')
        return '\n'.join(lines)

    @classmethod
    def restore(cls, artifact):
        if not isinstance(artifact, dict) or artifact.get('version') != VERSION or artifact.get('feature_contract_ref') != CONTRACT_REF:
            raise ValueError('Unknown semantic policy contract')
        body = {k: v for k, v in artifact.items() if k != 'artifact_ref'}
        if digest(body) != artifact.get('artifact_ref'):
            raise ValueError('Policy content hash mismatch')
        limits = artifact['limits']; validate_limits(limits)
        for boundary in ('yes', 'partial'):
            clauses = artifact[boundary]
            if not isinstance(clauses, list) or not 1 <= len(clauses) <= limits['clauses_per_boundary'] or len(artifact['support'][boundary]) != len(clauses):
                raise ValueError('Invalid policy boundary')
            for clause, support in zip(clauses, artifact['support'][boundary]):
                if not 1 <= len(clause) <= limits['atoms_per_clause'] or len({a['feature'] for a in clause}) != len(clause):
                    raise ValueError('Invalid conjunction')
                for a in clause:
                    if set(a) != {'feature', 'test'} or a['feature'] not in SPECS or a['test'] not in ('true', 'false'):
                        raise ValueError('Unknown policy predicate')
                    if SPECS[a['feature']]['role'] != 'context' and a['test'] != 'true':
                        raise ValueError('Reversed physical evidence direction')
                roles = {SPECS[a['feature']]['role'] for a in clause if a['test'] == 'true'}
                if boundary == 'yes' and 'core' not in roles or boundary == 'partial' and not roles & {'core', 'support'}:
                    raise ValueError('Positive label lacks its requested physical witness')
                if support['distinct_sources'] < limits['min_clause_sources'] or len(support['originating_batches']) < limits['min_clause_batches'] or sum(support['originating_batches'].values()) != support['distinct_sources']:
                    raise ValueError('Unsupported conjunction')
        t = artifact['training']
        if len(set(t['source_groups'])) != len(t['source_groups']) or len(t['source_groups']) != len(t['source_batches']):
            raise ValueError('Invalid source support')
        if any(t['metrics']['per_class'][label]['correct'] < limits['min_correct_per_class'] for label in ('no', 'partial', 'yes')):
            raise ValueError('Class-collapsed policy')
        obj = cls(limits=limits); obj._artifact = deepcopy(artifact); obj._candidates = [deepcopy(artifact)]
        return obj
