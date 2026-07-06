import { useState } from 'react'
import { startRun } from '../../api/runs'
import { useGraphStore } from '../../store/graphStore'
import { useRunStore } from '../../store/runStore'

export function RunControls() {
  const dryRun = useRunStore((s) => s.dryRun)
  const setDryRun = useRunStore((s) => s.setDryRun)
  const status = useRunStore((s) => s.status)
  const beginRun = useRunStore((s) => s.beginRun)
  const [busy, setBusy] = useState(false)

  const handleRun = async () => {
    if (!dryRun) {
      const ok = window.confirm(
        'This run will make real (billable) gateway calls. Continue with --live?',
      )
      if (!ok) return
    }

    setBusy(true)
    try {
      useGraphStore.getState().resetAllStatuses()
      const graph = useGraphStore.getState().toJSON()
      const result = await startRun(graph, dryRun, !dryRun)
      beginRun(result.run_id, graph.nodes.length)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="run-controls">
      <label className="dry-run-toggle">
        <input
          type="checkbox" checked={dryRun}
          onChange={(e) => setDryRun(e.target.checked)}
        />
        Dry run
      </label>
      <button
        className="btn-primary" onClick={handleRun} disabled={busy || status === 'running'}
      >
        {status === 'running' ? 'Running…' : 'Run'}
      </button>
    </div>
  )
}
