import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type { NodeResultOut } from '../api/runs'

export type RunStatus = 'idle' | 'running' | 'stopping' | 'stopped' | 'done' | 'error'

export interface LogLine {
  ts: number
  nodeId?: string
  text: string
}

export interface NodeProgress {
  completed: number
  total: number | null
}

// A live, in-flight preview of a `supports_partial_input` node's output (today, only Eval
// nodes wired downstream of a Judge Node with `batch_size` set) — recomputed from scratch
// on every batch, so this always reflects the latest cumulative snapshot, not a delta.
export interface PartialResult {
  outputs: Record<string, unknown>
  meta: Record<string, unknown>
}

export interface RunState {
  runId: string | null
  status: RunStatus
  error: string | null
  logs: LogLine[]
  dryRun: boolean
  // Whether the *current* run was launched with --live (real billable calls) — read by the
  // cross-tab warning (RunControls.tsx) when another tab's Run/Resume is clicked while this
  // one is still `running`.
  isLive: boolean
  // Per-node results (incl. outputs) from the most recently completed run — the data
  // source for the Judge/Eval secondary tabs. Only WS status events arrive live; the
  // full outputs are fetched once via GET when the run completes (see useRunSocket).
  lastNodeResults: Record<string, NodeResultOut>
  // Live batch-eval previews, keyed by node id — populated from `partial_result` WS
  // events while a run is in flight. Cleared at the start of each run; superseded by
  // `lastNodeResults` once the node's own authoritative run finishes.
  partialResults: Record<string, PartialResult>
  // Live progress, driving the 3 progress bars (see interface.md's Run controls).
  nodeProgress: Record<string, NodeProgress>
  currentRunningNodeId: string | null
  totalNodes: number
  completedNodeIds: Set<string>
  setDryRun: (v: boolean) => void
  beginRun: (runId: string, totalNodes: number, isLive?: boolean) => void
  appendLog: (line: LogLine) => void
  setStatus: (status: RunStatus, error?: string | null) => void
  setLastNodeResults: (results: Record<string, NodeResultOut>) => void
  setPartialResult: (nodeId: string, outputs: Record<string, unknown>, meta: Record<string, unknown>) => void
  setCurrentRunningNode: (nodeId: string | null) => void
  setNodeProgressTotal: (nodeId: string, total: number) => void
  incrementNodeProgress: (nodeId: string) => void
  markNodeCompleted: (nodeId: string) => void
  reset: () => void
}

export type RunStoreApi = UseBoundStore<StoreApi<RunState>>

/** One run document's worth of state — one instance per open tab (see tabsStore.ts). */
export function createRunStore(): RunStoreApi {
  return create<RunState>((set, get) => ({
    runId: null,
    status: 'idle',
    error: null,
    logs: [],
    dryRun: true,
    isLive: false,
    lastNodeResults: {},
    partialResults: {},
    nodeProgress: {},
    currentRunningNodeId: null,
    totalNodes: 0,
    completedNodeIds: new Set(),

    setDryRun: (v) => set({ dryRun: v }),

    beginRun: (runId, totalNodes, isLive = false) => set({
      runId, status: 'running', error: null, logs: [], isLive, partialResults: {},
      nodeProgress: {}, currentRunningNodeId: null, totalNodes, completedNodeIds: new Set(),
    }),

    appendLog: (line) => set((s) => ({ logs: [...s.logs, line] })),

    setStatus: (status, error = null) => set({ status, error }),

    setLastNodeResults: (results) => set({ lastNodeResults: results }),

    setPartialResult: (nodeId, outputs, meta) => {
      set((s) => ({ partialResults: { ...s.partialResults, [nodeId]: { outputs, meta } } }))
    },

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
      runId: null, status: 'idle', error: null, logs: [], isLive: false, partialResults: {},
      nodeProgress: {}, currentRunningNodeId: null, totalNodes: 0, completedNodeIds: new Set(),
    }),
  }))
}
