import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { useGraphStore } from './store/graphStore'
import { useRunStore } from './store/runStore'
import { ThemeProvider } from './theme/ThemeProvider'

const NODE_TYPES = [
  {
    type: 'dataset', category: 'node_db', input_sockets: {},
    output_sockets: { dataset: 'dataset', labels: 'labels' }, param_schema: {},
  },
  {
    type: 'judge', category: 'node_vejudge', input_sockets: { dataset: 'dataset' },
    output_sockets: { judge_result: 'judge_result' }, param_schema: {},
  },
  {
    type: 'eval', category: 'node_eval',
    input_sockets: { judge_result: 'judge_result', labels: 'labels' },
    output_sockets: { metrics_report: 'metrics_report' }, param_schema: {},
  },
]

// Set by the meta.warning test below, right before it triggers the run — mockJsonFor needs
// the real (dynamically-generated) node id to key the fake /api/runs/warn-run-1 response.
let warnRunNodeId = ''

function mockJsonFor(url: string): unknown {
  if (url.endsWith('/api/nodes')) return NODE_TYPES
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

  it('toggles the left panel', async () => {
    const { container } = renderApp()
    const toggle = screen.getByTitle('Toggle left panel')
    expect(container.querySelector('.left-panel.collapsed')).toBeNull()
    fireEvent.click(toggle)
    expect(container.querySelector('.left-panel.collapsed')).not.toBeNull()
  })

  it('adding a node from the palette shows it in the Inspector', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('judge'))
    expect(screen.getByRole('heading', { name: 'judge' })).toBeInTheDocument()
    // One copy inline on the node (expanded by default), one in the Inspector.
    expect(screen.getAllByText('skip_video').length).toBe(2)
  })

  it('double-clicking a node opens its secondary tab with a params summary header', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('dataset'))
    const nodeTitle = await screen.findByText('Dataset') // NodeChrome header, not the palette item
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
    fireEvent.click(await screen.findByText('judge'))
    const nodeId = useGraphStore.getState().nodes[0].id

    act(() => {
      useGraphStore.getState().setNodeStatus(nodeId, 'running')
      useRunStore.getState().setCurrentRunningNode(nodeId)
      useRunStore.getState().setNodeProgressTotal(nodeId, 5)
      useRunStore.getState().incrementNodeProgress(nodeId)
      useRunStore.getState().appendLog({ ts: Date.now(), nodeId, text: `${nodeId} x::0 M3` })
    })

    fireEvent.doubleClick(screen.getByText('Judge')) // NodeChrome header
    expect(screen.getByText('Judging…')).toBeInTheDocument()
    // The same log line also appears in the bottom Console (filtered to the selected
    // node), so there can be more than one match — just confirm it rendered somewhere.
    expect(screen.getAllByText(`${nodeId} x::0 M3`).length).toBeGreaterThan(0)
  })

  it('editing a param inline on the node updates the same value the Inspector shows', async () => {
    renderApp()
    fireEvent.click(await screen.findByText('dataset'))

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
    fireEvent.click(await screen.findByText('dataset'))
    // Both the inline node and the Inspector show a "loader" param label while expanded.
    expect(screen.getAllByText('loader').length).toBe(2)

    fireEvent.click(screen.getByTitle('Collapse'))
    // Only the Inspector's copy remains — the node itself now shows the summary line.
    expect(screen.getAllByText('loader').length).toBe(1)
    expect(screen.getByText('loader: peanut_eval')).toBeInTheDocument()
  })

  it('shows a green running border and a live progress bar while a node executes', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('judge'))
    const nodeId = useGraphStore.getState().nodes[0].id

    // Idle: no running highlight, no progress bar.
    expect(container.querySelector('.rf-node.is-running')).toBeNull()
    expect(container.querySelector('.node-progress-bar')).toBeNull()

    act(() => {
      useGraphStore.getState().setNodeStatus(nodeId, 'running')
      useRunStore.getState().setCurrentRunningNode(nodeId)
      useRunStore.getState().setNodeProgressTotal(nodeId, 4)
      useRunStore.getState().incrementNodeProgress(nodeId)
    })

    expect(container.querySelector('.rf-node.is-running')).not.toBeNull()
    const fill = container.querySelector('.node-progress-bar .progress-bar-fill') as HTMLElement
    expect(fill).not.toBeNull()
    expect(fill.style.width).toBe('25%')

    act(() => {
      useGraphStore.getState().setNodeStatus(nodeId, 'done')
    })
    expect(container.querySelector('.rf-node.is-running')).toBeNull()
  })

  it('shows top-bar overall + current-node progress bars only while running', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('judge'))
    const nodeId = useGraphStore.getState().nodes[0].id

    expect(container.querySelector('.run-progress')).toBeNull()

    act(() => {
      useRunStore.getState().beginRun('run-1', 3)
      useRunStore.getState().setCurrentRunningNode(nodeId)
      useRunStore.getState().setNodeProgressTotal(nodeId, 2)
      useRunStore.getState().incrementNodeProgress(nodeId)
      useRunStore.getState().markNodeCompleted('some-other-node')
    })

    expect(screen.getByText('Workflow progress')).toBeInTheDocument()
    expect(screen.getByText(`Running: Judge (${nodeId})`)).toBeInTheDocument()
    const bars = container.querySelectorAll('.run-progress .progress-bar-fill')
    expect(bars).toHaveLength(2)
    expect((bars[0] as HTMLElement).style.width).toBe(`${(1 / 3) * 100}%`) // overall: 1/3 nodes done
    expect((bars[1] as HTMLElement).style.width).toBe('50%') // current node: 1/2

    act(() => {
      useRunStore.getState().setStatus('done')
    })
    expect(container.querySelector('.run-progress')).toBeNull()
  })

  it('surfaces a node meta.warning as a console log line and inside its secondary tab', async () => {
    const { container } = renderApp()
    fireEvent.click(await screen.findByText('dataset'))
    const nodeId = useGraphStore.getState().nodes[0].id
    warnRunNodeId = nodeId

    await act(async () => {
      useRunStore.getState().beginRun('warn-run-1', 1)
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
