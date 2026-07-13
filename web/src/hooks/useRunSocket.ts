import { useEffect } from 'react'
import { getRun, type RunStatusOut } from '../api/runs'
import { wsUrl } from '../api/client'
import type { GraphStoreApi } from '../store/graphStore'
import type { RunStatus, RunStoreApi } from '../store/runStore'
import type { NodeStatus } from '../nodes/types'

interface RunEvent {
  type: string
  node_id?: string
  status?: string
  error?: string | null
  item_id?: string
  metric_id?: string
  detail?: string
  total?: number
  outputs?: Record<string, unknown>
  meta?: Record<string, unknown>
  order?: string[]
}

// "stopping" is an in-between state — not running-as-normal, but not terminal either (it
// will still transition to "stopped") — so anywhere this repo checks "is this run over",
// it must check against this set, not just `!== 'running'`.
const TERMINAL_STATUSES = new Set(['done', 'error', 'stopped'])

// A node can finish with status "done" and still have done nothing useful (e.g. a Dataset
// Node that matched 0 items) — the backend flags that in `meta.warning` rather than
// `error`, since it's not necessarily wrong, just worth a human's attention. WS status
// events don't carry `meta` (see the module doc below), so this only runs once full
// results are fetched — surfacing it as a log line is the one place every run (WS or the
// fast-completion path) is guaranteed to pass through.
function appendWarningLogs(runStore: RunStoreApi, nodeResults: RunStatusOut['node_results']) {
  const { appendLog } = runStore.getState()
  for (const [nodeId, result] of Object.entries(nodeResults)) {
    const warning = result.meta?.warning
    if (typeof warning === 'string' && warning) {
      appendLog({ ts: Date.now(), nodeId, text: `${nodeId}: warning — ${warning}` })
    }
  }
}

/**
 * Streams one run's progress into a tab's own `runStore` (logs/status/per-node progress)
 * and `graphStore` (per-node status dots). Takes the target tab's store instances
 * explicitly rather than reading module-global singletons — this is mounted once per open
 * tab, unconditionally (see App.tsx's RunSocketManager), so a backgrounded tab's run keeps
 * streaming into its own stores even while a different tab is active/visible.
 *
 * Always resyncs via GET before subscribing to the WS, since a run can finish before the
 * socket connects — a non-"running" resync is itself the terminal signal and the socket
 * closes right after, with no further events to wait for.
 *
 * WS events only carry status deltas, not outputs (that payload can be large), so once
 * a run reaches a terminal state this re-fetches the full result once via GET to
 * populate runStore.lastNodeResults — the data source for the Judge/Eval secondary tabs.
 */
export function useRunSocket(
  runId: string | null,
  runStore: RunStoreApi,
  graphStore: GraphStoreApi,
) {
  useEffect(() => {
    if (!runId) return
    const id: string = runId

    let cancelled = false
    let ws: WebSocket | null = null

    // Applies a terminal RunStatusOut's per-node statuses, exactly like a live WS
    // node_status event would have. Needed because the WS resync path (below) can observe
    // an already-terminal run and only ever sets the *overall* status + fetches results —
    // if that resync fires before any `node_status` events reached this client (a real,
    // reproducible race: the run finishes between the WS accepting and its own internal
    // status check, so its whole `handle.events` queue is skipped and never drained — see
    // `routes/ws.py`), individual nodes would otherwise be stuck showing a stale status
    // dot forever despite the overall run correctly reading "done".
    function applyFinalNodeStatuses(nodeResults: RunStatusOut['node_results']) {
      const { setNodeStatus } = graphStore.getState()
      for (const [nodeId, result] of Object.entries(nodeResults)) {
        setNodeStatus(nodeId, result.status as NodeStatus, result.error ?? null)
      }
    }

    async function finalizeRun() {
      const final = await getRun(id).catch(() => null)
      if (!cancelled && final) {
        applyFinalNodeStatuses(final.node_results)
        runStore.getState().setLastNodeResults(final.node_results)
        // Exactly this run's coverage (replaced, not merged) — gates lock-eligibility.
        runStore.getState().setLastRunNodeIds(Object.keys(final.node_results))
        appendWarningLogs(runStore, final.node_results)
        // Redundant with the `run_order` WS event in the common case (both fire), but this
        // is the only source of truth once the run has already finished — cheap to repeat.
        if (final.order?.length) {
          runStore.getState().setRunOrder(final.order)
          for (const nodeId of final.order) runStore.getState().clearStale(nodeId)
        }
      }
    }

    function applyEvent(event: RunEvent) {
      const {
        appendLog, setStatus, setCurrentRunningNode, markNodeCompleted,
        setNodeProgressTotal, incrementNodeProgress,
      } = runStore.getState()
      const { setNodeStatus } = graphStore.getState()

      if (event.type === 'node_status' && event.node_id) {
        const status = (event.status as NodeStatus) ?? 'running'
        setNodeStatus(event.node_id, status, event.error ?? null)
        if (status === 'running') {
          setCurrentRunningNode(event.node_id)
        } else if (TERMINAL_STATUSES.has(status)) {
          markNodeCompleted(event.node_id)
          // This node just produced a fresh result (any terminal outcome, not only
          // "done" — even an error/stop means it was actually re-attempted) — clear its
          // stale flag regardless of which run scope (full/ancestors/self_only) did it.
          runStore.getState().clearStale(event.node_id)
        }
        appendLog({
          ts: Date.now(),
          nodeId: event.node_id,
          text: `${event.node_id}: ${event.status}${event.error ? ` (${event.error})` : ''}`,
        })
      } else if (event.type === 'run_order') {
        runStore.getState().setRunOrder(event.order ?? [])
      } else if (
        (event.type === 'judge_progress_init' || event.type === 'calibration_progress_init') &&
        event.node_id && event.total != null
      ) {
        setNodeProgressTotal(event.node_id, event.total)
      } else if (
        event.type === 'judge_item_start' || event.type === 'judge_metric' ||
        event.type === 'calibration_item_start' || event.type === 'calibration_item_done'
      ) {
        if (
          (event.type === 'judge_metric' || event.type === 'calibration_item_done') &&
          event.node_id
        ) {
          incrementNodeProgress(event.node_id)
        }
        appendLog({
          ts: Date.now(),
          nodeId: event.node_id,
          text: [event.node_id, event.item_id, event.metric_id].filter(Boolean).join(' '),
        })
      } else if (event.type === 'partial_result' && event.node_id) {
        runStore.getState().setPartialResult(event.node_id, event.outputs ?? {}, event.meta ?? {})
      } else if (event.type === 'run_complete') {
        setStatus((event.status as RunStatus) ?? 'done', event.error ?? null)
      } else if (event.type === 'run_status' && event.status) {
        setStatus(event.status as RunStatus)
      } else if (event.type === 'error') {
        setStatus('error', event.detail ?? 'unknown error')
      }
    }

    async function resyncThenSubscribe() {
      const current = await getRun(id).catch(() => null)
      if (cancelled || !current) return

      if (TERMINAL_STATUSES.has(current.status)) {
        // The run can finish before this very first GET fires (a trivial or fast-failing
        // graph, e.g. a single unwired node, or a scoped Run/Re-run over a tiny/dry-run
        // graph) — no WS events ever arrive in that case, so per-node statuses (and the
        // order/stale bookkeeping below) have to be applied here too, not just the overall
        // run status. `current.order` is exactly this run's real execution scope (mirrors
        // the `run_order` WS event, just via REST — see GraphRunResult.order), so — unlike
        // a blind loop over every key in `node_results` (which, for a self_only re-run,
        // also includes seeded/not-actually-executed nodes) — it's safe to clear stale
        // flags for precisely these nodes and no others.
        applyFinalNodeStatuses(current.node_results ?? {})
        if (current.order?.length) {
          runStore.getState().setRunOrder(current.order)
          for (const nodeId of current.order) runStore.getState().clearStale(nodeId)
        }
        runStore.getState().setStatus(current.status as RunStatus, current.error)
        runStore.getState().setLastNodeResults(current.node_results)
        runStore.getState().setLastRunNodeIds(Object.keys(current.node_results ?? {}))
        appendWarningLogs(runStore, current.node_results ?? {})
        return
      }

      ws = new WebSocket(wsUrl(`/api/runs/${id}/ws`))
      ws.onmessage = (msg) => {
        const event = JSON.parse(msg.data) as RunEvent
        if (event.type === 'resync') {
          if (event.status && TERMINAL_STATUSES.has(event.status)) {
            runStore.getState().setStatus(event.status as RunStatus, null)
            void finalizeRun()
          }
          return
        }
        applyEvent(event)
        if (event.type === 'run_complete') {
          void finalizeRun()
        }
      }
    }

    resyncThenSubscribe()

    return () => {
      cancelled = true
      ws?.close()
    }
  }, [runId, runStore, graphStore])
}
