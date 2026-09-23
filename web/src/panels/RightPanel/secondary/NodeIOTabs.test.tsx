import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { NodeTypeOut } from '../../../api/nodes'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { NodeInputsTab } from './NodeInputsTab'
import { NodeOutputsTab } from './NodeOutputsTab'

// The schema header + socket lists are sourced from the live node-type API (GET /api/nodes),
// not the static socketTypes.ts mirror. Mock that API here — and deliberately include an
// output socket (`debug_extra`) that does NOT exist in the static mirror, so the tests prove
// the tabs reflect the API, not the hand-maintained file.
const MOCK_NODE_TYPES: NodeTypeOut[] = [
  {
    type: 'peanut_source', category: 'node_db',
    input_sockets: {}, output_sockets: { raw_dataset: 'raw_dataset' },
    multi_input_sockets: [], param_schema: {},
  },
  {
    type: 'dataset', category: 'node_db',
    input_sockets: { raw_dataset: 'raw_dataset' },
    output_sockets: { samples: 'samples', labels: 'labels', debug_extra: 'metrics_report' },
    multi_input_sockets: ['raw_dataset'], param_schema: {},
  },
]

vi.mock('../../../api/nodes', () => ({
  fetchNodeTypes: vi.fn(async () => MOCK_NODE_TYPES),
}))

// Render with a QueryClient whose ['nodeTypes'] cache is pre-seeded, so useNodeSchema resolves
// synchronously on first render (no waitFor needed).
function renderWithSchema(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['nodeTypes'], MOCK_NODE_TYPES)
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

function seed() {
  useTabsStore.getState().openBlankTab()
  const g = activeGraphStore().getState()
  // dataset (raw_dataset in -> samples/labels out) fed by a peanut source.
  g.addNode('peanut_source', { x: 0, y: 0 })
  g.addNode('dataset', { x: 300, y: 0 })
  const [src, ds] = activeGraphStore().getState().nodes
  activeGraphStore().getState().onConnect({
    source: src.id, sourceHandle: 'raw_dataset', target: ds.id, targetHandle: 'raw_dataset',
  })
  return { src, ds }
}

describe('NodeOutputsTab', () => {
  it('lists each output socket with its value from the run store', () => {
    const { ds } = seed()
    activeRunStore().getState().setLastNodeResults({
      [ds.id]: {
        status: 'done', error: null, meta: {},
        outputs: { samples: { 'a::0::x': {} }, labels: {} },
      },
    })
    renderWithSchema(<NodeOutputsTab node={activeGraphStore().getState().nodes[1]} />)
    // socket name + its type tag both read "samples"/"labels" — assert presence.
    expect(screen.getAllByText('samples').length).toBeGreaterThan(0)
    expect(screen.getAllByText('labels').length).toBeGreaterThan(0)
    // samples value summarized (also matches the schema example summary now — both present)
    expect(screen.getAllByText(/object · 1 key/).length).toBeGreaterThan(0)
  })

  it('renders an Output schema header sourced from the API (not the static mirror)', () => {
    seed()
    renderWithSchema(<NodeOutputsTab node={activeGraphStore().getState().nodes[1]} />)
    expect(screen.getByText('Output schema')).toBeInTheDocument()
    // `debug_extra` exists only in the mocked API response, not socketTypes.ts — its presence
    // proves the header reflects the live schema, so future backend sockets appear for free.
    // It shows in both the schema header and (value-less) value card, both API-sourced.
    expect(screen.getAllByText('debug_extra').length).toBeGreaterThan(0)
  })

  it('shows an expandable example payload per socket in the schema header', () => {
    seed()
    const { container } = renderWithSchema(
      <NodeOutputsTab node={activeGraphStore().getState().nodes[1]} />,
    )
    // The `samples` socket has a representative example — rendered as a collapsed <details>
    // inside the schema header that expands to real JSON subfields (item_id, use_case, …).
    const example = container.querySelector('.socket-schema-example details')
    expect(example).not.toBeNull()
    // Its expanded JSON pre carries the example's subfields.
    const pre = example!.querySelector('.json-preview')
    expect(pre?.textContent).toContain('item_id')
    expect(pre?.textContent).toContain('use_case')
  })
})

describe('NodeInputsTab', () => {
  it('reconstructs the input from the upstream node output on the wired edge', () => {
    const { src } = seed()
    // Only the SOURCE produced output; the Inputs tab of the dataset should surface it on
    // its raw_dataset socket by walking the edge back to the source's output.
    activeRunStore().getState().setLastNodeResults({
      [src.id]: {
        status: 'done', error: null, meta: {},
        outputs: { raw_dataset: { 'a::0::peanut': {}, 'b::0::peanut': {} } },
      },
    })
    renderWithSchema(<NodeInputsTab node={activeGraphStore().getState().nodes[1]} />)
    expect(screen.getByText('Input schema')).toBeInTheDocument()
    expect(screen.getAllByText('raw_dataset').length).toBeGreaterThan(0)
    // raw_dataset is a fan-in socket, so the reconstructed value is a list of the wired
    // sources' outputs (here one source) — matching the executor's merge semantics. The
    // fan-in tag shows in both the schema header and the value card.
    expect(screen.getAllByText('fan-in').length).toBeGreaterThan(0)
    expect(screen.getByText(/list · 1 item/)).toBeInTheDocument()
  })

  it('shows "no input sockets" for a source node', () => {
    seed()
    // The source node itself has no inputs.
    renderWithSchema(<NodeInputsTab node={activeGraphStore().getState().nodes[0]} />)
    expect(screen.getByText(/no input sockets/)).toBeInTheDocument()
  })
})
