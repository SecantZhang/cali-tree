import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProgressBar } from './ProgressBar'

describe('ProgressBar', () => {
  it('renders a determinate fill when total is known', () => {
    const { container } = render(<ProgressBar progress={{ completed: 1, total: 4 }} label="x" />)
    const fill = container.querySelector('.progress-bar-fill') as HTMLElement
    expect(fill).not.toHaveClass('progress-bar-idle')
    expect(fill).not.toHaveClass('progress-bar-indeterminate')
    expect(fill.style.width).toBe('25%')
  })

  it('renders the busy indeterminate animation when total is null', () => {
    const { container } = render(<ProgressBar progress={{ completed: 0, total: null }} label="x" />)
    const fill = container.querySelector('.progress-bar-fill') as HTMLElement
    expect(fill).toHaveClass('progress-bar-indeterminate')
  })

  it('renders a flat idle bar (distinct from busy) when progress is null', () => {
    const { container } = render(<ProgressBar progress={null} label="Idle" />)
    const fill = container.querySelector('.progress-bar-fill') as HTMLElement
    expect(fill).toHaveClass('progress-bar-idle')
    expect(fill).not.toHaveClass('progress-bar-indeterminate')
    expect(container.querySelector('.progress-bar-wrap-idle')).not.toBeNull()
    // No count shown in the idle state.
    expect(container.querySelector('.progress-bar-count')).toBeNull()
  })
})
