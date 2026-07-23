import { beforeEach, describe, expect, it } from 'vitest'
import { createRunStore, type RunStoreApi } from './runStore'

let store: RunStoreApi

beforeEach(() => {
  store = createRunStore()
})

describe('attachRun (open a past run)', () => {
  it('sets runId without going to running status (so useRunSocket hydrates it)', () => {
    store.getState().beginRun('old', 2)
    store.getState().attachRun('260720-10:00:00')
    const s = store.getState()
    expect(s.runId).toBe('260720-10:00:00')
    expect(s.status).toBe('idle') // not 'running' — this is a hydrate, not a launch
    expect(s.partialResults).toEqual({})
  })
})

describe('runStore progress tracking', () => {
  it('beginRun resets progress state using the given node count', () => {
    store.getState().incrementNodeProgress('stale')
    store.getState().beginRun('run-1', 3)

    const s = store.getState()
    expect(s.runId).toBe('run-1')
    expect(s.status).toBe('running')
    expect(s.totalNodes).toBe(3)
    expect(s.completedNodeIds.size).toBe(0)
    expect(s.nodeProgress).toEqual({})
  })

  it('beginRun records whether the run is live, for the cross-tab warning check', () => {
    store.getState().beginRun('run-1', 1, true)
    expect(store.getState().isLive).toBe(true)

    store.getState().reset()
    expect(store.getState().isLive).toBe(false)
  })

  it('setCurrentRunningNode seeds a fresh progress entry for a new node', () => {
    store.getState().setCurrentRunningNode('judge-1')
    const s = store.getState()
    expect(s.currentRunningNodeId).toBe('judge-1')
    expect(s.nodeProgress['judge-1']).toEqual({ completed: 0, total: null })
  })

  it('setCurrentRunningNode does not clobber an existing progress entry', () => {
    store.getState().setCurrentRunningNode('judge-1')
    store.getState().setNodeProgressTotal('judge-1', 10)
    store.getState().incrementNodeProgress('judge-1')
    store.getState().setCurrentRunningNode('judge-1') // re-set same node

    expect(store.getState().nodeProgress['judge-1']).toEqual({ completed: 1, total: 10 })
  })

  it('setNodeProgressTotal + incrementNodeProgress accumulate correctly', () => {
    const s = store.getState()
    s.setCurrentRunningNode('judge-1')
    s.setNodeProgressTotal('judge-1', 4)
    s.incrementNodeProgress('judge-1')
    s.incrementNodeProgress('judge-1')

    expect(store.getState().nodeProgress['judge-1']).toEqual({ completed: 2, total: 4 })
  })

  it('markNodeCompleted records completion and clears currentRunningNodeId when it matches', () => {
    const s = store.getState()
    s.setCurrentRunningNode('ds-1')
    s.markNodeCompleted('ds-1')

    const state = store.getState()
    expect(state.completedNodeIds.has('ds-1')).toBe(true)
    expect(state.currentRunningNodeId).toBeNull()
  })

  it('markNodeCompleted for a non-current node leaves currentRunningNodeId untouched', () => {
    const s = store.getState()
    s.setCurrentRunningNode('judge-1')
    s.markNodeCompleted('ds-1') // a different (already-finished) node

    const state = store.getState()
    expect(state.completedNodeIds.has('ds-1')).toBe(true)
    expect(state.currentRunningNodeId).toBe('judge-1')
  })

  it('setPartialResult stores a live batch-eval preview, keyed by node id', () => {
    store.getState().setPartialResult('eval-1', { metrics_report: { n_items: 2 } }, {})
    expect(store.getState().partialResults['eval-1']).toEqual({
      outputs: { metrics_report: { n_items: 2 } }, meta: {},
    })

    // A later batch overwrites the same node's entry rather than accumulating.
    store.getState().setPartialResult('eval-1', { metrics_report: { n_items: 4 } }, {})
    expect(store.getState().partialResults['eval-1'].outputs).toEqual({
      metrics_report: { n_items: 4 },
    })
  })

  it('beginRun and reset both clear stale partialResults from a previous run', () => {
    store.getState().setPartialResult('eval-1', { metrics_report: { n_items: 2 } }, {})
    store.getState().beginRun('run-2', 3)
    expect(store.getState().partialResults).toEqual({})

    store.getState().setPartialResult('eval-1', { metrics_report: { n_items: 2 } }, {})
    store.getState().reset()
    expect(store.getState().partialResults).toEqual({})
  })

  it('stores cumulative live debates by revision and marks an item complete', () => {
    const first = {
      item_id: 'item-a', metric_id: 'M3', revision: 1,
      turns: [{ round: 1, role: 'human_proxy' as const }],
      state: 'running' as const,
    }
    store.getState().setLiveDebate('cal-1', first)
    store.getState().setLiveDebate('cal-1', { ...first, revision: 0, turns: [] })
    expect(store.getState().liveDebates['cal-1']['item-a'].turns).toHaveLength(1)

    store.getState().setLiveDebate('cal-1', {
      ...first, revision: 2,
      turns: [...first.turns, { round: 1, role: 'judge' as const }],
    })
    store.getState().markLiveDebateComplete('cal-1', 'item-a')
    expect(store.getState().liveDebates['cal-1']['item-a']).toMatchObject({
      revision: 2, state: 'complete',
    })
  })

  it('promotes authoritative results atomically but preserves stopped partial chats', () => {
    const fake = (status: 'done' | 'stopped', outputs: Record<string, unknown>) => ({
      status, error: null, meta: {}, outputs,
    })
    store.getState().setPartialResult('done-node', { calibration_results: { a: {} } }, {})
    store.getState().setPartialResult('stopped-node', { calibration_results: { b: {} } }, {})
    store.getState().setLiveDebate('done-node', {
      item_id: 'a', metric_id: 'M3', revision: 0, turns: [], state: 'running',
    })
    store.getState().setLiveDebate('stopped-node', {
      item_id: 'b', metric_id: 'M3', revision: 0, turns: [], state: 'running',
    })

    store.getState().promoteFinalNodeResults({
      'done-node': fake('done', { calibration_results: { a: { final: true } } }),
      'stopped-node': fake('stopped', {}),
    })

    expect(store.getState().partialResults['done-node']).toBeUndefined()
    expect(store.getState().liveDebates['done-node']).toBeUndefined()
    expect(store.getState().partialResults['stopped-node']).toBeDefined()
    expect(store.getState().liveDebates['stopped-node']).toBeDefined()
    expect(store.getState().lastNodeResults['done-node'].outputs).toEqual({
      calibration_results: { a: { final: true } },
    })
  })

  it('beginRun clears live debates from the prior run', () => {
    store.getState().setLiveDebate('cal-1', {
      item_id: 'a', metric_id: 'M3', revision: 0, turns: [], state: 'running',
    })
    store.getState().beginRun('run-2', 2)
    expect(store.getState().liveDebates).toEqual({})
  })

  it('setLastNodeResults merges into the existing map rather than replacing it', () => {
    const fake = (v: number) => ({ status: 'done', error: null, meta: {}, outputs: { v } })
    store.getState().setLastNodeResults({ a: fake(1), b: fake(2) })
    // A scoped run's node_results only ever covers its own reduced scope — it must not
    // wipe out node 'b's last-known result, which a plain replace would do.
    store.getState().setLastNodeResults({ a: fake(3) })

    const results = store.getState().lastNodeResults
    expect(results.a).toEqual(fake(3))
    expect(results.b).toEqual(fake(2))
  })

  it('setRunOrder replaces the order wholesale on each new run', () => {
    store.getState().setRunOrder(['a', 'b', 'c'])
    expect(store.getState().runOrder).toEqual(['a', 'b', 'c'])
    store.getState().setRunOrder(['judge-1'])
    expect(store.getState().runOrder).toEqual(['judge-1'])
  })

  it('beginRun clears runOrder for the new run', () => {
    store.getState().setRunOrder(['a', 'b'])
    store.getState().beginRun('run-3', 2)
    expect(store.getState().runOrder).toEqual([])
  })

  it('markNodesStale adds ids and clearStale removes one, leaving the rest', () => {
    store.getState().markNodesStale(['eval-1', 'eval-2'])
    expect(store.getState().staleNodeIds).toEqual(new Set(['eval-1', 'eval-2']))

    store.getState().clearStale('eval-1')
    expect(store.getState().staleNodeIds).toEqual(new Set(['eval-2']))
  })

  it('reset clears staleNodeIds', () => {
    store.getState().markNodesStale(['eval-1'])
    store.getState().reset()
    expect(store.getState().staleNodeIds.size).toBe(0)
  })
})
