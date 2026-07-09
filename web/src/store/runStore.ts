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
  // The most recently *launched* run's actual execution scope and order (Jupyter-style
  // order badge — see NodeChrome.tsx): a full graph run carries every node id; a per-node
  // Run carries that node's ancestor closure; a Re-run carries just that one node id.
  // Replaced wholesale at the start of every run (`beginRun`/`setRunOrder`), so the badge
  // always reflects the latest launched run, not a running union of past runs.
  runOrder: string[]
  // Nodes whose last real result predates a since-changed ancestor (a per-node Run/Re-run
  // elsewhere in the graph) — flagged the moment such a run is *launched* (not on
  // completion), and cleared the moment that specific node itself completes a run (see
  // useRunSocket.ts's node_status handling), regardless of which run scope did it.
  staleNodeIds: Set<string>
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
  setRunOrder: (order: string[]) => void
  markNodesStale: (nodeIds: Iterable<string>) => void
  clearStale: (nodeId: string) => void
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
    runOrder: [],
    staleNodeIds: new Set(),

    setDryRun: (v) => set({ dryRun: v }),

    beginRun: (runId, totalNodes, isLive = false) => set({
      runId, status: 'running', error: null, logs: [], isLive, partialResults: {},
      nodeProgress: {}, currentRunningNodeId: null, totalNodes, completedNodeIds: new Set(),
      runOrder: [],
    }),

    appendLog: (line) => set((s) => ({ logs: [...s.logs, line] })),

    setStatus: (status, error = null) => set({ status, error }),

    // Merged, not replaced: a scoped Run/Re-run's node_results only ever covers that run's
    // reduced scope (see api/runs.ts's ScopedRunOptions), so replacing the whole map here
    // would wipe out every other node's last-known result the moment a scoped run finishes.
    // A no-op-equivalent difference for a full graph run, whose results already cover
    // every node anyway.
    setLastNodeResults: (results) => set((s) => ({ lastNodeResults: { ...s.lastNodeResults, ...results } })),

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

    // Also corrects `totalNodes` (the overall progress bar's denominator — RunProgress.tsx)
    // to the run's real scope: `beginRun`'s own `totalNodes` argument is only a rough
    // initial guess for a scoped Run/Re-run (the caller doesn't know the ancestor-closure
    // size without asking the backend), and this event is the backend's authoritative
    // answer, arriving moments after the run starts.
    setRunOrder: (order) => set({ runOrder: order, totalNodes: order.length }),

    markNodesStale: (nodeIds) => {
      set((s) => {
        const next = new Set(s.staleNodeIds)
        for (const id of nodeIds) next.add(id)
        return { staleNodeIds: next }
      })
    },

    clearStale: (nodeId) => {
      set((s) => {
        if (!s.staleNodeIds.has(nodeId)) return s
        const next = new Set(s.staleNodeIds)
        next.delete(nodeId)
        return { staleNodeIds: next }
      })
    },

    reset: () => set({
      runId: null, status: 'idle', error: null, logs: [], isLive: false, partialResults: {},
      nodeProgress: {}, currentRunningNodeId: null, totalNodes: 0, completedNodeIds: new Set(),
      runOrder: [], staleNodeIds: new Set(),
    }),
  }))
}
