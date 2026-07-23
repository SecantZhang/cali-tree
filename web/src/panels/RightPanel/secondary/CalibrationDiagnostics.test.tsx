import { act, fireEvent, render, screen } from '@testing-library/react'
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
    const { container } = render(<ClRuleTreeSecondaryTab node={n} />)
    const metricTable = container.querySelector('.calibration-mae-table')
    expect(metricTable).toHaveClass('calibration-mae-table')
    expect(screen.getByRole('columnheader', { name: 'training' })).toHaveClass('calibration-mae-number')
    expect(screen.getByRole('columnheader', { name: 'held-out' })).toHaveClass('calibration-mae-number')
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

  it('shows graded semantic evidence and training-only tree selection', () => {
    const n = node('cl_semantic_tree')
    activeRunStore().getState().setLastNodeResults({
      [n.id]: { status: 'done', error: null, meta: {}, outputs: { judge_rule: {
        n_items: 8, n_observations: 40, evaluation_mode: 'frozen_holdout',
        n_train_items: 6, n_validation_items: 2,
        bank: [{
          question: 'Does the opening establish context?', raises_score_when: 'yes',
          scope: 'item_quality',
        }],
        insample_mae: { semantic: 0.6 }, loo_mae: { semantic: 0.8 },
        semantic_tree_selection: {
          selected: {
            feature_set: 'rubric', max_depth: 3, min_samples_leaf: 2,
            semantic_split_count: 3, semantic_prompt_coverage: 3, raw_score_split_count: 0,
            semantic_coverage_tolerance: 0.01, selected_cv_penalty_for_coverage: 0.003,
            prefer_deeper_within_tolerance: true,
          },
          training_grouped_loo: [], validation_labels_used: false,
        },
        semantic_split_count: 3, raw_score_split_count: 0,
        leaf_feature_names: ['base_score', 'score_std'],
        per_item: {
          item: { base: 2, human: [3, 4], booleans: [1], semantic_values: [0.667], missing: [] },
        },
      } } },
    })
    render(<ClRuleTreeSecondaryTab node={n} />)
    expect(screen.getByText(/training-only grouped LOO/)).toHaveTextContent('depth 3')
    expect(screen.getByText(/validation labels used for tuning/)).toHaveTextContent('no')
    expect(screen.getByText(/graded semantics and debate rules/)).toBeInTheDocument()
    expect(screen.getByText(/Semantic-first structure/)).toHaveTextContent('3 learned semantic split(s)')
    expect(screen.getByText(/Semantic-first structure/)).toHaveTextContent('0 raw-score split(s)')
    expect(screen.getByText(/Broader semantic coverage cost/)).toBeInTheDocument()
    expect(screen.getByText(/Exploratory depth preference is enabled/)).toBeInTheDocument()
    expect(screen.getByText('[0.667]')).toBeInTheDocument()
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

  it('renders cumulative live debate turns and preserves the selected concurrent item', () => {
    const n = node('cl_adversarial')
    activeGraphStore().getState().setNodeStatus(n.id, 'running')
    const run = activeRunStore().getState()
    act(() => {
      run.setLiveDebate(n.id, {
        item_id: 'item-a', metric_id: 'M3', revision: 1, state: 'running',
        initial_judge_result: {
          metric_id: 'M3', parsed: { score_1_to_5: 3, reasoning_lines: ['anchor a'] },
        },
        turns: [{
          round: 1, role: 'human_proxy', valid: true,
          parsed: { score_1_to_5: 2, reasoning_lines: ['proxy a'] },
        }],
      })
      run.setLiveDebate(n.id, {
        item_id: 'item-b', metric_id: 'M3', revision: 0, state: 'running',
        initial_judge_result: {
          metric_id: 'M3', parsed: { score_1_to_5: 4, reasoning_lines: ['anchor b'] },
        },
        turns: [],
      })
    })

    const { container } = render(<ClAdversarialSecondaryTab node={n} />)
    expect(screen.getByText('proxy a')).toBeInTheDocument()
    expect(screen.getByText('Judge responding…')).toBeInTheDocument()

    const itemB = screen.getByText('item-b', { exact: false }).closest('li')!
    fireEvent.click(itemB)
    expect(itemB).toHaveClass('active')
    expect(screen.getByText('anchor b')).toBeInTheDocument()
    expect(screen.getByText('Human proxy responding…')).toBeInTheDocument()

    act(() => {
      run.setLiveDebate(n.id, {
        item_id: 'item-a', metric_id: 'M3', revision: 2, state: 'running',
        initial_judge_result: {
          metric_id: 'M3', parsed: { score_1_to_5: 3, reasoning_lines: ['anchor a'] },
        },
        turns: [
          {
            round: 1, role: 'human_proxy', valid: true,
            parsed: { score_1_to_5: 2, reasoning_lines: ['proxy a'] },
          },
          {
            round: 1, role: 'judge', valid: true,
            parsed: { score_1_to_5: 3, reasoning_lines: ['judge a'] },
          },
        ],
      })
    })
    expect(itemB).toHaveClass('active')
    expect(container).toHaveTextContent('anchor b')
    expect(container).not.toHaveTextContent('judge a')
  })

  it('keeps a completed calibration partial visible while a downstream node runs', () => {
    const n = node('cl_adversarial')
    activeGraphStore().getState().setNodeStatus(n.id, 'done')
    activeRunStore().getState().setPartialResult(n.id, {
      calibration_results: {
        item: {
          item_id: 'item', metric_id: 'M5', original_score: 2, final_score: 3,
          score_delta: 1, converged: true, rounds_run: 1, flags: [],
          optimized_prompt: 'persisted semantic prompt', reasoning: 'finished debate',
          transcript: {
            turns: [{
              round: 1, role: 'judge', valid: true,
              parsed: { score_1_to_5: 3, reasoning_lines: ['still visible'] },
            }],
            converged: true,
          },
          human_scores: {}, human_gap: {}, grounded: false,
        },
      },
    }, {})

    render(<ClAdversarialSecondaryTab node={n} />)

    expect(screen.getByText('still visible')).toBeInTheDocument()
    expect(screen.getByText(/Calibrated:/).parentElement).toHaveTextContent('3')
  })
})
