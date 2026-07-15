import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DecisionTreeView, type DecisionTreeNode } from './DecisionTreeView'

const SPLIT: DecisionTreeNode = {
  leaf: false,
  samples: 6,
  value: 3.0,
  feature: 'q2',
  threshold: 0.5,
  left: { leaf: true, samples: 4, value: 2.0 },
  right: { leaf: true, samples: 2, value: 4.0 },
}

describe('DecisionTreeView', () => {
  it('draws a split condition, both leaf values, and true/false branch labels', () => {
    const { container, getByText } = render(<DecisionTreeView tree={SPLIT} />)
    expect(container.querySelector('svg')).not.toBeNull()
    // Split node shows the feature + threshold.
    expect(getByText('q2')).toBeInTheDocument()
    expect(getByText('≤ 0.5')).toBeInTheDocument()
    // Both leaves render their calibrated score.
    expect(getByText('→ 2.00')).toBeInTheDocument()
    expect(getByText('→ 4.00')).toBeInTheDocument()
    // Branches are labeled so the tree reads without the raw text.
    expect(getByText('true')).toBeInTheDocument()
    expect(getByText('false')).toBeInTheDocument()
  })

  it('surfaces the mined rule as a tooltip on a split feature', () => {
    const { container } = render(
      <DecisionTreeView
        tree={SPLIT}
        featureTooltip={(f) => (f === 'q2' ? 'q2: over-penalizes a flaw?' : undefined)}
      />,
    )
    expect(container.querySelector('title')?.textContent).toContain('over-penalizes')
  })

  it('renders a lone leaf when the tree never split (degenerate fit)', () => {
    const { container, getByText } = render(
      <DecisionTreeView tree={{ leaf: true, samples: 5, value: 3.0 }} />,
    )
    expect(container.querySelector('svg')).not.toBeNull()
    expect(getByText('→ 3.00')).toBeInTheDocument()
    // No branch labels on a single leaf.
    expect(container.textContent).not.toContain('true')
  })
})
