import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { NodeInputsTab } from './NodeInputsTab'
import { NodeOutputsTab } from './NodeOutputsTab'

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
    render(<NodeOutputsTab node={activeGraphStore().getState().nodes[1]} />)
    // socket name + its type tag both read "samples"/"labels" — assert presence.
    expect(screen.getAllByText('samples').length).toBeGreaterThan(0)
    expect(screen.getAllByText('labels').length).toBeGreaterThan(0)
    expect(screen.getByText(/object · 1 key/)).toBeInTheDocument() // samples summarized
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
    render(<NodeInputsTab node={activeGraphStore().getState().nodes[1]} />)
    expect(screen.getAllByText('raw_dataset').length).toBeGreaterThan(0)
    // raw_dataset is a fan-in socket, so the reconstructed value is a list of the wired
    // sources' outputs (here one source) — matching the executor's merge semantics.
    expect(screen.getByText('fan-in')).toBeInTheDocument()
    expect(screen.getByText(/list · 1 item/)).toBeInTheDocument()
  })

  it('shows "not connected" for an unwired input socket', () => {
    seed()
    // The source node itself has no inputs.
    render(<NodeInputsTab node={activeGraphStore().getState().nodes[0]} />)
    expect(screen.getByText(/no input sockets/)).toBeInTheDocument()
  })
})
