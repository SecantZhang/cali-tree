import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { activeGraphStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { LMEngineSecondaryTab } from './LMEngineSecondaryTab'

const checkEngineHealth = vi.fn()
vi.mock('../../../api/engines', () => ({
  checkEngineHealth: (...args: unknown[]) => checkEngineHealth(...args),
}))

// The global test setup (src/test/setup.ts) resets the tabs singleton after every test.
function seed() {
  useTabsStore.getState().openBlankTab()
  const g = activeGraphStore().getState()
  g.addNode('lm_engine', { x: 0, y: 0 })
  g.addNode('judge', { x: 200, y: 0 })
  const [engine, judge] = activeGraphStore().getState().nodes
  return { engine, judge }
}

beforeEach(() => {
  checkEngineHealth.mockReset()
})

describe('LMEngineSecondaryTab', () => {
  it('shows the effective config and "not wired" when the engine feeds nothing', () => {
    const { engine } = seed()
    render(<LMEngineSecondaryTab node={engine} />)
    expect(screen.getByText('Engine kind:')).toBeInTheDocument()
    expect(screen.getByText(/Not wired to any Judge node yet/)).toBeInTheDocument()
  })

  it('lists the Judge node(s) this engine feeds', () => {
    const { engine, judge } = seed()
    activeGraphStore().getState().onConnect({
      source: engine.id, sourceHandle: 'engine_config',
      target: judge.id, targetHandle: 'engine_config',
    })
    render(<LMEngineSecondaryTab node={engine} />)
    expect(screen.getByText('Judge')).toBeInTheDocument()
  })

  it('confirms before the billable health check, then renders endpoint results', async () => {
    const { engine } = seed()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    checkEngineHealth.mockResolvedValue({
      endpoints: [
        { url: 'https://primary', ok: true, status: 200, latency: 0.05, error: null },
        { url: 'https://mirror', ok: false, status: 503, latency: 0.2, error: 'down' },
      ],
    })

    render(<LMEngineSecondaryTab node={engine} />)
    fireEvent.click(screen.getByRole('button', { name: 'Test this engine' }))

    expect(window.confirm).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.getByText('https://primary')).toBeInTheDocument())
    expect(screen.getByText('https://mirror')).toBeInTheDocument()
    expect(screen.getByText('down')).toBeInTheDocument()
    expect(checkEngineHealth).toHaveBeenCalledWith('gpt', expect.anything(), true)
  })

  it('does not call the health check if the confirm is dismissed', () => {
    const { engine } = seed()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<LMEngineSecondaryTab node={engine} />)
    fireEvent.click(screen.getByRole('button', { name: 'Test this engine' }))
    expect(checkEngineHealth).not.toHaveBeenCalled()
  })
})
