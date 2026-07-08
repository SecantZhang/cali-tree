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

    async function finalizeRun() {
      const final = await getRun(id).catch(() => null)
      if (!cancelled && final) {
        runStore.getState().setLastNodeResults(final.node_results)
        appendWarningLogs(runStore, final.node_results)
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
        }
        appendLog({
          ts: Date.now(),
          nodeId: event.node_id,
          text: `${event.node_id}: ${event.status}${event.error ? ` (${event.error})` : ''}`,
        })
      } else if (event.type === 'judge_progress_init' && event.node_id && event.total != null) {
        setNodeProgressTotal(event.node_id, event.total)
      } else if (event.type === 'judge_item_start' || event.type === 'judge_metric') {
        if (event.type === 'judge_metric' && event.node_id) {
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
        // graph, e.g. a single unwired node) — no WS events ever arrive in that case, so
        // per-node statuses have to be applied here too, not just the overall run status.
        const { setNodeStatus } = graphStore.getState()
        for (const [nodeId, result] of Object.entries(current.node_results ?? {})) {
          setNodeStatus(nodeId, result.status as NodeStatus, result.error ?? null)
        }
        runStore.getState().setStatus(current.status as RunStatus, current.error)
        runStore.getState().setLastNodeResults(current.node_results)
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
