import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { resumeRun, startRun, stopRun } from '../../api/runs'
import { listWorkflowRuns } from '../../api/workflows'
import { activeGraphStore, useActiveGraphStore, useActiveRunStore } from '../../store/activeTab'
import { useTabsStore } from '../../store/tabsStore'

// A workflow's latest run is worth offering to resume only if it left work unfinished —
// resuming a cleanly "done" run (or one that's still "running" elsewhere in this same
// server process) has nothing useful to continue.
const RESUMABLE_STATUSES = new Set(['error', 'stopped', 'interrupted'])
const TERMINAL_RUN_STATUSES = new Set(['done', 'error', 'stopped'])

// Checked before showing the --live confirm dialog — a same-window, zero-round-trip scan
// of every OTHER open tab's own runStore for a live run still in flight.
function liveRunInAnotherTab(): boolean {
  const { tabs, activeTabId } = useTabsStore.getState()
  return tabs.some((t) => {
    if (t.tabId === activeTabId) return false
    const rs = t.runStore.getState()
    return rs.status === 'running' && rs.isLive
  })
}

export function RunControls() {
  const queryClient = useQueryClient()
  const dryRun = useActiveRunStore((s) => s.dryRun)
  const setDryRun = useActiveRunStore((s) => s.setDryRun)
  const status = useActiveRunStore((s) => s.status)
  const runId = useActiveRunStore((s) => s.runId)
  const beginRun = useActiveRunStore((s) => s.beginRun)
  const setStatus = useActiveRunStore((s) => s.setStatus)
  const currentWorkflowName = useActiveGraphStore((s) => s.currentWorkflowName)
  const [busy, setBusy] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [resuming, setResuming] = useState(false)

  const { data: workflowRuns } = useQuery({
    queryKey: ['workflowRuns', currentWorkflowName],
    queryFn: () => listWorkflowRuns(currentWorkflowName as string),
    enabled: !!currentWorkflowName,
  })
  const latestRun = workflowRuns?.[0]
  const canResume = !!latestRun && RESUMABLE_STATUSES.has(latestRun.status)

  // The workflowRuns query has no other reason to refetch once a run reaches a terminal
  // state (nothing about `status` changing is itself a query-key change) — without this,
  // the Resume button would never learn about the run that just finished/stopped.
  useEffect(() => {
    if (TERMINAL_RUN_STATUSES.has(status) && currentWorkflowName) {
      queryClient.invalidateQueries({ queryKey: ['workflowRuns', currentWorkflowName] })
    }
  }, [status, currentWorkflowName, queryClient])

  const handleRun = async () => {
    if (!dryRun) {
      const warning = liveRunInAnotherTab()
        ? 'Another open tab has a live run in progress right now. '
        : ''
      const ok = window.confirm(
        `${warning}This run will make real (billable) gateway calls. Continue with --live?`,
      )
      if (!ok) return
    }

    setBusy(true)
    try {
      activeGraphStore().getState().resetAllStatuses()
      const graph = activeGraphStore().getState().toJSON()
      const result = await startRun(graph, dryRun, !dryRun, currentWorkflowName)
      beginRun(result.run_id, graph.nodes.length, !dryRun)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const handleResume = async () => {
    if (!latestRun) return
    if (liveRunInAnotherTab()) {
      const ok = window.confirm(
        'Another open tab has a live run in progress right now. Resume anyway?',
      )
      if (!ok) return
    }
    const ok = window.confirm(
      "Resume continues that run's original graph and parameters, not any changes you've "
        + 'made on the canvas since — continue?',
    )
    if (!ok) return

    setResuming(true)
    try {
      activeGraphStore().getState().resetAllStatuses()
      const result = await resumeRun(latestRun.run_id)
      beginRun(result.run_id, activeGraphStore().getState().nodes.length, latestRun.allow_live)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setResuming(false)
    }
  }

  const handleStop = async () => {
    if (!runId) return
    setStopping(true)
    try {
      await stopRun(runId)
      // The backend already flips to "stopping" synchronously — reflect that immediately
      // rather than waiting for the next websocket event to arrive.
      setStatus('stopping')
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setStopping(false)
    }
  }

  const running = status === 'running'
  const isStopping = status === 'stopping'
  const canStop = running && !!runId

  return (
    <div className="run-controls">
      <label className="dry-run-toggle">
        <input
          type="checkbox" checked={dryRun}
          onChange={(e) => setDryRun(e.target.checked)}
        />
        Dry run
      </label>
      <button className="btn-primary" onClick={handleRun} disabled={busy || running || isStopping}>
        {running ? 'Running…' : isStopping ? 'Stopping…' : 'Run'}
      </button>
      {canStop && (
        <button onClick={handleStop} disabled={stopping}>
          Stop
        </button>
      )}
      {!running && !isStopping && canResume && (
        <button
          onClick={handleResume} disabled={busy || resuming}
          title={`Resume the ${latestRun?.status} run (${latestRun?.n_checkpointed} item(s) already checkpointed)`}
        >
          Resume
        </button>
      )}
    </div>
  )
}
