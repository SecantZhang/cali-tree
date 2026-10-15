from copy import deepcopy

from critical.core.decision.artifacts import digest
from run.calitree_semantic_baselines import Fits, build_context, context_predictions
from tests.unit.calitree.test_semantic_hierarchy_m2 import samples


def test_outer_and_inner_fits_exclude_their_evaluation_sources(tmp_path):
    X, y, groups, batches = samples(48)
    rows = [{'case': f'C{i:02d}', 'id': str(i), 'source_group': groups[i],
             'batch': batches[i], 'reference': y[i], 'features': X[i]} for i in range(48)]
    fitting, held = rows[:36], rows[36:]
    context = build_context(fitting, Fits(tmp_path))
    unseen = {r['source_group'] for r in held}
    assert not unseen & set(context['fit_sources'])
    for p in [context['pooled'], *context['experts'].values()]:
        assert not unseen & set(p['training']['source_groups'])
    for fold in context['inner_pooled_oof']:
        assert set(fold['fit_sources']).isdisjoint(fold['validation_sources'])
        assert not unseen & (set(fold['fit_sources']) | set(fold['validation_sources']))
    before = digest(context)
    result = context_predictions(context, held)
    changed = deepcopy(held)
    for r in changed:
        r['reference'] = (r['reference'] + 1) % 3
    after = context_predictions(context, changed)
    assert result['pooled'] == after['pooled'] and result['routed'] == after['routed']
    assert digest(context) == before
    replayed = build_context(fitting, Fits(tmp_path, replay=True))
    assert replayed == context
