import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { JudgeSamplePreview } from './JudgeSamplePreview'

const item = {
  item_id: 'prj-a::0::peanut',
  use_case: 'visual montage',
  input: { user_prompt: 'make a montage' },
  output: { output_video_path: '' },
}

describe('JudgeSamplePreview', () => {
  it('renders the item header, use_case, and prompt', () => {
    render(<JudgeSamplePreview item={item} />)
    expect(screen.getByText('prj-a::0::peanut')).toBeInTheDocument()
    expect(screen.getByText('visual montage')).toBeInTheDocument()
    expect(screen.getByText('make a montage')).toBeInTheDocument()
  })

  it('does not render a human-label block when no label is passed', () => {
    const { container } = render(<JudgeSamplePreview item={item} />)
    expect(container.querySelector('.human-label-block')).toBeNull()
  })

  it('renders per-dimension scores when a label is passed, with a dash for a missing dimension', () => {
    const label = {
      n_annotators: 3,
      n_complete: 2,
      scores: { video_addresses_prompt: 4.5, voiceover_matches_visuals: null },
    }
    const { container } = render(<JudgeSamplePreview item={item} label={label} />)
    expect(container.querySelector('.human-label-block')).not.toBeNull()
    expect(screen.getByText(/3 annotator\(s\), 2 complete/)).toBeInTheDocument()
    expect(screen.getByText('4.50')).toBeInTheDocument()
    // A null-scored dimension renders a dash, not a crash.
    expect(container.querySelectorAll('.label-score-missing').length).toBeGreaterThan(0)
  })
})
