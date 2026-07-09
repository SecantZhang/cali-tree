import { beforeEach, describe, expect, it } from 'vitest'
import { createGraphStore, type GraphSpecJSON, type GraphStoreApi } from './graphStore'

let store: GraphStoreApi
let dirtyCount = 0

beforeEach(() => {
  dirtyCount = 0
  store = createGraphStore(() => {
    dirtyCount += 1
  })
})

describe('graphStore', () => {
  it('addNode seeds default params from the schema and selects the new node', () => {
    store.getState().addNode('judge_video', { x: 0, y: 0 })
    const { nodes, selectedNodeId } = store.getState()
    expect(nodes).toHaveLength(1)
    expect(nodes[0].type).toBe('judge_video')
    expect(nodes[0].data.params.batch_size).toBe(1)
    expect(selectedNodeId).toBe(nodes[0].id)
  })

  it('onConnect only accepts a socket-type-matching connection', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge_text', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes

    s.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    expect(store.getState().edges).toHaveLength(1)

    // labels -> dataset is a type mismatch; must be silently rejected.
    s.onConnect({
      source: ds.id, sourceHandle: 'labels', target: judge.id, targetHandle: 'dataset',
    })
    expect(store.getState().edges).toHaveLength(1)
  })

  it('onConnect replaces an existing edge into the same input socket (no fan-in)', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('dataset', { x: 0, y: 200 })
    s.addNode('judge_text', { x: 200, y: 0 })
    const [ds1, ds2, judge] = store.getState().nodes

    s.onConnect({
      source: ds1.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    s.onConnect({
      source: ds2.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    const edges = store.getState().edges
    expect(edges).toHaveLength(1)
    expect(edges[0].source).toBe(ds2.id)
  })

  it('toJSON/loadGraph round-trip preserves nodes, params, and edges', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge_video', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes
    s.updateNodeParams(judge.id, { batch_size: 5 })
    s.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })

    const json: GraphSpecJSON = store.getState().toJSON()
    expect(json.nodes).toHaveLength(2)
    expect(json.edges).toEqual([
      { source: ds.id, source_socket: 'dataset', target: judge.id, target_socket: 'dataset' },
    ])

    store.setState({ nodes: [], edges: [], selectedNodeId: null })
    store.getState().loadGraph(json)

    const restored = store.getState()
    expect(restored.nodes).toHaveLength(2)
    const restoredJudge = restored.nodes.find((n) => n.type === 'judge_video')
    expect(restoredJudge?.data.params.batch_size).toBe(5)
    expect(restored.edges).toHaveLength(1)
    expect(restored.toJSON()).toEqual(json)
  })

  it('toJSON/loadGraph round-trip preserves an explicitly resized node\'s width/height', () => {
    const s = store.getState()
    s.addNode('judge_text', { x: 0, y: 0 })
    const [judge] = store.getState().nodes
    // Simulates the post-NodeResizer state (explicit width/height set on the node).
    store.setState({
      nodes: store.getState().nodes.map((n) =>
        n.id === judge.id ? { ...n, width: 300, height: 220 } : n,
      ),
    })

    const json = store.getState().toJSON()
    expect(json.nodes[0].size).toEqual({ width: 300, height: 220 })

    store.setState({ nodes: [], edges: [], selectedNodeId: null })
    store.getState().loadGraph(json)
    const restored = store.getState().nodes[0]
    expect(restored.width).toBe(300)
    expect(restored.height).toBe(220)
  })

  it('toggleNodeCollapsed shrinks a resized node and restores its size on expand', () => {
    const s = store.getState()
    s.addNode('judge_text', { x: 0, y: 0 })
    const [judge] = store.getState().nodes
    store.setState({
      nodes: store.getState().nodes.map((n) =>
        n.id === judge.id ? { ...n, width: 300, height: 220 } : n,
      ),
    })

    s.toggleNodeCollapsed(judge.id)
    const collapsed = store.getState().nodes[0]
    expect(collapsed.data.collapsed).toBe(true)
    expect(collapsed.width).toBeUndefined()
    expect(collapsed.height).toBeUndefined()
    expect(collapsed.data.expandedSize).toEqual({ width: 300, height: 220 })

    s.toggleNodeCollapsed(judge.id)
    const expanded = store.getState().nodes[0]
    expect(expanded.data.collapsed).toBe(false)
    expect(expanded.width).toBe(300)
    expect(expanded.height).toBe(220)
  })

  it('loadGraph falls back to a grid position when a saved node has none', () => {
    store.getState().loadGraph({
      nodes: [{ id: 'ds-1', type: 'dataset', params: {} }],
      edges: [],
    })
    expect(store.getState().nodes[0].position).toEqual({ x: 80, y: 80 })
  })

  it('removeNode also drops edges touching it', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge_text', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes
    s.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })

    s.removeNode(ds.id)
    const state = store.getState()
    expect(state.nodes).toHaveLength(1)
    expect(state.edges).toHaveLength(0)
  })

  it('setNodeStatus updates only the targeted node', () => {
    const s = store.getState()
    s.addNode('judge_text', { x: 0, y: 0 })
    const [judge] = store.getState().nodes
    s.setNodeStatus(judge.id, 'error', 'boom')
    const updated = store.getState().nodes.find((n) => n.id === judge.id)
    expect(updated?.data.status).toBe('error')
    expect(updated?.data.error).toBe('boom')
  })

  it('calls onDirty for content-mutating actions but not for loadGraph/status setters', () => {
    store.getState().addNode('dataset', { x: 0, y: 0 })
    expect(dirtyCount).toBeGreaterThan(0)

    const countAfterAdd = dirtyCount
    const [node] = store.getState().nodes
    store.getState().setNodeStatus(node.id, 'running')
    store.getState().selectNode(node.id)
    expect(dirtyCount).toBe(countAfterAdd)

    store.getState().loadGraph({ nodes: [], edges: [] })
    expect(dirtyCount).toBe(countAfterAdd)
  })
})
