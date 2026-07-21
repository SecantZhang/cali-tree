import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/runs', () => ({
  listDiskRuns: vi.fn(async () => [
    { run_id: '260720-10:00:00', workflow_name: 'wf1', status: 'done', finished_at: 't', n_checkpointed: 5, n_nodes: 4 },
    { run_id: '260719-09:00:00', workflow_name: null, status: 'error', finished_at: 't', n_checkpointed: 2, n_nodes: 3 },
  ]),
  getRunGraph: vi.fn(),
  resumeRun: vi.fn(),
}))

import { RunsTab } from './RunsTab'

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RunsTab />
    </QueryClientProvider>,
  )
}

describe('RunsTab', () => {
  it('lists past runs with status, and offers Resume only for non-terminal-success runs', async () => {
    renderTab()
    await waitFor(() => expect(screen.getByText('260720-10:00:00')).toBeInTheDocument())
    expect(screen.getByText('260719-09:00:00')).toBeInTheDocument()
    // Both have an Open button…
    expect(screen.getAllByRole('button', { name: 'Open' })).toHaveLength(2)
    // …but only the errored run offers Resume.
    expect(screen.getAllByRole('button', { name: 'Resume' })).toHaveLength(1)
    expect(screen.getByText(/wf1/)).toBeInTheDocument()
  })
})
