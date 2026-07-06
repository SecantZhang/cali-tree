import { beforeEach, describe, expect, it } from 'vitest'
import { useRunStore } from './runStore'

beforeEach(() => {
  useRunStore.getState().reset()
})

describe('runStore progress tracking', () => {
  it('beginRun resets progress state using the given node count', () => {
    useRunStore.getState().incrementNodeProgress('stale')
    useRunStore.getState().beginRun('run-1', 3)

    const s = useRunStore.getState()
    expect(s.runId).toBe('run-1')
    expect(s.status).toBe('running')
    expect(s.totalNodes).toBe(3)
    expect(s.completedNodeIds.size).toBe(0)
    expect(s.nodeProgress).toEqual({})
  })

  it('setCurrentRunningNode seeds a fresh progress entry for a new node', () => {
    useRunStore.getState().setCurrentRunningNode('judge-1')
    const s = useRunStore.getState()
    expect(s.currentRunningNodeId).toBe('judge-1')
    expect(s.nodeProgress['judge-1']).toEqual({ completed: 0, total: null })
  })

  it('setCurrentRunningNode does not clobber an existing progress entry', () => {
    useRunStore.getState().setCurrentRunningNode('judge-1')
    useRunStore.getState().setNodeProgressTotal('judge-1', 10)
    useRunStore.getState().incrementNodeProgress('judge-1')
    useRunStore.getState().setCurrentRunningNode('judge-1') // re-set same node

    expect(useRunStore.getState().nodeProgress['judge-1']).toEqual({ completed: 1, total: 10 })
  })

  it('setNodeProgressTotal + incrementNodeProgress accumulate correctly', () => {
    const store = useRunStore.getState()
    store.setCurrentRunningNode('judge-1')
    store.setNodeProgressTotal('judge-1', 4)
    store.incrementNodeProgress('judge-1')
    store.incrementNodeProgress('judge-1')

    expect(useRunStore.getState().nodeProgress['judge-1']).toEqual({ completed: 2, total: 4 })
  })

  it('markNodeCompleted records completion and clears currentRunningNodeId when it matches', () => {
    const store = useRunStore.getState()
    store.setCurrentRunningNode('ds-1')
    store.markNodeCompleted('ds-1')

    const s = useRunStore.getState()
    expect(s.completedNodeIds.has('ds-1')).toBe(true)
    expect(s.currentRunningNodeId).toBeNull()
  })

  it('markNodeCompleted for a non-current node leaves currentRunningNodeId untouched', () => {
    const store = useRunStore.getState()
    store.setCurrentRunningNode('judge-1')
    store.markNodeCompleted('ds-1') // a different (already-finished) node

    const s = useRunStore.getState()
    expect(s.completedNodeIds.has('ds-1')).toBe(true)
    expect(s.currentRunningNodeId).toBe('judge-1')
  })
})
