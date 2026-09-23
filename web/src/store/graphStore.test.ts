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
    store.getState().addNode('judge', { x: 0, y: 0 })
    const { nodes, selectedNodeId } = store.getState()
    expect(nodes).toHaveLength(1)
    expect(nodes[0].type).toBe('judge')
    expect(nodes[0].data.params.batch_size).toBe(1)
    expect(selectedNodeId).toBe(nodes[0].id)
  })

  it('onConnect only accepts a socket-type-matching connection', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes

    s.onConnect({
      source: ds.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })
    expect(store.getState().edges).toHaveLength(1)

    // labels -> samples is a type mismatch; must be silently rejected.
    s.onConnect({
      source: ds.id, sourceHandle: 'labels', target: judge.id, targetHandle: 'samples',
    })
    expect(store.getState().edges).toHaveLength(1)
  })

  it('onConnect replaces an existing edge into the same input socket (no fan-in)', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('dataset', { x: 0, y: 200 })
    s.addNode('judge', { x: 200, y: 0 })
    const [ds1, ds2, judge] = store.getState().nodes

    s.onConnect({
      source: ds1.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })
    s.onConnect({
      source: ds2.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })
    const edges = store.getState().edges
    expect(edges).toHaveLength(1)
    expect(edges[0].source).toBe(ds2.id)
  })

  it('toJSON/loadGraph round-trip preserves nodes, params, and edges', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes
    s.updateNodeParams(judge.id, { batch_size: 5 })
    s.onConnect({
      source: ds.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })

    const json: GraphSpecJSON = store.getState().toJSON()
    expect(json.nodes).toHaveLength(2)
    expect(json.edges).toEqual([
      { source: ds.id, source_socket: 'samples', target: judge.id, target_socket: 'samples' },
    ])

    store.setState({ nodes: [], edges: [], selectedNodeId: null })
    store.getState().loadGraph(json)

    const restored = store.getState()
    expect(restored.nodes).toHaveLength(2)
    const restoredJudge = restored.nodes.find((n) => n.type === 'judge')
    expect(restoredJudge?.data.params.batch_size).toBe(5)
    expect(restored.edges).toHaveLength(1)
    expect(restored.toJSON()).toEqual(json)
  })

  it('toJSON/loadGraph round-trip preserves an explicitly resized node\'s width/height', () => {
    const s = store.getState()
    s.addNode('judge', { x: 0, y: 0 })
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
    s.addNode('judge', { x: 0, y: 0 })
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

  it('toJSON/loadGraph round-trip restores cosmetic view state (status/collapsed/expandedSize/stale)', () => {
    const s = store.getState()
    s.addNode('judge', { x: 0, y: 0 })
    const [judge] = store.getState().nodes
    store.setState({
      nodes: store.getState().nodes.map((n) =>
        n.id === judge.id ? { ...n, width: 300, height: 220 } : n,
      ),
    })
    s.setNodeStatus(judge.id, 'error', 'boom')
    s.toggleNodeCollapsed(judge.id) // captures expandedSize from the resize above

    const json = store.getState().toJSON(new Set([judge.id]))
    const savedNode = json.nodes[0]
    expect(savedNode.status).toBe('error')
    expect(savedNode.error).toBe('boom')
    expect(savedNode.collapsed).toBe(true)
    expect(savedNode.expanded_size).toEqual({ width: 300, height: 220 })
    expect(savedNode.stale).toBe(true)

    store.setState({ nodes: [], edges: [], selectedNodeId: null })
    store.getState().loadGraph(json)
    const restored = store.getState().nodes[0]
    expect(restored.data.status).toBe('error')
    expect(restored.data.error).toBe('boom')
    expect(restored.data.collapsed).toBe(true)
    expect(restored.data.expandedSize).toEqual({ width: 300, height: 220 })
    // `stale` isn't graphStore's concern (it lives in the separate runStore) — loadGraph
    // itself doesn't restore it; the tabsStore caller reads it straight off the saved JSON.
  })

  it('loadGraph sanitizes a stale "running" status back to "idle"', () => {
    // A node can never genuinely be "running" the instant a workflow is (re)loaded — no
    // run is actually in flight yet — so a workflow saved mid-run must not lie about that.
    store.getState().loadGraph({
      nodes: [{ id: 'judge-1', type: 'judge', params: {}, status: 'running' }],
      edges: [],
    })
    expect(store.getState().nodes[0].data.status).toBe('idle')
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
    s.addNode('judge', { x: 200, y: 0 })
    const [ds, judge] = store.getState().nodes
    s.onConnect({
      source: ds.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })

    s.removeNode(ds.id)
    const state = store.getState()
    expect(state.nodes).toHaveLength(1)
    expect(state.edges).toHaveLength(0)
  })

  it('setNodeStatus updates only the targeted node', () => {
    const s = store.getState()
    s.addNode('judge', { x: 0, y: 0 })
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

  it('autoLayoutNodes marks the graph dirty and increments the fit-view revision', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge', { x: 0, y: 0 })
    const [dataset, judge] = store.getState().nodes
    s.onConnect({
      source: dataset.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples',
    })
    const beforeDirty = dirtyCount
    s.autoLayoutNodes()
    const state = store.getState()
    expect(state.layoutRevision).toBe(1)
    expect(dirtyCount).toBe(beforeDirty + 1)
    expect(state.nodes.find((n) => n.id === judge.id)!.position.x)
      .toBeGreaterThan(state.nodes.find((n) => n.id === dataset.id)!.position.x)
  })

  it('lockNode locks the node and all its predecessors; unlockNode cascades to descendants', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge', { x: 200, y: 0 })
    s.addNode('eval', { x: 400, y: 0 })
    const [ds, judge, ev] = store.getState().nodes
    s.onConnect({ source: ds.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples' })
    s.onConnect({ source: judge.id, sourceHandle: 'judge_result', target: ev.id, targetHandle: 'judge_result' })

    // Locking the judge locks the judge + its predecessor (dataset), not the downstream eval.
    s.lockNode(judge.id)
    const locked = (id: string) => store.getState().nodes.find((n) => n.id === id)!.data.locked
    expect(locked(judge.id)).toBe(true)
    expect(locked(ds.id)).toBe(true)
    expect(locked(ev.id)).toBeFalsy()

    // Unlocking the dataset cascades forward: the judge (its descendant) unlocks too.
    s.unlockNode(ds.id)
    expect(locked(ds.id)).toBe(false)
    expect(locked(judge.id)).toBe(false)
  })

  it('lockNodes/unlockNodes apply to a whole selection at once', () => {
    const s = store.getState()
    s.addNode('dataset', { x: 0, y: 0 })
    s.addNode('judge', { x: 200, y: 0 })
    s.addNode('dataset', { x: 0, y: 200 })
    const [ds1, judge, ds2] = store.getState().nodes
    s.onConnect({ source: ds1.id, sourceHandle: 'samples', target: judge.id, targetHandle: 'samples' })

    // Lock a two-node selection (judge + the unrelated ds2): judge's ancestor ds1 also locks.
    s.lockNodes([judge.id, ds2.id])
    const locked = (id: string) => store.getState().nodes.find((n) => n.id === id)!.data.locked
    expect(locked(judge.id)).toBe(true)
    expect(locked(ds1.id)).toBe(true) // ancestor of judge
    expect(locked(ds2.id)).toBe(true)

    // Unlock the same selection.
    s.unlockNodes([judge.id, ds2.id])
    expect(locked(judge.id)).toBe(false)
    expect(locked(ds2.id)).toBe(false)
  })

  it('locked survives a toJSON/loadGraph round-trip', () => {
    const s = store.getState()
    s.addNode('judge', { x: 0, y: 0 })
    const [judge] = store.getState().nodes
    s.lockNode(judge.id)

    const json = store.getState().toJSON()
    expect(json.nodes[0].locked).toBe(true)
    store.setState({ nodes: [], edges: [], selectedNodeId: null })
    store.getState().loadGraph(json)
    expect(store.getState().nodes[0].data.locked).toBe(true)
  })

  it('groups: add/update/remove + toJSON/loadGraph round-trip', () => {
    const s = store.getState()
    s.addGroup({ x: 10, y: 20 })
    let group = store.getState().groups[0]
    expect(store.getState().groups).toHaveLength(1)
    expect(group.position).toEqual({ x: 10, y: 20 })

    s.updateGroup(group.id, { title: 'Prep', size: { width: 500, height: 400 } })
    group = store.getState().groups[0]
    expect(group.title).toBe('Prep')
    expect(group.size).toEqual({ width: 500, height: 400 })

    const json = store.getState().toJSON()
    expect(json.groups).toEqual([group])
    store.setState({ nodes: [], edges: [], groups: [], selectedNodeId: null })
    store.getState().loadGraph(json)
    expect(store.getState().groups).toEqual([group])

    s.removeGroup(group.id)
    expect(store.getState().groups).toHaveLength(0)
  })
})
