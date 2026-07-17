import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DataValueView, summarize } from './DataValueView'

describe('DataValueView / summarize', () => {
  it('summarizes large collections instead of dumping them', () => {
    const big = Object.fromEntries(Array.from({ length: 1170 }, (_, i) => [`item${i}`, i]))
    expect(summarize(big)).toContain('1170 keys')
    expect(summarize(Array.from({ length: 500 }, (_, i) => i))).toBe('list · 500 items')
    // A base64/data string is flagged, not shown.
    expect(summarize('data:video/mp4;base64,' + 'A'.repeat(500))).toContain('base64/data')
  })

  it('renders a scalar inline and a collection as a collapsed summary', () => {
    const { rerender, container } = render(<DataValueView value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(container.querySelector('details')).toBeNull()

    rerender(<DataValueView value={{ a: 1, b: 2, c: 3 }} />)
    const details = container.querySelector('details') as HTMLDetailsElement
    expect(details).not.toBeNull()
    expect(details.open).toBe(false) // collapsed by default — never auto-dumps
    expect(screen.getByText(/object · 3 keys/)).toBeInTheDocument()
  })

  it('caps a huge string preview', () => {
    const { container } = render(<DataValueView value={'x'.repeat(5000)} />)
    const pre = container.querySelector('pre.json-preview')!
    expect(pre.textContent!.length).toBeLessThan(1200)
    expect(pre.textContent).toContain('+')
  })
})
