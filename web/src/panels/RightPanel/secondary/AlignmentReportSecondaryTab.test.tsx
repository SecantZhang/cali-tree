import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { AlignmentReportSecondaryTab } from './AlignmentReportSecondaryTab'

function seed() {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode('alignment_report', { x: 0, y: 0 })
  return activeGraphStore().getState().nodes[0]
}

describe('AlignmentReportSecondaryTab', () => {
  it('renders our SRCC/PLCC/KRCC row, human ceiling, verdict, and the VE-Bench baselines', () => {
    const node = seed()
    activeRunStore().getState().setLastNodeResults({
      [node.id]: {
        status: 'done', error: null, meta: {},
        outputs: {
          comparison: {
            n_items: 120,
            verdict: 'Best dimension edit_quality: SRCC 0.545 — above the zero-shot baselines',
            rows: [{
              dimension: 'edit_quality', n: 120,
              srcc: 0.545, plcc: 0.508, krcc: 0.415, mae: 2.79, human_ceiling_mae: 1.1,
            }],
            baselines: [
              { method: 'CLIP-F', kind: 'zero-shot', srcc: 0.228, plcc: 0.186 },
              { method: 'VE-Bench QA', kind: 'trained on VE-Bench', srcc: 0.742, plcc: 0.733 },
            ],
          },
        },
      },
    })
    render(<AlignmentReportSecondaryTab node={node} />)
    expect(screen.getByText(/above the zero-shot baselines/)).toBeInTheDocument()
    expect(screen.getByText('edit_quality')).toBeInTheDocument()
    expect(screen.getByText('0.545')).toBeInTheDocument() // SRCC
    expect(screen.getByText('0.508')).toBeInTheDocument() // PLCC
    expect(screen.getByText('1.100')).toBeInTheDocument() // human ceiling
    // Published reference rows present.
    expect(screen.getByText('VE-Bench QA')).toBeInTheDocument()
    expect(screen.getByText('CLIP-F')).toBeInTheDocument()
  })

  it('shows an empty hint before a run', () => {
    const node = seed()
    render(<AlignmentReportSecondaryTab node={node} />)
    expect(screen.getByText(/Run the upstream Eval node/)).toBeInTheDocument()
  })
})
