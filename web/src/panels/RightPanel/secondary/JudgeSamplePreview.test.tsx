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

  it('renders ImagenHub image pairs and three-rater SC/PQ provenance', () => {
    const imageItem = {
      item_id: 'sample_1_1::SDEdit',
      use_case: 'text-guided-image-editing',
      input: {
        user_prompt: 'make it blue',
        source_image_path: '/tmp/source.jpg',
      },
      output: { edited_image_path: '/tmp/edited.jpg' },
    }
    const label = {
      target_label: 'partial',
      median_sc: 0.5,
      ratings: [
        { sc: 0, pq: 1 },
        { sc: 0.5, pq: 0.5 },
        { sc: 1, pq: 1 },
      ],
    }
    render(<JudgeSamplePreview item={imageItem} label={label} />)
    expect(screen.getByAltText('Source')).toBeInTheDocument()
    expect(screen.getByAltText('Edited')).toBeInTheDocument()
    expect(screen.getByText(/Human target:/).parentElement).toHaveTextContent('partial')
    expect(screen.getByText(/^Raters:/)).toHaveTextContent('SC 0.5 / PQ 0.5')
  })
})
