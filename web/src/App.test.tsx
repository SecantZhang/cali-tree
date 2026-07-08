import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { activeGraphStore, activeRunStore } from './store/activeTab'
import { useTabsStore } from './store/tabsStore'
import { ThemeProvider } from './theme/ThemeProvider'

const NODE_TYPES = [
  {
    type: 'peanut_source', category: 'node_db', input_sockets: {},
    output_sockets: { raw_dataset: 'raw_dataset' }, param_schema: {},
  },
  {
    type: 'dataset', category: 'node_db', input_sockets: { raw_dataset: 'raw_dataset' },
    output_sockets: { dataset: 'dataset', labels: 'labels' }, param_schema: {},
  },
  {
    type: 'preprocessing', category: 'node_preprocessing', input_sockets: { dataset: 'dataset' },
    output_sockets: { dataset: 'dataset' }, param_schema: {},
  },
  {
    type: 'judge_text', category: 'node_vejudge', input_sockets: { dataset: 'dataset' },
    output_sockets: { judge_result: 'judge_result' }, param_schema: {},
  },
  {
    type: 'judge_video', category: 'node_vejudge', input_sockets: { dataset: 'dataset' },
    output_sockets: { judge_result: 'judge_result' }, param_schema: {},
  },
  {
    type: 'eval', category: 'node_eval',
    input_sockets: { judge_result_text: 'judge_result', judge_result_video: 'judge_result', labels: 'labels' },
    output_sockets: { metrics_report: 'metrics_report' }, param_schema: {},
  },
]

// Set by the meta.warning test below, right before it triggers the run — mockJsonFor needs
// the real (dynamically-generated) node id to key the fake /api/runs/warn-run-1 response.
let warnRunNodeId = ''
// Set by the Resume-button test to control what /api/workflows/<name>/runs reports.
let workflowRunsResponse: unknown[] = []

function mockJsonFor(url: string): unknown {
  if (url.endsWith('/api/nodes')) return NODE_TYPES
  if (url.includes('/api/workflows/') && url.endsWith('/runs')) return workflowRunsResponse
  if (url.endsWith('/api/workflows')) return []
  if (url.endsWith('/api/datasets/loaders')) return []
  if (url.includes('/api/datasets/') && url.includes('/items') && !url.includes('/items/')) {
    return { items: [] }
  }
  if (url.endsWith('/api/settings/credentials')) {
    return { configured: false, source: 'none', base_url: null }
  }
  if (url.endsWith('/api/runs/warn-run-1')) {
    return {
      run_id: 'warn-run-1',
      status: 'done',
      error: null,
      node_results: {
        [warnRunNodeId]: {
          status: 'done',
          error: null,
          meta: { n_items: 0, warning: "Matched 0 items for loader 'peanut_eval'." },
          outputs: { dataset: {} },
        },
      },
    }
  }
  return {}
}

beforeEach(() => {
  localStorage.clear()
  workflowRunsResponse = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => mockJsonFor(url),
    })),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

describe('App shell', () => {
  it('renders the 4-pane layout', async () => {
    renderApp()
    expect(screen.getByText('VEJudge Interface')).toBeInTheDocument()
    expect(await screen.findByText('dataset')).toBeInTheDocument() // node palette item
    expect(screen.getByText('Select a node to inspect its parameters.')).toBeInTheDocument()
    expect(screen.getByText('Run a graph to see live logs here.')).toBeInTheDocument()
  })

  it('opens exactly one blank tab on a fresh load, even under StrictMode\'s double-invoked effects', async () => {
    // A real bug found via a manual `npm run dev` visual check, not by any automated
    // test: React 18 StrictMode (wraps <App> in main.tsx) double-invokes effects in
    // development (mount -> cleanup -> mount again, synchronously, before any
    // re-render). App.tsx's bootstrap effect originally checked the closure-captured
    // `hasTabs` rather than fresh store state, so both invocations saw the same stale
    // `false` and each opened their own blank tab. `renderApp()` above doesn't wrap in
    // StrictMode (matching the production build the E2E suite exercises, where React
    // compiles the double-invocation out) — this test wraps explicitly to reproduce it.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <StrictMode>
        <ThemeProvider>
          <QueryClientProvider client={queryClient}>
            <App />
          </QueryClientProvider>
        </ThemeProvider>
      </StrictMode>,
    )
    await screen.findByText('dataset') // wait for the shell to finish mounting
    expect(useTabsStore.getState().tabs).toHaveLength(1)
  })

  it('toggles the left panel', async () => {
    const { container } = renderApp()
    const toggle = screen.getByTitle('Toggle left panel')
    expect(container.querySelector('.left-panel.collapsed')).toBeNull()
    fireEvent.click(toggle)
    expect(container.querySelector('.left-panel.collapsed')).not.toBeNull()
  })

  it('adding a node from the palette shows it in the Inspector', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('judge_video'))
    expect(screen.getByRole('heading', { name: 'judge_video' })).toBeInTheDocument()
    // One copy inline on the node (expanded by default), one in the Inspector.
    expect(screen.getAllByText('batch_size').length).toBe(2)
  })

  it('double-clicking a node opens its secondary tab with a params summary header', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('peanut_source'))
    const nodeTitle = await screen.findByText('Peanut Source') // NodeChrome header, not the palette item
    fireEvent.doubleClick(nodeTitle)

    expect(await screen.findByText('No items found.')).toBeInTheDocument()
    const summary = container.querySelector('.secondary-summary')
    expect(summary?.textContent).toContain('peanut_eval') // Loader
    expect(summary?.textContent).toContain('all') // Projects (none set)
    fireEvent.click(screen.getByText('Close'))
    expect(screen.queryByText('No items found.')).toBeNull()
  })

  it('shows a live progress readout in the Judge secondary tab while running', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('judge_text'))
    const nodeId = activeGraphStore().getState().nodes[0].id

    act(() => {
      activeGraphStore().getState().setNodeStatus(nodeId, 'running')
      activeRunStore().getState().setCurrentRunningNode(nodeId)
      activeRunStore().getState().setNodeProgressTotal(nodeId, 5)
      activeRunStore().getState().incrementNodeProgress(nodeId)
      activeRunStore().getState().appendLog({ ts: Date.now(), nodeId, text: `${nodeId} x::0 M3` })
    })

    fireEvent.doubleClick(screen.getByText('Text Judge')) // NodeChrome header
    expect(screen.getByText('Judging…')).toBeInTheDocument()
    // The same log line also appears in the bottom Console (filtered to the selected
    // node), so there can be more than one match — just confirm it rendered somewhere.
    expect(screen.getAllByText(`${nodeId} x::0 M3`).length).toBeGreaterThan(0)
  })

  it('editing a param inline on the node updates the same value the Inspector shows', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('peanut_source'))

    // The node is expanded by default and shows the full param list inline — one "model"
    // input on the node, one in the Inspector, both bound to the same store value.
    const modelInputs = screen.getAllByDisplayValue('peanut')
    expect(modelInputs.length).toBe(2)
    fireEvent.change(modelInputs[0], { target: { value: 'coconut' } })

    // Inspector (right panel) reflects the same store value written by the inline edit.
    const inspectorInputs = screen.getAllByDisplayValue('coconut')
    expect(inspectorInputs.length).toBe(2) // one on the node, one in the Inspector
  })

  it('collapsing a node hides its inline params behind a summary line', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('peanut_source'))
    // Both the inline node and the Inspector show a "model" param label while expanded.
    expect(screen.getAllByText('model').length).toBe(2)

    fireEvent.click(screen.getByTitle('Collapse'))
    // Only the Inspector's copy remains — the node itself now shows the summary line.
    expect(screen.getAllByText('model').length).toBe(1)
    expect(screen.getByText('model: peanut')).toBeInTheDocument()
  })

  it('shows a green running border and a live progress bar while a node executes', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('judge_text'))
    const nodeId = activeGraphStore().getState().nodes[0].id

    // Idle: no running highlight, no progress bar.
    expect(container.querySelector('.rf-node.is-running')).toBeNull()
    expect(container.querySelector('.node-progress-bar')).toBeNull()

    act(() => {
      activeGraphStore().getState().setNodeStatus(nodeId, 'running')
      activeRunStore().getState().setCurrentRunningNode(nodeId)
      activeRunStore().getState().setNodeProgressTotal(nodeId, 4)
      activeRunStore().getState().incrementNodeProgress(nodeId)
    })

    expect(container.querySelector('.rf-node.is-running')).not.toBeNull()
    const fill = container.querySelector('.node-progress-bar .progress-bar-fill') as HTMLElement
    expect(fill).not.toBeNull()
    expect(fill.style.width).toBe('25%')

    act(() => {
      activeGraphStore().getState().setNodeStatus(nodeId, 'done')
    })
    expect(container.querySelector('.rf-node.is-running')).toBeNull()
  })

  it('shows top-bar overall + current-node progress bars only while running', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('judge_text'))
    const nodeId = activeGraphStore().getState().nodes[0].id

    expect(container.querySelector('.run-progress')).toBeNull()

    act(() => {
      activeRunStore().getState().beginRun('run-1', 3)
      activeRunStore().getState().setCurrentRunningNode(nodeId)
      activeRunStore().getState().setNodeProgressTotal(nodeId, 2)
      activeRunStore().getState().incrementNodeProgress(nodeId)
      activeRunStore().getState().markNodeCompleted('some-other-node')
    })

    expect(screen.getByText('Workflow progress')).toBeInTheDocument()
    expect(screen.getByText(`Running: Text Judge (${nodeId})`)).toBeInTheDocument()
    const bars = container.querySelectorAll('.run-progress .progress-bar-fill')
    expect(bars).toHaveLength(2)
    expect((bars[0] as HTMLElement).style.width).toBe(`${(1 / 3) * 100}%`) // overall: 1/3 nodes done
    expect((bars[1] as HTMLElement).style.width).toBe('50%') // current node: 1/2

    act(() => {
      activeRunStore().getState().setStatus('done')
    })
    expect(container.querySelector('.run-progress')).toBeNull()
  })

  it('shows a Resume button only when the current workflow\'s latest run is resumable', async () => {
    renderApp()
    expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull()

    workflowRunsResponse = [
      { run_id: 'run-x', status: 'error', dry_run: true, allow_live: false, n_checkpointed: 3 },
    ]
    act(() => {
      activeGraphStore().getState().setCurrentWorkflowName('my_wf')
    })
    const resumeButton = await screen.findByRole('button', { name: 'Resume' })

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(resumeButton)
    await waitFor(() => {
      const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls as [
        string,
        RequestInit | undefined,
      ][]
      const resumeCall = calls.find(([url]) => url.endsWith('/api/runs'))
      expect(resumeCall).toBeTruthy()
      expect(JSON.parse(resumeCall?.[1]?.body as string)).toEqual({ resume_from: 'run-x' })
    })
  })

  it('does not show Resume when the latest run already finished cleanly', async () => {
    workflowRunsResponse = [
      { run_id: 'run-y', status: 'done', dry_run: true, allow_live: false, n_checkpointed: 5 },
    ]
    renderApp()
    act(() => {
      activeGraphStore().getState().setCurrentWorkflowName('my_wf')
    })
    await waitFor(() => {
      const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls as [string][]
      expect(calls.some(([url]) => url.endsWith('/api/workflows/my_wf/runs'))).toBe(true)
    })
    expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull()
  })

  it('shows a Stop button only while running, and clicking it POSTs to the stop endpoint', async () => {
    renderApp()
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()

    act(() => {
      activeRunStore().getState().beginRun('run-to-stop', 2)
    })
    const stopButton = screen.getByRole('button', { name: 'Stop' })

    fireEvent.click(stopButton)
    await waitFor(() => {
      const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls as [
        string,
        RequestInit | undefined,
      ][]
      const stopCall = calls.find(([url]) => url.endsWith('/api/runs/run-to-stop/stop'))
      expect(stopCall).toBeTruthy()
      expect(stopCall?.[1]?.method).toBe('POST')
    })
    expect(activeRunStore().getState().status).toBe('stopping')
    // Once stopping, the button disappears — there's nothing further to do but wait.
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Stopping…' })).toBeInTheDocument()
  })

  it('surfaces a node meta.warning as a console log line and inside its secondary tab', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('dataset'))
    const nodeId = activeGraphStore().getState().nodes[0].id
    warnRunNodeId = nodeId

    await act(async () => {
      activeRunStore().getState().beginRun('warn-run-1', 1)
    })

    // The fast-completion resync path (the run is already "done" by the time the very
    // first GET fires) is exactly what a 0-items run looks like — this must still surface
    // the warning, not just the WS-driven path.
    await screen.findByText(`${nodeId}: warning — Matched 0 items for loader 'peanut_eval'.`)

    fireEvent.doubleClick(screen.getByText('Dataset')) // NodeChrome header
    const modalWarning = container.querySelector('.modal-body .meta-warning')
    expect(modalWarning?.textContent).toBe("Matched 0 items for loader 'peanut_eval'.")
  })

  it('opens the credentials modal from the top bar', async () => {
    renderApp()
    fireEvent.click(screen.getByTitle('API credentials'))
    expect(await screen.findByText('API Credentials')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByText('API Credentials')).toBeNull()
  })

  it('switches the canvas colorMode with the app theme (drives React Flow\'s own dark styles)', async () => {
    const { container } = renderApp()
    const rf = () => container.querySelector('.react-flow') as HTMLElement

    expect(rf().classList.contains('light')).toBe(true)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    fireEvent.click(screen.getByTitle('Toggle theme'))

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(rf().classList.contains('dark')).toBe(true)
    expect(rf().classList.contains('light')).toBe(false)
  })
})
