import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { CaliTreeEvalSecondaryTab } from './CaliTreeEvalSecondaryTab'

function node() {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode('calitree_eval', { x: 0, y: 0 })
  return activeGraphStore().getState().nodes[0]
}

describe('CaliTreeEvalSecondaryTab', () => {
  it('separates full coverage from explicit human-review metrics', () => {
    const n = node()
    activeRunStore().getState().setLastNodeResults({
      [n.id]: {
        status: 'done',
        error: null,
        meta: {},
        outputs: {
          metrics_report: {
            overall: {
              n: 10,
              accuracy: 0.8,
              balanced_accuracy: 0.7,
              confusion: {
                no: { no: 2, partial: 0, yes: 1 },
                partial: { no: 1, partial: 1, yes: 0 },
                yes: { no: 0, partial: 0, yes: 5 },
              },
            },
            train: { n: 0, accuracy: null, balanced_accuracy: null },
            test: { n: 10, accuracy: 0.8, balanced_accuracy: 0.7 },
            selective: {
              overall: {
                n_total: 10,
                n_accepted: 6,
                n_needs_human: 4,
                needs_human_outcome_enabled: true,
                coverage: 0.6,
                review_rate: 0.4,
                error_capture_rate: 1,
                partial_review_rate: 0.5,
                system_accuracy_with_perfect_human_review: 1,
                decision_distribution: {
                  no: 1, partial: 0, yes: 5, needs_human: 4,
                },
                accepted: {
                  n: 6, accuracy: 1, balanced_accuracy: 1,
                },
              },
            },
          },
        },
      },
    })

    render(<CaliTreeEvalSecondaryTab node={n} />)

    expect(screen.getByText('Full coverage · overall').parentElement).toHaveTextContent('80.0%')
    expect(screen.getByText('Auto-decided · overall').parentElement).toHaveTextContent('100.0%')
    expect(screen.getByLabelText('Human review metrics')).toHaveTextContent(
      'auto coverage 60.0%',
    )
    expect(screen.getByLabelText('Human review metrics')).toHaveTextContent(
      'needs human 4 (40.0%)',
    )
    expect(screen.getByLabelText('Human review metrics')).toHaveTextContent(
      'error capture 100.0%',
    )
    expect(screen.getByLabelText('Human review metrics')).toHaveTextContent(
      'upper bound, not model accuracy',
    )
    expect(screen.getByLabelText('Deployment decision distribution')).toHaveTextContent(
      'needs_human: 4',
    )
    expect(screen.getByRole('table', { name: 'Cali-Tree Eval confusion matrix' }))
      .toHaveTextContent('5')
  })
})
