import { useQuery } from '@tanstack/react-query'
import { getRunGraph, listDiskRuns, resumeRun, type DiskRunSummary } from '../../api/runs'
import { useTabsStore } from '../../store/tabsStore'

// Past runs found on disk (logs/exps). Open = inspect the reconstructed graph + statuses +
// outputs; Resume = continue that run from its checkpoints (re-executes, skipping done items).
export function RunsTab() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['diskRuns'],
    queryFn: listDiskRuns,
  })

  const handleOpen = async (r: DiskRunSummary) => {
    const graph = await getRunGraph(r.run_id)
    useTabsStore.getState().openRunTab(r.run_id, graph, r.workflow_name)
  }

  const handleResume = async (r: DiskRunSummary) => {
    const graph = await getRunGraph(r.run_id)
    useTabsStore.getState().openRunTab(r.run_id, graph, r.workflow_name)
    const res = await resumeRun(r.run_id)
    const tab = useTabsStore.getState().getActiveTab()
    tab?.runStore.getState().beginRun(res.run_id, tab.graphStore.getState().nodes.length, false)
    refetch()
  }

  if (isLoading) return <p className="empty-hint">Loading runs…</p>
  if (isError || !data) {
    return <p className="empty-hint">Could not reach the backend. Is vejudge-interface running?</p>
  }
  if (data.length === 0) return <p className="empty-hint">No past runs found under logs/exps.</p>

  // Resume only makes sense for a run that stopped short.
  const resumable = new Set(['error', 'stopped', 'interrupted'])

  return (
    <div>
      {data.map((r) => (
        <div key={r.run_id} className="run-item">
          <div className="run-item-head">
            <span className="run-item-id">{r.run_id}</span>
            <span className={`run-status-tag status-${r.status}`}>{r.status}</span>
          </div>
          <div className="run-item-meta">
            {r.workflow_name ?? 'unnamed'} · {r.n_nodes ?? '?'} nodes · {r.n_checkpointed} cached
          </div>
          <div className="run-item-actions">
            <button onClick={() => handleOpen(r)}>Open</button>
            {resumable.has(r.status) && (
              <button onClick={() => handleResume(r)}>Resume</button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
