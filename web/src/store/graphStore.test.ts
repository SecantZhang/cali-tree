import { beforeEach, describe, expect, it } from 'vitest'
import { useGraphStore, type GraphSpecJSON } from './graphStore'

beforeEach(() => {
  useGraphStore.setState({ nodes: [], edges: [], selectedNodeId: null })
})

describe('graphStore', () => {
  it('addNode seeds default params from the schema and selects the new node', () => {
    useGraphStore.getState().addNode('judge', { x: 0, y: 0 })
    const { nodes, selectedNodeId } = useGraphStore.getState()
    expect(nodes).toHaveLength(1)
    expect(nodes[0].type).toBe('judge')
    expect(nodes[0].data.params.skip_video).toBe(false)
    expect(selectedNodeId).toBe(nodes[0].id)
  })

  it('onConnect only accepts a socket-type-matching connection', () => {
    const store = useGraphStore.getState()
    store.addNode('dataset', { x: 0, y: 0 })
    store.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = useGraphStore.getState().nodes

    store.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    expect(useGraphStore.getState().edges).toHaveLength(1)

    // labels -> dataset is a type mismatch; must be silently rejected.
    store.onConnect({
      source: ds.id, sourceHandle: 'labels', target: judge.id, targetHandle: 'dataset',
    })
    expect(useGraphStore.getState().edges).toHaveLength(1)
  })

  it('onConnect replaces an existing edge into the same input socket (no fan-in)', () => {
    const store = useGraphStore.getState()
    store.addNode('dataset', { x: 0, y: 0 })
    store.addNode('dataset', { x: 0, y: 200 })
    store.addNode('judge', { x: 200, y: 0 })
    const [ds1, ds2, judge] = useGraphStore.getState().nodes

    store.onConnect({
      source: ds1.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    store.onConnect({
      source: ds2.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })
    const edges = useGraphStore.getState().edges
    expect(edges).toHaveLength(1)
    expect(edges[0].source).toBe(ds2.id)
  })

  it('toJSON/loadGraph round-trip preserves nodes, params, and edges', () => {
    const store = useGraphStore.getState()
    store.addNode('dataset', { x: 0, y: 0 })
    store.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = useGraphStore.getState().nodes
    store.updateNodeParams(judge.id, { skip_video: true })
    store.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })

    const json: GraphSpecJSON = useGraphStore.getState().toJSON()
    expect(json.nodes).toHaveLength(2)
    expect(json.edges).toEqual([
      { source: ds.id, source_socket: 'dataset', target: judge.id, target_socket: 'dataset' },
    ])

    useGraphStore.setState({ nodes: [], edges: [], selectedNodeId: null })
    useGraphStore.getState().loadGraph(json)

    const restored = useGraphStore.getState()
    expect(restored.nodes).toHaveLength(2)
    const restoredJudge = restored.nodes.find((n) => n.type === 'judge')
    expect(restoredJudge?.data.params.skip_video).toBe(true)
    expect(restored.edges).toHaveLength(1)
    expect(restored.toJSON()).toEqual(json)
  })

  it('removeNode also drops edges touching it', () => {
    const store = useGraphStore.getState()
    store.addNode('dataset', { x: 0, y: 0 })
    store.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = useGraphStore.getState().nodes
    store.onConnect({
      source: ds.id, sourceHandle: 'dataset', target: judge.id, targetHandle: 'dataset',
    })

    store.removeNode(ds.id)
    const state = useGraphStore.getState()
    expect(state.nodes).toHaveLength(1)
    expect(state.edges).toHaveLength(0)
  })

  it('setNodeStatus updates only the targeted node', () => {
    const store = useGraphStore.getState()
    store.addNode('judge', { x: 0, y: 0 })
    const [judge] = useGraphStore.getState().nodes
    store.setNodeStatus(judge.id, 'error', 'boom')
    const updated = useGraphStore.getState().nodes.find((n) => n.id === judge.id)
    expect(updated?.data.status).toBe('error')
    expect(updated?.data.error).toBe('boom')
  })
})
