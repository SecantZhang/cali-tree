import { ProgressBar } from '../../components/ProgressBar'
import { nodeTitle } from '../../nodes/nodeTitles'
import { useActiveGraphStore, useActiveRunStore } from '../../store/activeTab'

/**
 * Bars (b) and (c) from interface.md's Run controls section: overall workflow progress
 * (nodes completed / total), and directly below it, the currently-running node's own
 * progress — the same data driving that node's bar on the canvas (NodeChrome), just
 * also visible here so you don't need the node in view. Both bars stay visible at all
 * times, showing a flat "Idle" state before/between runs rather than disappearing.
 */
export function RunProgress() {
  const status = useActiveRunStore((s) => s.status)
  const totalNodes = useActiveRunStore((s) => s.totalNodes)
  const completedCount = useActiveRunStore((s) => s.completedNodeIds.size)
  const currentRunningNodeId = useActiveRunStore((s) => s.currentRunningNodeId)
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress)
  const currentNode = useActiveGraphStore((s) => s.nodes.find((n) => n.id === currentRunningNodeId))

  const running = status === 'running'

  const overall = running ? { completed: completedCount, total: totalNodes || null } : null
  const current = running && currentRunningNodeId ? nodeProgress[currentRunningNodeId] ?? null : null
  const currentLabel = running && currentNode
    ? `Running: ${nodeTitle(currentNode.type)} (${currentNode.id})`
    : 'Idle — no run in progress'

  return (
    <div className="run-progress">
      <ProgressBar
        inline
        progress={overall}
        label={running ? 'Workflow progress' : 'Workflow progress — Idle'}
      />
      <ProgressBar inline progress={current} label={currentLabel} />
    </div>
  )
}
