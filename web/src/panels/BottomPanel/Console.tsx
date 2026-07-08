import { useActiveGraphStore, useActiveRunStore } from '../../store/activeTab'

export function Console({ height }: { height: number }) {
  const logs = useActiveRunStore((s) => s.logs)
  const status = useActiveRunStore((s) => s.status)
  const runError = useActiveRunStore((s) => s.error)
  const selectedNodeId = useActiveGraphStore((s) => s.selectedNodeId)

  const visible = selectedNodeId ? logs.filter((l) => l.nodeId === selectedNodeId) : logs

  return (
    <div className="bottom-panel" style={{ height }}>
      <div className="console-header">
        <span>Run status: {status}</span>
        {runError && <span className="console-error"> — {runError}</span>}
        {selectedNodeId && <span className="filter-hint"> (filtered to {selectedNodeId})</span>}
      </div>
      {visible.length === 0 && <p className="empty-hint">Run a graph to see live logs here.</p>}
      {visible.map((l, i) => (
        <div key={`${l.ts}-${i}`} className="console-line">
          {l.text}
        </div>
      ))}
    </div>
  )
}
