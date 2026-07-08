import { beforeEach, describe, expect, it } from 'vitest'
import { createRunStore, type RunStoreApi } from './runStore'

let store: RunStoreApi

beforeEach(() => {
  store = createRunStore()
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
})
