"""M7 bounded hierarchy construction with reusable M5/M6 components."""
from collections import Counter
from copy import deepcopy

from ...decision.artifacts import digest
from .hierarchy_protocol_v9 import SEARCH, score
from .hierarchy_scopes_v9 import matches
from .hierarchy_similarity_v9 import seed_bank, propose
from .hierarchy_merge_v9 import parent_node, replacement, active_complexity, decide, predictions


def build(rows, folds, context, fold_contexts, fits, emit):
    """Search development only; emit every candidate before any promotion.

    No final-test or separate development-batch examples are accepted here.
    Unpromoted local candidates may seed a parent, but the comparator is always
    the actual current system, including the pooled fallback.
    """
    rows = list(rows)
    bank = seed_bank(context, rows)
    frontier = set(bank)
    fold_rows = {f: [r for r in rows if folds[r['source_group']] != f] for f in fold_contexts}
    fold_banks = {f: seed_bank(c, fold_rows[f], include_duplicates=True) for f, c in fold_contexts.items()}
    current, fold_current = deepcopy(context['bundle']), {f: deepcopy(c['bundle']) for f, c in fold_contexts.items()}
    initial = deepcopy(current)
    history, states, state_tried = [], [], {}

    def oof(bundles):
        by_source = {}
        for f, bundle in bundles.items():
            selected = [r for r in rows if folds[r['source_group']] == f]
            ds = predictions(bundle, selected)
            by_source.update({r['source_group']: d for r, d in zip(selected, ds)})
        if set(by_source) != {r['source_group'] for r in rows}:
            raise ValueError('OOF scoring omitted or duplicated sources')
        return [by_source[r['source_group']] for r in rows]

    initial_oof = oof(fold_current)
    while len(history) < SEARCH['max_parent_proposals']:
        state_ref = current['bundle_ref']
        tried = state_tried.setdefault(state_ref, set())
        proposals, rejected = propose(frontier, bank, rows, tried)
        state = {'state_ref': state_ref, 'frontier': sorted(frontier),
                 'ranked_proposals': proposals, 'ineligible_pairs': rejected}
        emit('states/' + str(len(states)), state); states.append(state)
        if not proposals:
            stop = 'no_eligible_unevaluated_pair'
            break
        proposal = proposals[0]; children = proposal['children']; tried.add(proposal['pair_ref'])
        full, union = parent_node(children, bank, rows, fits)
        if full is None:
            raise ValueError('M5 proposed a parent without a measurable full-fit scope')
        after = replacement(current, full, bank)
        fold_after, fold_nodes, fold_unions, missing = {}, {}, {}, []
        for f in sorted(fold_contexts):
            child_missing = [c for c in children if c not in fold_banks[f]]
            if child_missing:
                missing.append({'fold': f, 'reason': 'missing_child_policy', 'children': child_missing})
                fold_after[f] = fold_current[f]; continue
            node, manifest = parent_node(children, fold_banks[f], fold_rows[f], fits)
            fold_unions[f] = manifest
            if node is None:
                missing.append({'fold': f, 'reason': manifest['reason']})
                fold_after[f] = fold_current[f]; continue
            evaluated_sources = {r['source_group'] for r in rows if folds[r['source_group']] == f}
            if set(node['fit_sources']) & evaluated_sources:
                raise ValueError('Parent or warm-start lineage leaked an OOF source')
            fold_nodes[f] = node
            fold_after[f] = replacement(fold_current[f], node, fold_banks[f])
        before_ps, after_ps = oof(fold_current), oof(fold_after)
        protected = {}
        for child in children:
            protected['instruction_scope:' + child] = [i for i, r in enumerate(rows) if matches(r['scope'], bank[child]['scope'])]
            for batch in bank[child]['originating_batches']:
                protected['originating_batch:' + batch] = [i for i, r in enumerate(rows) if r['batch'] == batch]
        structural = []
        if not full['specialist_eligible']:
            structural.extend(full['eligibility_reasons'])
        training = score(rows, predictions(after, rows))
        # Preserve the user's accepted M2 local fitting floor for the complete
        # system. An OOF gain cannot silently destroy the 44/48 starting fit.
        if training['correct'] <= 0.9 * len(rows):
            structural.append('complete_system_local_fit_not_above_90_percent')
        decision = decide(rows, before_ps, after_ps, protected,
                          active_complexity(current), active_complexity(after), structural_errors=structural)
        if missing:
            decision['insufficient_evidence'].append('not_all_outer_folds_have_supported_child_scopes')
            decision['status'] = 'insufficient' if not structural else 'rejected'
        step = {'index': len(history), 'state_before_ref': state_ref, 'proposal': proposal,
                'parent': full, 'union_manifest': union, 'fold_parents': fold_nodes,
                'fold_union_manifests': fold_unions, 'missing_folds': missing,
                'full_candidate_bundle': after, 'fold_candidate_bundles': fold_after,
                'before_oof': before_ps, 'after_oof': after_ps, 'training_metrics': training,
                'decision': decision}
        emit('candidates/' + str(len(history)), step)
        history.append(step)
        if decision['status'] == 'accepted':
            current = after; fold_current = fold_after; bank[full['node_id']] = full
            frontier.difference_update(children); frontier.add(full['node_id'])
            for f in fold_banks:
                fold_banks[f][full['node_id']] = fold_nodes[f]
        print({'stage': 'M6/M7', 'proposal': len(history), 'children': children,
               'fit_union': len(full['fit_sources']), 'parent_local_correct': full['metrics']['correct'],
               'system_training': training['correct'], 'oof_before': decision['before']['correct'],
               'oof_after': decision['after']['correct'], 'decision': decision['status'],
               'reasons': decision['reasons'], 'insufficient': decision['insufficient_evidence']}, flush=True)
    else:
        stop = 'parent_proposal_budget_exhausted'
    final_oof = oof(fold_current)
    return {'bundle': current, 'fold_bundles': fold_current, 'node_registry': bank,
            'frontier': sorted(frontier), 'initial_bundle_ref': initial['bundle_ref'],
            'initial_oof': initial_oof, 'final_oof': final_oof,
            'initial_oof_metrics': score(rows, initial_oof), 'final_oof_metrics': score(rows, final_oof),
            'history': history, 'states': states, 'stop_reason': stop,
            'proposal_count': len(history), 'acceptance_counts': dict(Counter(s['decision']['status'] for s in history)),
            'new_model_calls': 0, 'reserved_test_predictions': 0,
            'interpretation': 'Bounded development search, not a final-test or repeated-model robustness result.'}

