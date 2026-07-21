import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { ClAdversarialSecondaryTab } from './ClAdversarialSecondaryTab'
import { ClRuleEvalSecondaryTab } from './ClRuleEvalSecondaryTab'
import { ClRuleTreeSecondaryTab } from './ClRuleTreeSecondaryTab'

function node(type: string) {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode(type, { x: 0, y: 0 })
  return activeGraphStore().getState().nodes[0]
}

describe('calibration diagnostics', () => {
  it('distinguishes videos from raw ratings and shows frozen-holdout warnings', () => {
    const n = node('cl_rule_tree')
    activeRunStore().getState().setLastNodeResults({
      [n.id]: { status: 'done', error: null, meta: {}, outputs: { judge_rule: {
        n_items: 9, n_observations: 126, evaluation_mode: 'frozen_holdout',
        n_train_items: 7, n_validation_items: 2,
        bank: [{ question: 'Is evidence missing?', raises_score_when: 'yes' }],
        feature_names: ['base_score', 'q1'],
        insample_mae: { bias: 0.8, tree: 0.7 }, loo_mae: { bias: 0.9, tree: 0.9 },
        warnings: ['All usable raw judge scores are constant.'],
        diagnostics: { n_raw_ratings: 126, n_unique_base_scores: 1,
          score_source: { parsed_field: 'score_1_to_5' } },
        dropped_features: [{ question: 'Always false?', reason: 'constant_on_training' }],
        per_item: {},
      } } },
    })
    render(<ClRuleTreeSecondaryTab node={n} />)
    expect(screen.getByText(/Videos:/).parentElement).toHaveTextContent('9')
    expect(screen.getByText(/Raw ratings:/).parentElement).toHaveTextContent('126')
    expect(screen.getByText(/frozen holdout/)).toBeInTheDocument()
    expect(screen.getByText(/raw judge scores are constant/)).toBeInTheDocument()
    expect(screen.getByText(/Dropped constant questions/)).toBeInTheDocument()
  })

  it('shows an uncertainty-aware insufficient-data verdict', () => {
    const n = node('cl_rule_eval')
    activeRunStore().getState().setLastNodeResults({
      [n.id]: { status: 'done', error: null, meta: {}, outputs: { comparison: {
        n_items: 9, metric: 'M5', evaluation_mode: 'frozen_holdout', n_validation_items: 2,
        rows: [{ key: 'bias', label: 'bias', insample: 0.8, loo: 0.9 }],
        verdict: 'Insufficient validation data: 2 independent videos.', beats_bias: false,
        warnings: ['Only 2 validation videos.'],
      } } },
    })
    render(<ClRuleEvalSecondaryTab node={n} />)
    expect(screen.getByText(/Insufficient validation data/)).toBeInTheDocument()
    expect(screen.getByText(/Only 2 validation videos/)).toBeInTheDocument()
  })

  it('shows the immutable polarized disagreement profile', () => {
    const n = node('cl_adversarial')
    activeRunStore().getState().setLastNodeResults({
      [n.id]: { status: 'done', error: null, meta: {}, outputs: { calibration_results: {
        item: {
          item_id: 'item', metric_id: 'M5', original_score: 2, final_score: 2,
          score_delta: 0, converged: false, rounds_run: 4,
          flags: ['oscillation_detected'], optimized_prompt: 'safe', reasoning: 'trace',
          transcript: { item_id: 'item', metric_id: 'M5', turns: [], converged: false },
          human_scores: {}, human_gap: {}, grounded: true,
          human_disagreement_profile: {
            rating_count: 2, histogram: { '2': 1, '5': 1 }, range: 3,
            median: 3.5, modes: [2, 5], polarized: true,
          },
        },
      } } },
    })
    render(<ClAdversarialSecondaryTab node={n} />)
    expect(screen.getByText(/Fixed human disagreement profile — polarized/)).toBeInTheDocument()
    expect(screen.getByText('oscillation_detected')).toBeInTheDocument()
  })
})
