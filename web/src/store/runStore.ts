import { create } from 'zustand'
import type { NodeResultOut } from '../api/runs'

export type RunStatus = 'idle' | 'running' | 'done' | 'error'

export interface LogLine {
  ts: number
  nodeId?: string
  text: string
}

export interface NodeProgress {
  completed: number
  total: number | null
}

interface RunState {
  runId: string | null
  status: RunStatus
  error: string | null
  logs: LogLine[]
  dryRun: boolean
  // Per-node results (incl. outputs) from the most recently completed run — the data
  // source for the Judge/Eval secondary tabs. Only WS status events arrive live; the
  // full outputs are fetched once via GET when the run completes (see useRunSocket).
  lastNodeResults: Record<string, NodeResultOut>
  // Live progress, driving the 3 progress bars (see interface.md's Run controls).
  nodeProgress: Record<string, NodeProgress>
  currentRunningNodeId: string | null
  totalNodes: number
  completedNodeIds: Set<string>
  setDryRun: (v: boolean) => void
  beginRun: (runId: string, totalNodes: number) => void
  appendLog: (line: LogLine) => void
  setStatus: (status: RunStatus, error?: string | null) => void
  setLastNodeResults: (results: Record<string, NodeResultOut>) => void
  setCurrentRunningNode: (nodeId: string | null) => void
  setNodeProgressTotal: (nodeId: string, total: number) => void
  incrementNodeProgress: (nodeId: string) => void
  markNodeCompleted: (nodeId: string) => void
  reset: () => void
}

export const useRunStore = create<RunState>((set, get) => ({
  runId: null,
  status: 'idle',
  error: null,
  logs: [],
  dryRun: true,
  lastNodeResults: {},
  nodeProgress: {},
  currentRunningNodeId: null,
  totalNodes: 0,
  completedNodeIds: new Set(),

  setDryRun: (v) => set({ dryRun: v }),

  beginRun: (runId, totalNodes) => set({
    runId, status: 'running', error: null, logs: [],
    nodeProgress: {}, currentRunningNodeId: null, totalNodes, completedNodeIds: new Set(),
  }),

  appendLog: (line) => set((s) => ({ logs: [...s.logs, line] })),

  setStatus: (status, error = null) => set({ status, error }),

  setLastNodeResults: (results) => set({ lastNodeResults: results }),

  setCurrentRunningNode: (nodeId) => {
    set((s) => ({
      currentRunningNodeId: nodeId,
      nodeProgress: nodeId && !s.nodeProgress[nodeId]
        ? { ...s.nodeProgress, [nodeId]: { completed: 0, total: null } }
        : s.nodeProgress,
    }))
  },

  setNodeProgressTotal: (nodeId, total) => {
    set((s) => ({
      nodeProgress: {
        ...s.nodeProgress,
        [nodeId]: { completed: s.nodeProgress[nodeId]?.completed ?? 0, total },
      },
    }))
  },

  incrementNodeProgress: (nodeId) => {
    set((s) => {
      const prev = s.nodeProgress[nodeId] ?? { completed: 0, total: null }
      return { nodeProgress: { ...s.nodeProgress, [nodeId]: { ...prev, completed: prev.completed + 1 } } }
    })
  },

  markNodeCompleted: (nodeId) => {
    const { currentRunningNodeId, completedNodeIds } = get()
    const next = new Set(completedNodeIds)
    next.add(nodeId)
    set({
      completedNodeIds: next,
      currentRunningNodeId: currentRunningNodeId === nodeId ? null : currentRunningNodeId,
    })
  },

  reset: () => set({
    runId: null, status: 'idle', error: null, logs: [],
    nodeProgress: {}, currentRunningNodeId: null, totalNodes: 0, completedNodeIds: new Set(),
  }),
}))
